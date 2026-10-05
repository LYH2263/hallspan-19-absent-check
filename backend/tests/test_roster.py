"""缺考核对册 / 当前方案指针 / 08 缺考策略口径的不变量测试。"""
from sqlalchemy import func, select

from app.models.models import SeatPlan
from app.services.seed import seed_if_empty


def plan_count(db_factory, hall_id):
    db = db_factory()
    n = db.scalar(select(func.count()).select_from(SeatPlan).where(SeatPlan.hall_id == hall_id))
    db.close()
    return n


# ---- 未排座前：任何只读页都不得为凑数临时生成方案 ----

def test_no_plan_readonly_pages_fail_and_create_nothing(client, db_factory, make_hall):
    hid = make_hall()
    assert plan_count(db_factory, hid) == 0
    for path in (f"/api/seating/roster?hall_id={hid}",
                 f"/api/seating/stats?hall_id={hid}",
                 f"/api/seating/latest?hall_id={hid}",
                 f"/api/seating/violations?hall_id={hid}"):
        r = client.get(path)
        assert r.status_code in (404, 409), path
    # 打开核对册（及其它只读页）后，方案条数仍为 0
    assert plan_count(db_factory, hid) == 0


# ---- 同一张当前有效方案：核对册 / 排座图 / 违规 / 统计指针与数量一致 ----

def test_roster_matches_stats_violations_and_map_same_plan(client, db_factory, make_hall):
    hid = make_hall()
    run = client.post(f"/api/seating/run?hall_id={hid}").json()
    pid = run["id"]

    roster = client.get(f"/api/seating/roster?hall_id={hid}").json()
    stats = client.get(f"/api/seating/stats?hall_id={hid}").json()
    viols = client.get(f"/api/seating/violations?hall_id={hid}").json()
    latest = client.get(f"/api/seating/latest?hall_id={hid}").json()

    assert roster["plan_id"] == stats["plan_id"] == viols["plan_id"] == latest["id"] == pid
    sm = roster["summary"]
    assert sm["present"] == stats["seated"] == len(latest["assignments"])
    assert sm["absent"] == stats["absent"] == 0           # 未配缺考 → 缺考为 0
    assert sm["unplaced"] == stats["unplaced"]
    assert sm["violations"] == stats["violations"] == len(viols["violations"])
    assert sm["roster_total"] == 12
    assert sm["present"] + sm["absent"] + sm["unplaced"] == sm["roster_total"]


def test_opening_roster_never_adds_plans(client, db_factory, make_hall):
    hid = make_hall()
    client.post(f"/api/seating/run?hall_id={hid}")
    assert plan_count(db_factory, hid) == 1
    for _ in range(3):
        client.get(f"/api/seating/roster?hall_id={hid}")
        client.get(f"/api/seating/stats?hall_id={hid}")
    assert plan_count(db_factory, hid) == 1


# ---- 作废切换后核对册必须跟随新指针 ----

def test_void_and_switch_pointer(client, db_factory, make_hall):
    hid = make_hall()
    p1 = client.post(f"/api/seating/run?hall_id={hid}").json()["id"]
    p2 = client.post(f"/api/seating/run?hall_id={hid}").json()["id"]
    assert client.get(f"/api/seating/roster?hall_id={hid}").json()["plan_id"] == p2

    # 作废当前方案：指针落空，核对册失败而不是偷偷重排
    client.post(f"/api/seating/plans/{p2}/void")
    r = client.get(f"/api/seating/roster?hall_id={hid}")
    assert r.status_code == 409
    assert plan_count(db_factory, hid) == 2  # 没有新增方案凑数

    # 切换到仍有效的旧方案：核对册跟随新指针
    client.post(f"/api/seating/plans/{p1}/activate")
    roster = client.get(f"/api/seating/roster?hall_id={hid}").json()
    assert roster["plan_id"] == p1


def test_cannot_activate_voided_plan(client, db_factory, make_hall):
    hid = make_hall()
    p1 = client.post(f"/api/seating/run?hall_id={hid}").json()["id"]
    client.post(f"/api/seating/plans/{p1}/void")
    r = client.post(f"/api/seating/plans/{p1}/activate")
    assert r.status_code == 409


# ---- 08 策略口径：占格保留 vs 释放 ----

def _set_absent(client, hid, db_factory, k):
    db = db_factory()
    from app.models.models import Candidate
    from sqlalchemy import select
    cid = db.scalars(select(Candidate.id).where(Candidate.hall_id == hid)
                     .order_by(Candidate.id)).all()[k]
    db.close()
    client.post("/api/absences", json={"hall_id": hid, "candidate_ids": [cid]})
    return cid


def test_reserve_policy_absent_holds_seat_and_not_unplaced(client, db_factory, make_hall):
    # 1x3 共 3 格、min_dist=1；4 名考生、第 0 名缺考、占格保留
    hid = make_hall(rows=1, cols=3, min_manhattan=1, reserve=True, n=4)
    cid = _set_absent(client, hid, db_factory, 0)
    client.post(f"/api/seating/run?hall_id={hid}")

    roster = client.get(f"/api/seating/roster?hall_id={hid}").json()
    stats = client.get(f"/api/seating/stats?hall_id={hid}").json()
    sm = roster["summary"]

    assert sm["reserve_absent_seat"] is True
    assert sm["absent"] == 1 and sm["absent_held"] == 1
    # 缺考计入占格，挤占一个座位 → 一名到考未排；缺考本身不得入未排
    assert sm["occupied"] == sm["capacity"] == 3
    assert sm["unplaced"] == 1
    assert sm["present"] == 2
    absent_row = next(r for r in roster["rows"] if r["candidate_id"] == cid)
    assert absent_row["status"] == "absent" and absent_row["held"] is True
    unplaced_ids = {r["candidate_id"] for r in roster["rows"] if r["status"] == "unplaced"}
    assert cid not in unplaced_ids
    # 与统计同数
    assert (stats["absent"], stats["absent_held"], stats["unplaced"],
            stats["occupied"]) == (1, 1, 1, 3)


def test_release_policy_absent_does_not_hold_nor_unplaced(client, db_factory, make_hall):
    hid = make_hall(rows=1, cols=3, min_manhattan=1, reserve=False, n=4)
    cid = _set_absent(client, hid, db_factory, 0)
    client.post(f"/api/seating/run?hall_id={hid}")

    roster = client.get(f"/api/seating/roster?hall_id={hid}").json()
    stats = client.get(f"/api/seating/stats?hall_id={hid}").json()
    sm = roster["summary"]

    assert sm["reserve_absent_seat"] is False
    assert sm["absent"] == 1 and sm["absent_held"] == 0
    # 释放：缺考不占格，3 个到考全部落座，不计未排
    assert sm["present"] == 3 and sm["unplaced"] == 0
    absent_row = next(r for r in roster["rows"] if r["candidate_id"] == cid)
    assert absent_row["status"] == "absent" and absent_row["held"] is False
    assert (stats["absent"], stats["absent_held"], stats["unplaced"],
            stats["occupied"]) == (1, 0, 0, 3)


# ---- 种子排完即与统计同数，且打开核对册不增加条数 ----

def test_seed_then_roster_equals_stats_and_no_extra_plans(client, db_factory):
    db = db_factory()
    seed_if_empty(db)
    db.close()

    roster = client.get("/api/seating/roster?hall_id=1").json()
    stats = client.get("/api/seating/stats?hall_id=1").json()
    sm = roster["summary"]
    assert sm["absent"] == 0
    assert (sm["present"], sm["unplaced"], sm["violations"]) == \
           (stats["seated"], stats["unplaced"], stats["violations"])
    assert roster["plan_id"] == stats["plan_id"]

    n_before = plan_count(db_factory, 1)
    client.get("/api/seating/roster?hall_id=1")
    assert plan_count(db_factory, 1) == n_before
