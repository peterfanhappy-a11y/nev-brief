"""Summarizer pipeline orchestrator."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import psycopg
from nev_pipeline.entity_dict import load_entity_dict
from nev_shared.logger import get_logger

from nev_summarizer.candidates_builder import build_candidate
from nev_summarizer.cluster_aggregator import Cluster, aggregate_clusters
from nev_summarizer.cluster_scoring import cluster_importance
from nev_summarizer.deepseek_summarizer import ClusterSummary, summarize_cluster
from nev_summarizer.storage import upsert_daily_brief

log = get_logger("summarizer.runner")

DEFAULT_CONCURRENCY = 5
DEFAULT_TOP_N = 35


def _is_nev_cluster(cluster: Cluster, nev_canonical: set[str]) -> bool:
    """A cluster qualifies as NEV-relevant iff at least one of its brands maps to
    an entity_dict canonical brand (i.e. a known auto brand).

    Articles with brands=[] are dropped — DeepSeek would have extracted a brand
    if one was mentioned. brands=[] correlates strongly with non-NEV content
    (financial / general tech / ETF / etc.) per empirical 2026-06-02 data.
    """
    return bool(set(cluster.brands) & nev_canonical)


async def _summarize_with_semaphore(
    cluster: Cluster, score: float, semaphore: asyncio.Semaphore,
) -> tuple[Cluster, float, ClusterSummary | None]:
    async with semaphore:
        summary = await summarize_cluster(cluster)
        return cluster, score, summary


async def run_brief_for_date(
    conn: psycopg.Connection,
    brief_date: date,
    top_n: int = DEFAULT_TOP_N,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[str, Any]:
    """End-to-end pipeline: read processed → score → top-N → summarize → upsert."""
    clusters = aggregate_clusters(conn, brief_date)
    log.info("clusters_loaded", date=str(brief_date), n=len(clusters))

    nev_canonical = set(load_entity_dict().brands_by_canonical.keys())
    nev_clusters = [c for c in clusters if _is_nev_cluster(c, nev_canonical)]
    dropped = len(clusters) - len(nev_clusters)
    log.info("nev_filter_applied",
             total=len(clusters), nev_relevant=len(nev_clusters), dropped=dropped)

    scored: list[tuple[Cluster, float]] = [
        (c, cluster_importance(c)) for c in nev_clusters
    ]
    scored.sort(key=lambda x: -x[1])
    top = scored[:top_n]

    if not top:
        # No clusters → still upsert empty candidates so downstream sees today's run
        upsert_daily_brief(conn, brief_date, [])
        return {
            "brief_date": str(brief_date),
            "clusters": 0,
            "summarized": 0,
            "truncated": 0,
        }

    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(*[
        _summarize_with_semaphore(c, s, semaphore) for c, s in top
    ])

    candidates: list[dict[str, Any]] = []
    truncated = 0
    rank = 1
    for cluster, score, summary in results:
        if summary is None:
            continue  # fail-safe: skip clusters where DeepSeek failed entirely
        if summary.used_truncation:
            truncated += 1
        candidates.append(build_candidate(cluster, summary, score, rank))
        rank += 1

    upsert_daily_brief(conn, brief_date, candidates)
    log.info(
        "brief_done", date=str(brief_date),
        clusters=len(clusters), summarized=len(candidates), truncated=truncated,
    )
    return {
        "brief_date": str(brief_date),
        "clusters": len(clusters),
        "summarized": len(candidates),
        "truncated": truncated,
    }
