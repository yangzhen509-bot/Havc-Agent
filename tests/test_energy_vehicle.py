"""能耗治理 Agent 与车辆总线测试。"""
from __future__ import annotations

from havc_agent.config import ENERGY
from havc_agent.energy import EnergyGuardAgent
from havc_agent.engine import Engine
from havc_agent.schemas import CabinContext, OccupantState, SceneInput, ZoneSetting
from havc_agent.vehicle import MockVehicleBus, merge_snapshot_into_cabin


def _cabin(soc: float, **kw) -> CabinContext:
    base = dict(
        ambient_temp=35.0,
        cabin_temp=38.0,
        humidity=55.0,
        season="summer",
        weather="sunny",
        soc=soc,
        speed=40.0,
        sun_driver_wm2=900.0,
        sun_passenger_wm2=800.0,
    )
    base.update(kw)
    return CabinContext(**base)


def test_energy_levels():
    agent = EnergyGuardAgent()
    assert agent.assess(_cabin(80)).level == "normal"
    assert agent.assess(_cabin(ENERGY.soc_save)).level == "save"
    assert agent.assess(_cabin(ENERGY.soc_critical)).level == "critical"


def test_energy_caps_fan_but_respects_max_defrost():
    agent = EnergyGuardAgent()
    cabin = _cabin(10.0, max_defrost=True)
    setting = ZoneSetting(
        seat_id="driver", fan_level=7, temp_set=20.0, air_mode="face", reasoning="t"
    )
    out, notes = agent.apply(setting, cabin)
    assert out.fan_level == 7
    assert any("除霜" in n for n in notes)


def test_energy_soft_cap_when_low_soc():
    agent = EnergyGuardAgent()
    cabin = _cabin(10.0)
    setting = ZoneSetting(
        seat_id="driver", fan_level=7, temp_set=18.0, air_mode="face", reasoning="t"
    )
    out, notes = agent.apply(setting, cabin)
    assert out.fan_level <= ENERGY.fan_cap_critical
    assert notes


def test_mock_vehicle_bus_merge():
    cabin = _cabin(50.0)
    bus = MockVehicleBus(cabin)
    snap = bus.read()
    assert snap.soc == 50.0
    snap.soc = 12.0
    merged = merge_snapshot_into_cabin(cabin, snap)
    assert merged.soc == 12.0


def test_engine_infer_with_energy():
    scene = SceneInput(
        cabin=_cabin(12.0),
        occupants=[
            OccupantState(seat_id="driver", user_id="u1", present=True),
        ],
    )
    eng = Engine()
    result = eng.infer(scene, now=1_700_000_000.0)
    assert result.energy is not None
    assert result.energy.level == "critical"
    assert "driver" in result.settings
