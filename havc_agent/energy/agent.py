"""能耗治理 Agent:低 SOC 时软约束风量/设定温差。

设计原则:
- 不替代舒适 Agent / 除雾 Agent,只做「合成前的节能软钳制」;
- 除雾 strong / 最大除霜时不降风量(安全优先);
- 规则与阈值均可改,见 config.EnergyThresholds。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import ENERGY, FAN_MIN, TEMP_MAX, TEMP_MIN, TEMP_STEP
from ..schemas import CabinContext, DefogDecision, ZoneSetting


@dataclass
class EnergyDecision:
    """能耗治理结论。"""

    level: str = "normal"  # normal / save / critical
    fan_cap: Optional[int] = None
    temp_bias: float = 0.0  # 制冷时上抬 / 制热时下调的偏置(节能)
    recirculation: str = "auto"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "fan_cap": self.fan_cap,
            "temp_bias": self.temp_bias,
            "recirculation": self.recirculation,
            "notes": list(self.notes),
        }


class EnergyGuardAgent:
    """车厢级能耗 Agent:按 SOC / 环境负荷给出节能策略。"""

    def assess(self, cabin: CabinContext) -> EnergyDecision:
        soc = float(cabin.soc)
        notes: list[str] = []
        if soc <= ENERGY.soc_critical:
            level = "critical"
            fan_cap = ENERGY.fan_cap_critical
            bias = ENERGY.temp_bias_critical
            notes.append(f"SOC={soc:.0f}%≤{ENERGY.soc_critical}% → 强节能")
        elif soc <= ENERGY.soc_save:
            level = "save"
            fan_cap = ENERGY.fan_cap_save
            bias = ENERGY.temp_bias_save
            notes.append(f"SOC={soc:.0f}%≤{ENERGY.soc_save}% → 温和节能")
        else:
            level = "normal"
            fan_cap = None
            bias = 0.0
            notes.append(f"SOC={soc:.0f}% 充足,不限制舒适策略")

        # 雨雪/雾风险场景优先内循环建议,但仍服从除雾安全层
        if cabin.weather in ("rain", "snow") or cabin.humidity >= 80:
            recirculation = "fresh_bias"
            notes.append("高湿/雨雪:建议偏外循环配合除雾")
        elif level != "normal":
            recirculation = "recirc"
            notes.append("低电量:建议内循环降低负荷")
        else:
            recirculation = "auto"

        return EnergyDecision(
            level=level,
            fan_cap=fan_cap,
            temp_bias=bias,
            recirculation=recirculation,
            notes=notes,
        )

    def apply(
        self,
        setting: ZoneSetting,
        cabin: CabinContext,
        defog: Optional[DefogDecision] = None,
        decision: Optional[EnergyDecision] = None,
    ) -> tuple[ZoneSetting, list[str]]:
        """把能耗决策应用到座位设定;安全除雾优先于节能。"""
        decision = decision or self.assess(cabin)
        adj: list[str] = []
        if decision.level == "normal":
            return setting, adj

        # 安全优先:强除雾 / 最大除霜不砍风量
        if cabin.max_defrost or (defog is not None and defog.level == "strong"):
            adj.append("能耗 Agent:除霜安全优先,跳过风量封顶")
            return setting, adj

        fan = setting.fan_level
        temp = setting.temp_set
        if decision.fan_cap is not None and fan > decision.fan_cap:
            adj.append(
                f"能耗 Agent({decision.level}):风量 {fan}→{decision.fan_cap} 封顶"
            )
            fan = max(FAN_MIN, decision.fan_cap)

        # 制冷场景(车内偏热):设定上抬以省电;制热场景:设定下调
        cabin_t = cabin.cabin_temp if cabin.cabin_temp is not None else cabin.ambient_temp
        if decision.temp_bias:
            if cabin_t >= temp:  # 正在制冷或维持偏低设定
                new_t = temp + decision.temp_bias
                adj.append(
                    f"能耗 Agent:制冷设定 {temp}℃→{new_t}℃(偏置+{decision.temp_bias})"
                )
                temp = new_t
            else:
                new_t = temp - decision.temp_bias
                adj.append(
                    f"能耗 Agent:制热设定 {temp}℃→{new_t}℃(偏置-{decision.temp_bias})"
                )
                temp = new_t
            temp = round(max(TEMP_MIN, min(temp, TEMP_MAX)) / TEMP_STEP) * TEMP_STEP

        for n in decision.notes:
            if n not in adj:
                adj.append(n)

        new_setting = ZoneSetting(
            seat_id=setting.seat_id,
            fan_level=fan,
            temp_set=temp,
            air_mode=setting.air_mode,
            reasoning=(setting.reasoning or "") + (f"；节能:{decision.level}" if decision.level != "normal" else ""),
        )
        return new_setting, adj
