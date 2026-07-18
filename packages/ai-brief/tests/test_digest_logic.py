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


def test_rebalance_enforces_2A_3B() -> None:
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


def test_rebalance_all_B_only_picked() -> None:
    by = _items()
    order = _rebalance([6, 7, 8, 9, 10], by)
    a = [i for i in order if i <= 5]
    b = [i for i in order if i > 5]
    assert len(a) == 2 and len(b) == 3
    assert a == [1, 2]                                  # 无 A 被选 → 按序补 1,2


def test_parse_index() -> None:
    assert _parse_index("2", 3) == 2
    assert _parse_index("图 1", 3) == 1
    assert _parse_index("我选 0 号", 3) == 0
    assert _parse_index("5", 3) == 0                    # 越界 → 回退 0
    assert _parse_index("没有数字", 3) == 0
