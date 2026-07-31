"""座舱集总热动力学：吸热/放热 + 空调送风，闭环仿真一步。

简化物理（集总热容）:
  C · dT/dt = Q_amb + Q_solar + Q_vent + Q_hvac

- Q_amb   : 车身与环境对流/导热 (UA · (T_amb - T_cabin))
- Q_solar : 日照得热
- Q_vent  : 开窗/行驶通风拉回环境温度
- Q_hvac  : 空调送风 (ṁ · cp · (T_supply - T_cabin))，风量越大换热越强
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass(frozen=True)
class CabinThermalParams:
    """座舱热参数（可标定）。

    标定目标（演示友好、仍物理自洽）:
    - 夏季暴晒 38℃ 起步、外温 32℃、日照约 800 W/m²、大风量低温设定
    - 约 3–5 分钟舱温可降到舒适区附近（~23℃），而非卡在 27℃+ 热平衡
    """

    # 有效热容:空气+内饰等效 (J/K) — 略降以加快瞬态可见性
    capacity_j_per_k: float = 28_000.0
    # 车身综合传热系数 (W/K)
    ua_body_w_per_k: float = 50.0
    # 日照得热系数:平均辐照(W/m²) → 舱内功率(W)
    # 约按有效透光面积×透过率，800 W/m² → ~560 W（原先 1.8 导致 ~1440 W，空调打不穿）
    solar_gain_w_per_wm2: float = 0.70
    # 每档风量对应送风质量流量 (kg/s) — 提高以贴近车载空调换热能力
    mass_flow_per_fan: float = 0.045
    # 空气比热 (J/(kg·K))
    cp_air: float = 1005.0
    # 开窗通风基准 (W/K)，按开窗百分比与车速放大
    ua_vent_base: float = 25.0
    # 车速对通风增益 (每 km/h)
    vent_speed_gain: float = 0.08
    # 单步限幅，避免数值炸裂
    max_abs_dT: float = 5.0


@dataclass
class ZoneActuator:
    """单个温区空调执行量。"""

    temp_set: float
    fan_level: int
    weight: float = 1.0  # 多温区合成权重


@dataclass
class ThermalStepResult:
    cabin_temp: float
    dT: float
    q_amb: float
    q_solar: float
    q_vent: float
    q_hvac: float
    t_supply: float
    mass_flow: float
    dt_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "cabin_temp": self.cabin_temp,
            "dT": self.dT,
            "q_amb_w": round(self.q_amb, 1),
            "q_solar_w": round(self.q_solar, 1),
            "q_vent_w": round(self.q_vent, 1),
            "q_hvac_w": round(self.q_hvac, 1),
            "t_supply": self.t_supply,
            "mass_flow": round(self.mass_flow, 3),
            "dt_s": self.dt_s,
        }


def _blend_supply(
    zones: Sequence[ZoneActuator],
    params: Optional[CabinThermalParams] = None,
) -> tuple[float, float]:
    """多温区合成等效送风温度与质量流量。"""
    p = params or CabinThermalParams()
    if not zones:
        return 24.0, 0.05
    tw = sum(max(0.1, z.weight) for z in zones)
    t_sup = sum(z.temp_set * max(0.1, z.weight) for z in zones) / tw
    m_dot = sum(
        max(1, min(7, int(z.fan_level))) * p.mass_flow_per_fan * max(0.1, z.weight)
        for z in zones
    )
    m_dot = max(0.04, min(m_dot, 0.55))
    return float(t_sup), float(m_dot)


def step_cabin_temperature(
    cabin_temp: float,
    ambient_temp: float,
    sun_wm2: float,
    speed_kmh: float = 0.0,
    window_open_pct: float = 0.0,
    zones: Optional[Sequence[ZoneActuator]] = None,
    dt_s: float = 10.0,
    params: Optional[CabinThermalParams] = None,
) -> ThermalStepResult:
    """推进 dt_s 秒，返回新舱温与热流诊断。"""
    p = params or CabinThermalParams()
    zones = list(zones or [])
    t_sup, m_dot = _blend_supply(zones, p)

    q_amb = p.ua_body_w_per_k * (ambient_temp - cabin_temp)
    q_solar = p.solar_gain_w_per_wm2 * max(0.0, sun_wm2)
    ua_vent = p.ua_vent_base * (max(0.0, window_open_pct) / 100.0) * (
        1.0 + p.vent_speed_gain * max(0.0, speed_kmh)
    )
    q_vent = ua_vent * (ambient_temp - cabin_temp)
    q_hvac = m_dot * p.cp_air * (t_sup - cabin_temp)

    q_net = q_amb + q_solar + q_vent + q_hvac
    dT = (q_net * dt_s) / p.capacity_j_per_k
    dT = max(-p.max_abs_dT, min(p.max_abs_dT, dT))
    new_t = round(cabin_temp + dT, 2)
    # 物理夹紧
    new_t = max(-20.0, min(80.0, new_t))
    return ThermalStepResult(
        cabin_temp=new_t,
        dT=round(dT, 3),
        q_amb=q_amb,
        q_solar=q_solar,
        q_vent=q_vent,
        q_hvac=q_hvac,
        t_supply=round(t_sup, 2),
        mass_flow=m_dot,
        dt_s=dt_s,
    )
