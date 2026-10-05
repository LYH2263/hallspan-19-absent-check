"""Exam seating: min Manhattan distance; same paper_id cannot be 4-neighbor adjacent.

缺考策略（与 08 策略口径一致）：
- reserve（缺考占格保留）：缺考考生仍占一个格子，计入占格，且不得记入未排；
  占格不是真人，故不参与间距 / 同卷违规判定。
- release（释放策略）：缺考考生既不占格，也不计入未排。

两种策略下都必须满足核对恒等式：
    名册人数 = 已到(seated) + 缺考(absent) + 未排(unplaced)
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

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

def _first_free_cell(rows: int, cols: int, taken: set[tuple[int, int]]) -> tuple[int, int] | None:
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in taken:
                return (r, c)
    return None

def place_candidates(rows: int, cols: int, min_dist: int, candidates: list[dict],
                     absent_ids: set[int] | None = None,
                     reserve_absent: bool = False) -> tuple[list[SeatAssign], list[dict]]:
    """Greedy row-major placement.

    返回 (assigns, unplaced)。assigns 含正常到考座位与（占格策略下的）缺考占格，
    缺考占格以 ``absent=True`` 标记。unplaced 只含到考却排不下的考生。
    """
    absent_ids = set(absent_ids or [])
    held: dict[tuple[int, int], SeatAssign] = {}          # 缺考占格：占位但不产生间距约束
    seated: dict[tuple[int, int], SeatAssign] = {}        # 到考考生
    unplaced: list[dict] = []

    def taken(pos: tuple[int, int]) -> bool:
        return pos in held or pos in seated

    for cand in candidates:
        if cand["id"] in absent_ids:
            if reserve_absent:
                pos = _first_free_cell(rows, cols, set(held) | set(seated))
                if pos is not None:
                    held[pos] = SeatAssign(cand["id"], cand["name"], cand["ticket_no"],
                                           cand["paper_id"], pos[0], pos[1], absent=True)
            # 释放策略：缺考直接跳过，不占格、不入未排
            continue

        placed = False
        for r in range(rows):
            for c in range(cols):
                if taken((r, c)):
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
                # also check 4-neigh same paper against current neighbors
                for nr, nc in neighbors4(r, c, rows, cols):
                    if (nr, nc) in seated and seated[(nr, nc)].paper_id == cand["paper_id"]:
                        ok = False
                        break
                if not ok:
                    continue
                seated[(r, c)] = SeatAssign(cand["id"], cand["name"], cand["ticket_no"],
                                            cand["paper_id"], r, c)
                placed = True
                break
            if placed:
                break
        if not placed:
            unplaced.append(cand)

    ordered = [held[pos] for pos in sorted(held)] + [seated[pos] for pos in sorted(seated)]
    return ordered, unplaced

def find_violations(rows: int, cols: int, min_dist: int, assigns: list[SeatAssign]) -> list[Violation]:
    viols: list[Violation] = []
    people = [a for a in assigns if not a.absent]
    by_pos = {(a.row, a.col): a for a in people}
    for i, a in enumerate(people):
        for b in people[i + 1:]:
            d = manhattan((a.row, a.col), (b.row, b.col))
            if d < min_dist:
                viols.append(Violation("distance", a.candidate_id, b.candidate_id,
                                       f"曼哈顿距离 {d} < 最小要求 {min_dist}"))
            if a.paper_id == b.paper_id and (b.row, b.col) in neighbors4(a.row, a.col, rows, cols):
                viols.append(Violation("same_paper_adjacent", a.candidate_id, b.candidate_id,
                                       f"同试卷套 {a.paper_id} 四邻相邻"))
    return viols

def plan_to_dict(assigns: list[SeatAssign], unplaced: list[dict], viols: list[Violation],
                 rows: int, cols: int, absent_rows: list[dict] | None = None,
                 reserve_absent: bool = False) -> dict:
    absent_rows = absent_rows or []
    seated = [a for a in assigns if not a.absent]
    held = [a for a in assigns if a.absent]
    stats = {
        "seated": len(seated),
        "absent": len(absent_rows),
        "absent_held": len(held),
        "unplaced": len(unplaced),
        "violations": len(viols),
        "capacity": rows * cols,
        "occupied": len(seated) + len(held),
        "roster_total": len(seated) + len(absent_rows) + len(unplaced),
        "reserve_absent_seat": reserve_absent,
    }
    return {
        "rows": rows,
        "cols": cols,
        "reserve_absent_seat": reserve_absent,
        "assignments": [asdict(a) for a in assigns],
        "absent": absent_rows,
        "unplaced": unplaced,
        "violations": [asdict(v) for v in viols],
        "stats": stats,
    }

def build_plan(rows: int, cols: int, min_dist: int, candidates: list[dict],
               absent_ids: set[int] | None = None, reserve_absent: bool = False) -> dict:
    """编排一次排座并做口径核对；任何恒等式对不上直接抛错（对不齐失败）。"""
    absent_ids = set(absent_ids or [])
    assigns, unplaced = place_candidates(rows, cols, min_dist, candidates,
                                         absent_ids, reserve_absent)
    by_id = {c["id"]: c for c in candidates}
    unknown = absent_ids - set(by_id)
    if unknown:
        raise ValueError(f"缺考名单含未知考生: {sorted(unknown)}")

    held_pos = {a.candidate_id: (a.row, a.col) for a in assigns if a.absent}
    absent_rows: list[dict] = []
    for cid in sorted(absent_ids):
        c = by_id[cid]
        pos = held_pos.get(cid)
        absent_rows.append({
            "id": c["id"], "name": c["name"], "ticket_no": c["ticket_no"],
            "paper_id": c["paper_id"], "held": pos is not None,
            "row": pos[0] if pos else None, "col": pos[1] if pos else None,
        })

    viols = find_violations(rows, cols, min_dist, assigns)
    result = plan_to_dict(assigns, unplaced, viols, rows, cols, absent_rows, reserve_absent)

    stats = result["stats"]
    # 核对恒等式：名册人数 = 已到 + 缺考 + 未排
    if stats["roster_total"] != len(candidates):
        raise AssertionError("核对失败：已到+缺考+未排 ≠ 名册人数")
    # 缺考绝不能再被记入未排
    if {u["id"] for u in unplaced} & absent_ids:
        raise AssertionError("核对失败：缺考被记入未排")
    if reserve_absent:
        # 占格保留：每名缺考都须占格
        if stats["absent_held"] != stats["absent"]:
            raise AssertionError("核对失败：占格策略下缺考未全部占格")
    else:
        # 释放策略：缺考不占格
        if stats["absent_held"] != 0:
            raise AssertionError("核对失败：释放策略下缺考仍占格")
    return result
