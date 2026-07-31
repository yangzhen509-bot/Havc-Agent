"""座舱热动力学与闭环仿真步进。"""
from havc_agent.engine import Engine
from havc_agent.memory.store import MemoryStore
from havc_agent.schemas import CabinContext, OccupantState, SceneInput
from havc_agent.sim import ClosedLoopSim, ZoneActuator, step_cabin_temperature


def test_hot_cabin_cools_with_ac():
    """暴晒热舱 + 低温大风量 → 舱温应下降。"""
    r = step_cabin_temperature(
        cabin_temp=38.0,
        ambient_temp=32.0,
        sun_wm2=800.0,
        zones=[ZoneActuator(temp_set=18.5, fan_level=7)],
        dt_s=10.0,
    )
    assert r.cabin_temp < 38.0
    assert r.q_hvac < 0  # 制冷放热为负（从舱内抽热）
    assert r.dT < 0


def test_no_ac_heats_with_sun():
    """无有效制冷、强日照时舱温不应下降。"""
    r = step_cabin_temperature(
        cabin_temp=30.0,
        ambient_temp=32.0,
        sun_wm2=1000.0,
        zones=[ZoneActuator(temp_set=30.0, fan_level=1)],
        dt_s=10.0,
    )
    assert r.q_solar > 0
    assert r.cabin_temp >= 30.0


def test_closed_loop_cabin_drops(tmp_path):
    """闭环若干步后舱温应相对初始下降（夏季暴晒起步）。"""
    scene = SceneInput(
        cabin=CabinContext(
            ambient_temp=32.0,
            cabin_temp=38.0,
            season="summer",
            humidity=55,
            sun_driver_wm2=900,
            sun_passenger_wm2=700,
            soc=70,
        ),
        occupants=[
            OccupantState(seat_id="driver", user_id="alice", clothing="light"),
            OccupantState(seat_id="front_passenger", user_id="bob", clothing="light"),
        ],
    )
    eng = Engine(store=MemoryStore(tmp_path / "m.json"))
    sim = ClosedLoopSim(engine=eng, scene=scene, dt_s=10.0, max_steps=30)
    sim.start(initial_infer=True)
    t0 = float(sim.scene.cabin.cabin_temp)
    for _ in range(8):
        if not sim.running:
            break
        sim.tick()
    t1 = float(sim.scene.cabin.cabin_temp)
    assert t1 < t0
    assert len(sim.history) >= 2
    assert sim.last_thermal is not None


def test_comfort_convergence_or_progress(tmp_path):
    """要么收敛到舒适，要么在限步内持续降温逼近。"""
    scene = SceneInput(
        cabin=CabinContext(
            ambient_temp=28.0,
            cabin_temp=34.0,
            season="summer",
            humidity=50,
            sun_driver_wm2=200,
            sun_passenger_wm2=150,
            soc=80,
        ),
        occupants=[
            OccupantState(seat_id="driver", user_id="alice", clothing="light"),
        ],
    )
    eng = Engine(store=MemoryStore(tmp_path / "m.json"))
    sim = ClosedLoopSim(
        engine=eng, scene=scene, dt_s=10.0, max_steps=40, pmv_abs_limit=0.5, ppd_limit=10.0
    )
    sim.start(initial_infer=True)
    temps = [float(sim.scene.cabin.cabin_temp)]
    while sim.running:
        sim.tick()
        temps.append(float(sim.scene.cabin.cabin_temp))
    assert sim.converged or temps[-1] < temps[0]
    # 历史时间轴按 10s 递增
    if len(sim.history) >= 3:
        assert sim.history[1].t_s == 10.0
        assert sim.history[2].t_s == 20.0
