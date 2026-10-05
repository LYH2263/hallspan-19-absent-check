"""缺考核对册（只读）验收测试。

覆盖：
- 已到/缺考/未排 与排座图(effective)、违规、统计指向同一张当前有效方案；
- 打开核对册/统计/违规不生成新方案（无方案时 404，条数不因打开而增加）；
- 作废切换后核对册跟随新指针；
- retain：缺考计入占格、不再记入未排；release：缺考不占格；
- 未配缺考时册上缺考为 0；种子排完后核对册与统计同数。
"""
import json

from app.models.models import Absentee, SeatPlan
from tests.conftest import make_hall


def _run(client):
    return client.post("/api/seating/run?hall_id=1").json()


def _reg(client):
    return client.get("/api/seating/register?hall_id=1").json()


def _stats(client):
    return client.get("/api/seating/stats?hall_id=1").json()


def _viol(client):
    return client.get("/api/seating/violations?hall_id=1").json()


def _eff(client):
    return client.get("/api/seating/effective?hall_id=1").json()


def _plan_count(client):
    return len(client.get("/api/seating/plans?hall_id=1").json())


def test_no_plan_readonly_views_404_and_never_generate(db, client):
    make_hall(db)
    assert client.get("/api/seating/register?hall_id=1").status_code == 404
    assert client.get("/api/seating/stats?hall_id=1").status_code == 404
    assert client.get("/api/seating/violations?hall_id=1").status_code == 404
    assert client.get("/api/seating/effective?hall_id=1").status_code == 404
    # 反复打开只读页不得为凑数生成任何方案。
    for _ in range(3):
        client.get("/api/seating/register?hall_id=1")
    assert _plan_count(client) == 0


def test_all_views_point_to_same_effective_plan(db, client):
    make_hall(db)
    p1 = _run(client)["id"]
    for endpoint in (_reg, _stats, _viol, _eff):
        body = endpoint(client)
        assert body.get("plan_id", body.get("id")) == p1
    # 再排一张，新方案成为当前有效，四个视图一起跟新。
    p2 = _run(client)["id"]
    for endpoint in (_reg, _stats, _viol, _eff):
        body = endpoint(client)
        assert body.get("plan_id", body.get("id")) == p2


def test_opening_register_does_not_add_plans(db, client):
    make_hall(db)
    _run(client)
    assert _plan_count(client) == 1
    for _ in range(5):
        _reg(client)
        _stats(client)
    assert _plan_count(client) == 1


def test_register_equals_stats_after_run(db, client):
    make_hall(db)
    _run(client)
    reg, stats = _reg(client), _stats(client)
    assert reg["counts"]["arrived"] == stats["seated"]
    assert reg["counts"]["absent"] == stats["absent"] == 0  # 未配缺考
    assert reg["counts"]["unseated"] == stats["unplaced"]
    assert reg["counts"]["occupied"] == stats["occupied"]
    assert reg["plan_id"] == stats["plan_id"]


def test_void_switches_register_to_new_pointer(db, client):
    make_hall(db)
    p1 = _run(client)
    # 在 p1 之后标记缺考并重排得到 p2。
    db.add(Absentee(candidate_id=2, hall_id=1))
    db.commit()
    p2 = _run(client)
    assert _reg(client)["plan_id"] == p2["id"]
    n = _plan_count(client)

    client.post(f"/api/seating/{p2['id']}/void")

    # 作废后核对册/统计/违规/排座图全部回落到 p1。
    assert _reg(client)["plan_id"] == p1["id"]
    assert _stats(client)["plan_id"] == p1["id"]
    assert _viol(client)["plan_id"] == p1["id"]
    assert _eff(client)["id"] == p1["id"]
    # 打开核对册不增加条数。
    _reg(client); _reg(client)
    assert _plan_count(client) == n
    # 且 p1（标记缺考前所排）册上缺考为 0。
    assert _reg(client)["counts"]["absent"] == 0


def test_retain_strategy_counts_absent_as_occupied_not_unplaced(db, client):
    make_hall(db, strategy="retain")
    db.add_all([Absentee(candidate_id=2, hall_id=1), Absentee(candidate_id=5, hall_id=1)])
    db.commit()
    _run(client)
    reg, stats = _reg(client), _stats(client)
    assert stats["absent"] == 2 and reg["counts"]["absent"] == 2
    assert stats["occupied"] == stats["seated"] + stats["absent"]
    assert stats["unplaced"] == 0 and reg["counts"]["unseated"] == 0
    # 缺考者在保留策略下有占格座次。
    assert {s["candidate_id"] for s in reg["absent_seats"]} == {2, 5}
    absent_ids_in_unplaced = {u["id"] for u in reg["unseated"]}
    assert not ({2, 5} & absent_ids_in_unplaced)


def test_release_strategy_absent_does_not_occupy(db, client):
    make_hall(db, strategy="release")
    db.add_all([Absentee(candidate_id=2, hall_id=1), Absentee(candidate_id=5, hall_id=1)])
    db.commit()
    _run(client)
    reg, stats = _reg(client), _stats(client)
    assert stats["absent"] == 2
    assert stats["occupied"] == stats["seated"]      # 缺考不占格
    assert reg["counts"]["occupied"] == reg["counts"]["arrived"]
    assert reg["absent_seats"] == []


def test_strategy_switch_then_rerun_changes_occupancy(db, client):
    make_hall(db, strategy="retain")
    db.add(Absentee(candidate_id=2, hall_id=1))
    db.commit()
    pr = _run(client)
    assert pr["stats"]["occupied"] == pr["stats"]["seated"] + 1

    client.patch("/api/halls/1/strategy", json={"absent_strategy": "release"})
    pl = _run(client)
    assert pl["stats"]["occupied"] == pl["stats"]["seated"]
    # 当前有效指针是最新的 release 方案，核对册口径与之完全一致。
    reg = _reg(client)
    assert reg["plan_id"] == pl["id"]
    assert reg["counts"]["occupied"] == pl["stats"]["occupied"]


def test_reinstate_newer_plan_becomes_effective_again(db, client):
    make_hall(db)
    p1 = _run(client)["id"]
    p2 = _run(client)["id"]
    client.post(f"/api/seating/{p2}/void")
    assert _eff(client)["id"] == p1
    client.post(f"/api/seating/{p2}/reinstate")
    assert _eff(client)["id"] == p2
    assert _reg(client)["plan_id"] == p2


def test_register_fails_422_on_inconsistent_snapshot(db, client):
    """篡改/损坏导致计数与明细对不齐时，核对册必须失败而非凑数输出。"""
    make_hall(db)
    good = _run(client)
    corrupt = dict(good)
    corrupt["stats"] = dict(good["stats"])
    corrupt["stats"]["seated"] = 99  # 与明细人数对不上
    db.add(SeatPlan(hall_id=1, result_json=json.dumps(corrupt, ensure_ascii=False)))
    db.commit()
    resp = client.get("/api/seating/register?hall_id=1")
    assert resp.status_code == 422
    assert resp.json()["code"] == "plan_reconcile_failed"
    # 失败不得回退去生成新方案凑数。
    assert len(client.get("/api/seating/plans").json()) == 2
