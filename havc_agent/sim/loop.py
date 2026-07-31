"""闭环热管理仿真：舱温动力学 ↔ Agent 重推理，直至舒适收敛。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..engine import Engine, InferenceResult
from ..schemas import SceneInput
from .cabin_thermal import (
    CabinThermalParams,
    ThermalStepResult,
    ZoneActuator,
    step_cabin_temperature,
)


@dataclass
class SimSnapshot:
    """一个仿真时刻的快照。"""

    t_s: float
    cabin_temp: float
    settings: dict[str, dict]
    pmv: dict[str, float]
    ppd: dict[str, float]
    thermal: dict[str, Any]
    comfortable: bool
    request_id: str = ""


@dataclass
class ClosedLoopSim:
    """闭环仿真状态机。"""

    engine: Engine
    scene: SceneInput
    dt_s: float = 10.0
    pmv_abs_limit: float = 0.5
    ppd_limit: float = 10.0
    max_steps: int = 60
    params: CabinThermalParams = field(default_factory=CabinThermalParams)

    t_s: float = 0.0
    step_i: int = 0
    running: bool = False
    converged: bool = False
    history: list[SimSnapshot] = field(default_factory=list)
    last_result: Optional[InferenceResult] = None
    last_thermal: Optional[ThermalStepResult] = None

    def _sun_avg(self) -> float:
        c = self.scene.cabin
        return 0.5 * (c.sun_driver_wm2 + c.sun_passenger_wm2)

    def _window_pct(self) -> float:
        return float(self.scene.cabin.max_window_open())

    def _with_cabin_temp(self, temp: float) -> SceneInput:
        data = self.scene.cabin.model_dump()
        data["cabin_temp"] = float(temp)
        from ..schemas import CabinContext

        return SceneInput(
            cabin=CabinContext.model_validate(data),
            occupants=list(self.scene.occupants),
        )

    def _zones_from_result(self, result: InferenceResult) -> list[ZoneActuator]:
        return [
            ZoneActuator(temp_set=s.temp_set, fan_level=s.fan_level, weight=1.0)
            for s in result.settings.values()
        ]

    def _comfort_maps(self, result: InferenceResult) -> tuple[dict, dict]:
        pmv, ppd = {}, {}
        for seat, tr in result.traces.items():
            m = tr.comfort_metrics
            if m:
                pmv[seat] = float(m.pmv)
                ppd[seat] = float(m.ppd)
        return pmv, ppd

    def is_comfortable(self, result: InferenceResult) -> bool:
        if not result.traces:
            return False
        for tr in result.traces.values():
            m = tr.comfort_metrics
            if m is None:
                return False
            if abs(m.pmv) > self.pmv_abs_limit or m.ppd > self.ppd_limit:
                return False
        return True

    def start(self, initial_infer: bool = True) -> InferenceResult:
        """启动/重置仿真。"""
        self.t_s = 0.0
        self.step_i = 0
        self.running = True
        self.converged = False
        self.history.clear()
        cab_t = self.scene.cabin.cabin_temp
        if cab_t is None:
            from ..tools.thermal_comfort import estimate_cabin_temp

            cab_t = estimate_cabin_temp(
                self.scene.cabin.ambient_temp,
                self._sun_avg(),
                self._window_pct(),
                self.scene.cabin.speed,
            )
            self.scene = self._with_cabin_temp(cab_t)
        if initial_infer or self.last_result is None:
            self.last_result = self.engine.infer(
                self.scene, capture_chain=True, force=True
            )
        pmv, ppd = self._comfort_maps(self.last_result)
        self.converged = self.is_comfortable(self.last_result)
        self.history.append(
            SimSnapshot(
                t_s=self.t_s,
                cabin_temp=float(self.scene.cabin.cabin_temp),
                settings={
                    k: {
                        "temp_set": v.temp_set,
                        "fan_level": v.fan_level,
                        "air_mode": v.air_mode,
                    }
                    for k, v in self.last_result.settings.items()
                },
                pmv=pmv,
                ppd=ppd,
                thermal={},
                comfortable=self.converged,
                request_id=self.last_result.request_id,
            )
        )
        if self.converged:
            self.running = False
        return self.last_result

    def tick(self) -> InferenceResult:
        """推进一个仿真步:热模型 → 更新舱温 → Agent 重推理。"""
        if not self.running or self.converged or self.last_result is None:
            return self.last_result  # type: ignore[return-value]
        if self.step_i >= self.max_steps:
            self.running = False
            return self.last_result

        cabin_now = float(self.scene.cabin.cabin_temp)
        thermal = step_cabin_temperature(
            cabin_temp=cabin_now,
            ambient_temp=self.scene.cabin.ambient_temp,
            sun_wm2=self._sun_avg(),
            speed_kmh=self.scene.cabin.speed,
            window_open_pct=self._window_pct(),
            zones=self._zones_from_result(self.last_result),
            dt_s=self.dt_s,
            params=self.params,
        )
        self.last_thermal = thermal
        self.t_s = round(self.t_s + self.dt_s, 1)
        self.step_i += 1
        self.scene = self._with_cabin_temp(thermal.cabin_temp)
        self.last_result = self.engine.infer(
            self.scene, capture_chain=True, force=True
        )
        pmv, ppd = self._comfort_maps(self.last_result)
        self.converged = self.is_comfortable(self.last_result)
        self.history.append(
            SimSnapshot(
                t_s=self.t_s,
                cabin_temp=thermal.cabin_temp,
                settings={
                    k: {
                        "temp_set": v.temp_set,
                        "fan_level": v.fan_level,
                        "air_mode": v.air_mode,
                    }
                    for k, v in self.last_result.settings.items()
                },
                pmv=pmv,
                ppd=ppd,
                thermal=thermal.to_dict(),
                comfortable=self.converged,
                request_id=self.last_result.request_id,
            )
        )
        if self.converged or self.step_i >= self.max_steps:
            self.running = False
        return self.last_result

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "converged": self.converged,
            "t_s": self.t_s,
            "step_i": self.step_i,
            "max_steps": self.max_steps,
            "dt_s": self.dt_s,
            "cabin_temp": self.scene.cabin.cabin_temp,
            "last_dT": None if not self.last_thermal else self.last_thermal.dT,
            "q_hvac_w": None if not self.last_thermal else round(self.last_thermal.q_hvac, 1),
            "q_solar_w": None if not self.last_thermal else round(self.last_thermal.q_solar, 1),
            "q_amb_w": None if not self.last_thermal else round(self.last_thermal.q_amb, 1),
        }
