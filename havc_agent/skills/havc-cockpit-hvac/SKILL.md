---
name: havc-cockpit-hvac
description: >-
  Use when working on Havc-Agent under Havc-Agent/havc_agent/. Covers ISO 7730
  PMV/PPD, multi-zone comfort agent, defog agent, energy guard agent, vehicle
  signal bus adapter, gradual-approach memory, and how to extend knowledge /
  tools / skills. Trigger on: 座舱空调/热舒适/PMV/能耗/除雾/HAVC.
---

# HVAC 座舱空调 Agent · 专家技能

本技能描述 **Havc-Agent** 工程规范：多温区舒适 Agent、除雾 Agent、能耗治理 Agent、
车辆信号适配层、记忆逐步逼近。

## 决策优先级

`安全(起雾/强制除霜)` > `能耗软钳制(低 SOC)` > `用户偏好逐步逼近` > `专业舒适锚点(PMV≈0)` > `LLM`

## 扩展点

- 知识：`havc_agent/knowledge/docs/`、`havc_agent/defog/docs/`
- 舒适工具：`havc_agent/tools/thermal_comfort.py`
- Skill：`havc_agent/skills/registry.py`
- 除雾 Agent：`havc_agent/defog/`
- 能耗 Agent：`havc_agent/energy/agent.py`（阈值在 `config.ENERGY`）
- 车辆总线：`havc_agent/vehicle/adapter.py`（默认 mock，可自写 CAN/SOA）

## 设定域

温度 15.5–31.5℃ / 0.5；风量 1–7；7 种出风模式。
