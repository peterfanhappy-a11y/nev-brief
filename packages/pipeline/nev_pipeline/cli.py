"""nev_pipeline CLI — python -m nev_pipeline run [--limit N]"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

import psycopg
from nev_shared.config import get_settings
from nev_shared.logger import configure_logging, get_logger

from nev_pipeline.clustering import ClusterCandidate
from nev_pipeline.runner import process_article
from nev_pipeline.storage import (
    claim_pending,
    load_recent_processed,
    mark_raw_done,
    mark_raw_failed,
    upsert_processed,
)

log = get_logger("pipeline.cli")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m nev_pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="处理待处理文章")
    run.add_argument("--limit", type=int, default=50, help="单次最多处理条数")
    return p


def _to_candidate(row: dict) -> ClusterCandidate:
    return ClusterCandidate(
        brands=list(row.get("brands") or []),
        models=list(row.get("models") or []),
        simhash=int(row["simhash"]),
        published_at=row["published_at"],
        cluster_id=str(row["cluster_id"]) if row.get("cluster_id") else None,
    )


def _processed_to_candidate(processed: dict) -> ClusterCandidate:
    return ClusterCandidate(
        brands=processed["brands"],
        models=processed["models"],
        simhash=processed["simhash"],
        published_at=processed.get("published_at") or datetime.now(tz=timezone.utc),
        cluster_id=processed["cluster_id"],
    )


async def _async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    conn = psycopg.connect(settings.database_url)
    try:
        batch = claim_pending(conn, args.limit)
        conn.commit()
        log.info("claimed", n=len(batch))
        if not batch:
            print("OK 0 articles to process.")
            return 0

        recent = [_to_candidate(r) for r in load_recent_processed(conn, hours=24)]
        log.info("loaded_recent", n=len(recent))

        ok = 0
        for raw in batch:
            try:
                processed = await process_article(raw, recent)
                # 把 published_at 带过去给后续聚类传播；DB 写入不需要这个字段
                processed_with_pub = {**processed, "published_at": raw.get("published_at")}
                upsert_processed(conn, processed)
                mark_raw_done(conn, raw["id"])
                conn.commit()
                recent.append(_processed_to_candidate(processed_with_pub))
                ok += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("process_failed", raw_id=str(raw["id"]), error=str(exc))
                conn.rollback()
                try:
                    mark_raw_failed(conn, raw["id"], str(exc))
                    conn.commit()
                except Exception as exc2:  # noqa: BLE001
                    log.error("mark_failed_failed", raw_id=str(raw["id"]), error=str(exc2))
                    conn.rollback()

        log.info("pipeline_done", ok=ok, total=len(batch))
        print(f"OK {ok}/{len(batch)} articles processed.")
        return 0 if ok > 0 else 1
    finally:
        conn.close()


def main() -> int:
    args = _build_parser().parse_args()
    if args.cmd == "run":
        return asyncio.run(_async_main(args))
    return 2


if __name__ == "__main__":
    sys.exit(main())
