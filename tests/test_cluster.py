"""集群编排层单测。"""
from __future__ import annotations

from havc_agent.cluster import (
    ActionFeedback,
    FeedbackCode,
    IngestCoalescer,
    PendingStore,
    build_default_cluster,
)
from havc_agent.engine import Engine
from havc_agent.schemas import CabinContext, OccupantState, SceneInput


def test_cluster_registry_loads_yaml():
    reg = build_default_cluster()
    ids = {s.id for s in reg.enabled_agents()}
    assert "comfort" in ids
    assert "defog" in ids
    assert reg.is_enabled("energy")


def test_pending_confirm_reject():
    store = PendingStore()
    t = store.create("v1", "driver", {"temp": 18}, reason="test")
    assert store.get("v1").ticket_id == t.ticket_id
    got = store.resolve("v1", "confirm")
    assert got is not None
    assert store.get("v1") is None


def test_ingest_coalesce():
    c = IngestCoalescer(lease_seconds=60)
    ok1, _ = c.should_process("k", "same", now=100.0)
    ok2, reason = c.should_process("k", "same", now=101.0)
    assert ok1 is True
    assert ok2 is False
    assert "coalesced" in reason


def test_feedback_dict():
    fb = ActionFeedback.success("ok", request_id="abc", agent_id="engine")
    assert fb.to_dict()["code"] == "OK"


def test_engine_infer_has_request_id_and_cluster():
    scene = SceneInput(
        cabin=CabinContext(
            ambient_temp=30, cabin_temp=35, humidity=50, season="summer",
            soc=80, sun_driver_wm2=500, sun_passenger_wm2=400,
        ),
        occupants=[OccupantState(seat_id="driver", user_id="u1")],
    )
    eng = Engine()
    result = eng.infer(scene, now=1_700_000_000.0, force=True)
    assert result.request_id
    assert result.cluster_summary
    assert result.feedback is not None
    assert result.feedback.code in (FeedbackCode.OK, FeedbackCode.PENDING)
