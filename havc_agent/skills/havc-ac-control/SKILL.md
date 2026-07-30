---
name: havc-ac-control
description: >
  将自然语言空调意图解析为结构化设定字段。用于 NLU / 交互快路径参考：
  只填有意义字段，遵守温度与风量绝对/相对互斥。
---

# Skill: 空调域结构化控制（参考 BrainCloud car-control）

## 原则

1. 只填用户提到的字段，不要占位。  
2. 绝对温度 `temp_set` 与相对调温 `delta_temp` 二选一。  
3. 绝对风量 `fan_level` 与相对调风 `delta_fan` 二选一。  
4. 出风模式仅使用：`face` / `feet` / `face_feet`（除霜由除雾 Agent / 安全层叠加）。  
5. 无法识别时返回 `{"no_action": true}`。

## 字段

| 意图 | 字段 |
|------|------|
| 打开/设定 | `temp_set`（15.5–31.5，0.5 步进）、`fan_level`（1–7）、`air_mode` |
| 相对调温 | `delta_temp`（℃，可负） |
| 相对调风 | `delta_fan`（档，可负） |
| 关空调（演示） | `power: "off"`（当前 PoC 以低风量+中性温度近似） |

示例 — 主驾 24℃ 吹面：

```json
{"temp_set": 24.0, "fan_level": 3, "air_mode": "face"}
```

示例 — 调高 2 度：

```json
{"delta_temp": 2.0}
```
