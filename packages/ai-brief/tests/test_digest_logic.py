"""condenser / image_judge 的纯逻辑单测（不触 API）。"""
from __future__ import annotations

from ai_brief.digest.condenser import _rebalance
from ai_brief.digest.image_judge import _parse_index
from ai_brief.digest.models import BuilderItem


def _items() -> dict[int, BuilderItem]:
    out = {}
    for i in range(1, 11):
        out[i] = BuilderItem(
            index=i, is_top5=(i <= 5), person=f"P{i}", headline=f"H{i}", body="b", url="u"
        )
    return out


def test_rebalance_enforces_2a_3b() -> None:
    by = _items()
    order = _rebalance([1, 2, 6, 7, 8], by)          # 正好 2A + 3B
    assert order == [1, 2, 6, 7, 8]


def test_rebalance_fixes_wrong_counts() -> None:
    by = _items()
    # 模型错选 4 条 A、1 条 B → 应收敛到 2A + 3B
    order = _rebalance([1, 2, 3, 4, 6], by)
    a = [i for i in order if i <= 5]
    b = [i for i in order if i > 5]
    assert len(a) == 2 and len(b) == 3
    assert a == [1, 2]                                 # 保留前2个 A
    assert 6 in b                                       # 保留模型选的 B，其余按序补


def test_rebalance_all_b_only_picked() -> None:
    by = _items()
    order = _rebalance([6, 7, 8, 9, 10], by)
    a = [i for i in order if i <= 5]
    b = [i for i in order if i > 5]
    assert len(a) == 2 and len(b) == 3
    assert a == [1, 2]                                  # 无 A 被选 → 按序补 1,2


def test_clip_sentence() -> None:
    from ai_brief.digest.condenser import _clip_sentence
    # 短文本原样返回
    assert _clip_sentence("完整核心观点。", 120) == "完整核心观点。"
    # 超限 → 收在窗口内最后一个句末标点，成完整句、不留半截
    long = "他认为AI降低门槛，人人可创造。但成本控制是真痛点，账单可能暴涨失控。"
    r = _clip_sentence(long, 18)
    assert r.endswith("。") and len(r) <= 18
    # 窗口内无句末标点 → 去尾部连接词标点并加省略号
    r2 = _clip_sentence("要点一，要点二，要点三，要点四，要点五，要点六", 8)
    assert r2.endswith("…") and "，" not in r2[-1]


def test_parse_index() -> None:
    assert _parse_index("2", 3) == 2
    assert _parse_index("图 1", 3) == 1
    assert _parse_index("我选 0 号", 3) == 0
    assert _parse_index("5", 3) == 0                    # 越界 → 回退 0
    assert _parse_index("没有数字", 3) == 0
