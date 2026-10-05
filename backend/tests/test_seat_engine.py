import pytest

from app.constants import ABSENT_RELEASE, ABSENT_RETAIN
from app.services.seat_engine import (
    PlanReconcileError,
    SeatAssign,
    find_violations,
    manhattan,
    place_candidates,
    register_view,
    seat_snapshot,
)


def cands(n=12):
    return [{"id": i, "name": f"C{i}", "ticket_no": f"T{i}", "paper_id": 1 + (i % 2)}
            for i in range(1, n + 1)]


def test_manhattan():
    assert manhattan((0, 0), (2, 1)) == 3


def test_min_distance_placement():
    assigns, unplaced = place_candidates(4, 4, 2, cands(4))
    assert len(assigns) + len(unplaced) == 4
    for i, a in enumerate(assigns):
        for b in assigns[i + 1:]:
            assert manhattan((a.row, a.col), (b.row, b.col)) >= 2


def test_violation_detection():
    assigns = [SeatAssign(1, "A", "T1", 1, 0, 0), SeatAssign(2, "B", "T2", 1, 0, 1)]
    kinds = {v.kind for v in find_violations(2, 2, 2, assigns)}
    assert "distance" in kinds and "same_paper_adjacent" in kinds


# ---- 08 策略：缺考占格口径 ----

def test_no_absence_means_absent_zero():
    snap = seat_snapshot(5, 6, 2, cands(), absent_ids=set(), strategy=ABSENT_RETAIN)
    assert snap["stats"]["absent"] == 0
    assert register_view(snap)["counts"]["absent"] == 0


def test_retain_absent_occupies_seat_and_not_unplaced():
    snap = seat_snapshot(5, 6, 2, cands(), absent_ids={2, 5}, strategy=ABSENT_RETAIN)
    st = snap["stats"]
    assert st["absent"] == 2
    assert st["seated"] == 10
    assert st["unplaced"] == 0
    assert st["occupied"] == 12  # 已到 10 + 缺考 2，缺考计入占格
    reserved = {a["candidate_id"] for a in snap["assignments"] if a["absent"]}
    assert reserved == {2, 5}
    assert {u["id"] for u in snap["unplaced"]} == set()  # 缺考不得再记入未排


def test_release_absent_does_not_occupy():
    snap = seat_snapshot(5, 6, 2, cands(), absent_ids={2, 5}, strategy=ABSENT_RELEASE)
    st = snap["stats"]
    assert st["absent"] == 2
    assert st["seated"] == 10
    assert st["occupied"] == 10  # 缺考不占格
    assert not any(a["absent"] for a in snap["assignments"])
    assert {u["id"] for u in snap["unplaced"]} == set()


def test_register_matches_stats_both_strategies():
    for strat in (ABSENT_RETAIN, ABSENT_RELEASE):
        snap = seat_snapshot(5, 6, 2, cands(), absent_ids={3}, strategy=strat)
        reg = register_view(snap)
        assert reg["counts"]["arrived"] == snap["stats"]["seated"]
        assert reg["counts"]["absent"] == snap["stats"]["absent"]
        assert reg["counts"]["unseated"] == snap["stats"]["unplaced"]
        assert reg["counts"]["occupied"] == snap["stats"]["occupied"]


def test_three_buckets_partition_all_candidates():
    snap = seat_snapshot(5, 6, 2, cands(12), absent_ids={1, 7}, strategy=ABSENT_RETAIN)
    reg = register_view(snap)
    ids = (
        {a["candidate_id"] for a in reg["arrived"]}
        | {x["id"] for x in reg["absent"]}
        | {u["id"] for u in reg["unseated"]}
    )
    assert ids == {c["id"] for c in cands(12)}


def test_retain_overflow_is_reconcile_failure_not_silent_fudge():
    # 4 格容量，5 名缺考需各占一格 → 无法满足占格口径，必须失败而非凑数。
    with pytest.raises(PlanReconcileError):
        seat_snapshot(2, 2, 2, cands(6), absent_ids={1, 2, 3, 4, 5}, strategy=ABSENT_RETAIN)


def test_release_frees_seats_for_attendees():
    # 3 格容量，retain 时缺考锁格会挤出到场考生；release 时空位可安排到场考生。
    people = cands(5)
    rel = seat_snapshot(1, 3, 1, people, absent_ids={1, 2}, strategy=ABSENT_RELEASE)
    assert rel["stats"]["seated"] == 3
    assert rel["stats"]["occupied"] == 3
    ret = seat_snapshot(1, 3, 1, people, absent_ids={1, 2}, strategy=ABSENT_RETAIN)
    assert ret["stats"]["seated"] == 1          # 两格被缺考占，只剩 1 格给到场者
    assert ret["stats"]["occupied"] == 3
    assert ret["stats"]["unplaced"] == 2        # 3 名到场者中 2 名无格可排
