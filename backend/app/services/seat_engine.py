"""Exam seating: min Manhattan distance; same paper_id cannot be 4-neighbor adjacent.

缺考占格策略（08 策略口径，全系统唯一来源）：
  retain  —— 缺考占格保留：缺考者保留一个座位（占格、桌位空置），计入占格，不计入未排；
             其空位不参与最小间距/同卷判定（无人即无相邻问题）。
  release —— 释放策略：缺考者不保留座位、不占格；空出的桌位可继续安排其他到场考生。

两种策略下考生都被唯一地归入三类之一：已到(seated) / 缺考(absent) / 未排(unseated)，
三者两两不交且并集为全体考生。reconcile_plan 校验这些口径，对不齐即抛错。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

from app.constants import ABSENT_RELEASE, ABSENT_RETAIN, ABSENT_STRATEGIES


class PlanReconcileError(ValueError):
    """核对册 / 统计 / 排座图口径不一致。"""


@dataclass
class SeatAssign:
    candidate_id: int
    name: str
    ticket_no: str
    paper_id: int
    row: int
    col: int
    absent: bool = False


@dataclass
class Violation:
    kind: str
    a_id: int
    b_id: int
    detail: str


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def neighbors4(r: int, c: int, rows: int, cols: int) -> list[tuple[int, int]]:
    out = []
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append((nr, nc))
    return out


def _first_free(occupied: dict, rows: int, cols: int) -> tuple[int, int] | None:
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in occupied:
                return (r, c)
    return None


def place_candidates(
    rows: int,
    cols: int,
    min_dist: int,
    candidates: list[dict],
    absent_ids: set[int] | None = None,
    strategy: str = ABSENT_RETAIN,
) -> tuple[list[SeatAssign], list[dict]]:
    """返回 (占格 assignments, 到场却未排座的考生 unplaced)。

    retain：先为每位缺考者预留一个空位（不施加间距约束），再安排到场考生；
    release：缺考者不占格，直接跳过；空出的桌位可安排到场考生。
    未排(unplaced)只包含「到场但引擎未能排座」的考生，任何策略下都不含缺考者。
    """
    if strategy not in ABSENT_STRATEGIES:
        raise ValueError(f"未知缺考占格策略: {strategy}")
    absent_ids = set(absent_ids or ())
    occupied: dict[tuple[int, int], SeatAssign] = {}
    seated: dict[tuple[int, int], SeatAssign] = {}

    # 1) retain：缺考占格保留——优先锁定空位，空桌不参与间距/同卷判定。
    if strategy == ABSENT_RETAIN:
        for cand in candidates:
            if cand["id"] not in absent_ids:
                continue
            pos = _first_free(occupied, rows, cols)
            if pos is None:
                break  # 容量不足以保留占格；reconcile 会因缺考未占格而报错
            occupied[pos] = SeatAssign(cand["id"], cand["name"], cand["ticket_no"],
                                       cand["paper_id"], pos[0], pos[1], absent=True)

    # 2) 安排到场考生。
    unplaced: list[dict] = []
    for cand in candidates:
        if cand["id"] in absent_ids:
            continue  # release：不占格；retain：已在上方预留
        placed = False
        for r in range(rows):
            for c in range(cols):
                if (r, c) in occupied:
                    continue
                ok = True
                for pos, other in seated.items():
                    if manhattan((r, c), pos) < min_dist:
                        ok = False
                        break
                    if other.paper_id == cand["paper_id"] and (r, c) in neighbors4(pos[0], pos[1], rows, cols):
                        ok = False
                        break
                if not ok:
                    continue
                for nr, nc in neighbors4(r, c, rows, cols):
                    if (nr, nc) in seated and seated[(nr, nc)].paper_id == cand["paper_id"]:
                        ok = False
                        break
                if not ok:
                    continue
                assign = SeatAssign(cand["id"], cand["name"], cand["ticket_no"], cand["paper_id"], r, c)
                occupied[(r, c)] = assign
                seated[(r, c)] = assign
                placed = True
                break
            if placed:
                break
        if not placed:
            unplaced.append(cand)
    return list(occupied.values()), unplaced


def find_violations(rows: int, cols: int, min_dist: int, assigns: list[SeatAssign]) -> list[Violation]:
    viols: list[Violation] = []
    # 缺考保留的空桌无人，不参与任何违规判定。
    present = [a for a in assigns if not a.absent]
    for i, a in enumerate(present):
        for b in present[i + 1:]:
            d = manhattan((a.row, a.col), (b.row, b.col))
            if d < min_dist:
                viols.append(Violation("distance", a.candidate_id, b.candidate_id,
                                       f"曼哈顿距离 {d} < 最小要求 {min_dist}"))
            if a.paper_id == b.paper_id and (b.row, b.col) in neighbors4(a.row, a.col, rows, cols):
                viols.append(Violation("same_paper_adjacent", a.candidate_id, b.candidate_id,
                                       f"同试卷套 {a.paper_id} 四邻相邻"))
    return viols


def seat_snapshot(
    rows: int,
    cols: int,
    min_dist: int,
    candidates: list[dict],
    absent_ids: set[int] | None = None,
    strategy: str = ABSENT_RETAIN,
    hall: dict | None = None,
) -> dict:
    """排座并产出唯一权威快照；统计、违规、排座图、核对册全部从这一份派生。"""
    if strategy not in ABSENT_STRATEGIES:
        raise ValueError(f"未知缺考占格策略: {strategy}")
    absent_ids = {c["id"] for c in candidates if c["id"] in (absent_ids or set())}
    assigns, unplaced = place_candidates(rows, cols, min_dist, candidates, absent_ids, strategy)
    viols = find_violations(rows, cols, min_dist, assigns)

    present_assigns = [a for a in assigns if not a.absent]
    absent_list = [c for c in candidates if c["id"] in absent_ids]

    snapshot = {
        "rows": rows,
        "cols": cols,
        "assignments": [asdict(a) for a in assigns],
        "unplaced": unplaced,
        "absent": absent_list,
        "violations": [asdict(v) for v in viols],
        "stats": {
            "seated": len(present_assigns),          # 已到
            "absent": len(absent_list),              # 缺考
            "unplaced": len(unplaced),               # 未排（到场未排座）
            "occupied": len(assigns),                # 占格
            "capacity": rows * cols,
            "violations": len(viols),
            "strategy": strategy,
        },
    }
    if hall is not None:
        snapshot["hall"] = hall
    reconcile_plan(snapshot, candidates, absent_ids, strategy)
    return snapshot


def reconcile_plan(snapshot: dict, candidates: list[dict], absent_ids: set[int], strategy: str) -> None:
    """校验快照内部口径：三类不交且覆盖全体；占格数与 08 策略一致；计数自洽。

    任何不一致都抛 PlanReconcileError——核对册/统计/排座图对不齐即失败，绝不静默凑数。
    """
    if strategy not in ABSENT_STRATEGIES:
        raise PlanReconcileError(f"未知缺考占格策略: {strategy}")
    st = snapshot.get("stats", {})
    assigns = snapshot.get("assignments", [])
    unplaced = snapshot.get("unplaced", [])
    absent = snapshot.get("absent", [])

    seated_ids = {a["candidate_id"] for a in assigns if not a.get("absent")}
    reserved_ids = {a["candidate_id"] for a in assigns if a.get("absent")}
    unplaced_ids = {u["id"] for u in unplaced}
    absent_set = {a["id"] for a in absent}
    expected_absent = set(absent_ids or ())
    all_ids = {c["id"] for c in candidates}

    errors: list[str] = []

    if absent_set != expected_absent:
        errors.append(f"缺考名单不符: 快照 {sorted(absent_set)} != 登记 {sorted(expected_absent)}")
    if st.get("absent") != len(expected_absent):
        errors.append(f"缺考计数 {st.get('absent')} != 登记人数 {len(expected_absent)}")

    # 三类两两不交。
    if seated_ids & expected_absent:
        errors.append(f"缺考者被排入座位: {sorted(seated_ids & expected_absent)}")
    if unplaced_ids & expected_absent:
        errors.append(f"缺考者被记入未排: {sorted(unplaced_ids & expected_absent)}")
    if seated_ids & unplaced_ids:
        errors.append(f"已到与未排重叠: {sorted(seated_ids & unplaced_ids)}")

    # 到场考生 = 已到 ∪ 未排，全体 = 已到 ∪ 缺考 ∪ 未排。
    attendee_ids = all_ids - expected_absent
    if seated_ids | unplaced_ids != attendee_ids:
        missing = attendee_ids - (seated_ids | unplaced_ids)
        extra = (seated_ids | unplaced_ids) - attendee_ids
        errors.append(f"到场考生未被唯一归类, 缺失 {sorted(missing)} 多余 {sorted(extra)}")
    if seated_ids | expected_absent | unplaced_ids != all_ids:
        errors.append("已到/缺考/未排未能覆盖全体考生")

    # 08 策略占格口径。
    if strategy == ABSENT_RETAIN:
        if reserved_ids != expected_absent:
            errors.append(f"保留策略下缺考须各占一格: 占格 {sorted(reserved_ids)} != 缺考 {sorted(expected_absent)}")
        if st.get("occupied") != st.get("seated") + st.get("absent"):
            errors.append("保留策略下占格须 = 已到 + 缺考")
    else:  # release
        if reserved_ids:
            errors.append(f"释放策略下缺考不得占格, 却保留了 {sorted(reserved_ids)}")
        if st.get("occupied") != st.get("seated"):
            errors.append("释放策略下占格须 = 已到（缺考不占格）")

    if st.get("seated") != len(seated_ids):
        errors.append(f"已到计数 {st.get('seated')} != 实际排座 {len(seated_ids)}")
    if st.get("unplaced") != len(unplaced_ids):
        errors.append(f"未排计数 {st.get('unplaced')} != 实际未排 {len(unplaced_ids)}")
    if st.get("occupied") != len(assigns):
        errors.append(f"占格计数 {st.get('occupied')} != 实际占格 {len(assigns)}")
    if st.get("capacity") != snapshot.get("rows", 0) * snapshot.get("cols", 0):
        errors.append("容量计数与网格不符")
    if st.get("violations") != len(snapshot.get("violations", [])):
        errors.append("违规计数与明细不符")

    if errors:
        raise PlanReconcileError("; ".join(errors))


def normalize_snapshot(data: dict) -> dict:
    """补齐历史方案缺失的缺考字段（旧方案本就没有缺考：absent=0、按保留口径 occupied=seated）。"""
    data = dict(data)
    assigns = list(data.get("assignments") or [])
    for a in assigns:
        a.setdefault("absent", False)
    data["assignments"] = assigns
    data.setdefault("absent", [])
    data.setdefault("unplaced", [])
    data.setdefault("violations", [])
    stats = dict(data.get("stats") or {})
    stats.setdefault("seated", sum(1 for a in assigns if not a.get("absent")))
    stats.setdefault("absent", len(data["absent"]))
    stats.setdefault("unplaced", len(data["unplaced"]))
    stats.setdefault("occupied", len(assigns))
    stats.setdefault("capacity", data.get("rows", 0) * data.get("cols", 0))
    stats.setdefault("violations", len(data["violations"]))
    stats.setdefault("strategy", ABSENT_RETAIN)
    data["stats"] = stats
    return data


def register_view(snapshot: dict) -> dict:
    """从同一快照派生只读核对册视图，并独立重算每个计数核对。

    这里不相信 stats 字段，而是从 assignments/absent/unplaced 明细重算，
    与统计口径对不上即抛 PlanReconcileError（对不齐失败，绝不凑数）。
    """
    st = snapshot["stats"]
    strategy = st.get("strategy", ABSENT_RETAIN)
    arrived = [a for a in snapshot["assignments"] if not a.get("absent")]
    absent_seats = [a for a in snapshot["assignments"] if a.get("absent")]
    absent_list = snapshot.get("absent", [])
    unseated = snapshot.get("unplaced", [])

    n_arrived = len(arrived)
    n_absent = len(absent_list)
    n_unseated = len(unseated)
    n_occupied = len(snapshot["assignments"])

    errors: list[str] = []
    if st.get("seated") != n_arrived:
        errors.append(f"已到: 统计 {st.get('seated')} != 明细 {n_arrived}")
    if st.get("absent") != n_absent:
        errors.append(f"缺考: 统计 {st.get('absent')} != 明细 {n_absent}")
    if st.get("unplaced") != n_unseated:
        errors.append(f"未排: 统计 {st.get('unplaced')} != 明细 {n_unseated}")
    if st.get("occupied") != n_occupied:
        errors.append(f"占格: 统计 {st.get('occupied')} != 明细 {n_occupied}")

    # 三类不交，且缺考不得混进已到/未排。
    arrived_ids = {a["candidate_id"] for a in arrived}
    absent_ids = {a["id"] for a in absent_list}
    unseated_ids = {u["id"] for u in unseated}
    held_ids = {a["candidate_id"] for a in absent_seats}
    if arrived_ids & absent_ids or unseated_ids & absent_ids or arrived_ids & unseated_ids:
        errors.append("已到/缺考/未排三类存在交叉")

    # 08 策略占格口径独立复核。
    if strategy == ABSENT_RETAIN:
        if held_ids != absent_ids:
            errors.append("保留策略下每位缺考须各占一格")
        if n_occupied != n_arrived + n_absent:
            errors.append("保留策略下占格须 = 已到 + 缺考")
    else:
        if held_ids or n_occupied != n_arrived:
            errors.append("释放策略下缺考不得占格，占格须 = 已到")

    if errors:
        raise PlanReconcileError("; ".join(errors))

    return {
        "strategy": strategy,
        "counts": {
            "arrived": n_arrived,
            "absent": n_absent,
            "unseated": n_unseated,
            "occupied": n_occupied,
            "capacity": st.get("capacity"),
        },
        "arrived": arrived,
        "absent": absent_list,
        "absent_seats": absent_seats,
        "unseated": unseated,
    }
