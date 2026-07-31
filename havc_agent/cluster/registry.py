"""配置驱动的 Agent 集群注册表（对齐 BrainCloud agents.enabled + priority）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from ..config import PROJECT_ROOT


@dataclass(frozen=True)
class AgentSpec:
    """单个 Agent 的注册元数据。"""

    id: str
    name: str
    priority: int = 100
    enabled: bool = True
    role: str = ""
    description: str = ""


@dataclass
class ClusterRegistry:
    """按 priority 降序管理 Agent；支持按 id 启停。"""

    specs: list[AgentSpec] = field(default_factory=list)

    def enabled_agents(self) -> list[AgentSpec]:
        return sorted(
            [s for s in self.specs if s.enabled],
            key=lambda s: s.priority,
            reverse=True,
        )

    def get(self, agent_id: str) -> Optional[AgentSpec]:
        for s in self.specs:
            if s.id == agent_id:
                return s
        return None

    def is_enabled(self, agent_id: str) -> bool:
        s = self.get(agent_id)
        return bool(s and s.enabled)

    def summary(self) -> list[dict[str, Any]]:
        return [
            {
                "id": s.id,
                "name": s.name,
                "priority": s.priority,
                "enabled": s.enabled,
                "role": s.role,
                "description": s.description,
            }
            for s in sorted(self.specs, key=lambda x: x.priority, reverse=True)
        ]


_DEFAULT_SPECS = [
    AgentSpec("comfort", "舒适 Agent", 100, True, "per_seat",
              "ISO 7730 多温区热舒适推理（PMV/PPD）"),
    AgentSpec("defog", "除雾 Agent", 95, True, "cabin",
              "玻璃温度/露点/雨量判定，安全优先叠加除霜"),
    AgentSpec("energy", "能耗 Agent", 90, True, "cabin",
              "低 SOC 软钳制风量与设定温差"),
    AgentSpec("interaction", "交互快路径", 110, False, "ui",
              "（产品版停用）手调/记忆写入"),
    AgentSpec("nlu", "语音理解", 85, False, "per_seat",
              "（产品版停用）自然语言指令"),
]


def _load_yaml_overrides(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    agents = data.get("agents") or {}
    return {str(k): (v or {}) for k, v in agents.items()}


def build_default_cluster(config_path: Optional[Path] = None) -> ClusterRegistry:
    """从 config/agents.yaml 合并启停与优先级，缺省用内置表。"""
    path = config_path or (PROJECT_ROOT / "config" / "agents.yaml")
    overrides = _load_yaml_overrides(path)
    specs: list[AgentSpec] = []
    for base in _DEFAULT_SPECS:
        ov = overrides.get(base.id, {})
        specs.append(
            AgentSpec(
                id=base.id,
                name=ov.get("name", base.name),
                priority=int(ov.get("priority", base.priority)),
                enabled=bool(ov.get("enabled", base.enabled)),
                role=ov.get("role", base.role),
                description=ov.get("description", base.description),
            )
        )
    # YAML 中新增的自定义 id 也纳入展示
    known = {s.id for s in specs}
    for aid, ov in overrides.items():
        if aid in known:
            continue
        specs.append(
            AgentSpec(
                id=aid,
                name=str(ov.get("name", aid)),
                priority=int(ov.get("priority", 50)),
                enabled=bool(ov.get("enabled", False)),
                role=str(ov.get("role", "custom")),
                description=str(ov.get("description", "")),
            )
        )
    return ClusterRegistry(specs=specs)
