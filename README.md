# Havc-Agent · HVAC 座舱多 Agent

座舱空调智能控制 Agent 集群：多温区热舒适、智能除雾、能耗治理、记忆学习。  
企业控制台风格 UI；配置化 Agent 启停（对齐 BrainCloud 集群思路）。

## 文档

- [操作指南](docs/操作指南.md) — 安装、启动、演示步骤  
- [了解指南](docs/了解指南.md) — 架构、决策优先级、与 BrainCloud 对齐点  

## 快速开始

```bash
cd /Users/yz/Desktop/比赛/havc/Havc-Agent
conda activate havc-agent
pip install -r requirements.txt
python -m streamlit run havc_agent/app_web.py
```

## 能力摘要

| 模块 | 说明 |
|------|------|
| 舒适 Agent | ISO 7730 + RAG + LangGraph 多温区 |
| 除雾 Agent | 玻璃/露点/雨量，安全优先 |
| 能耗 Agent | 低 SOC 软钳制 |
| 集群层 | `config/agents.yaml` 启停、Pending、Ingest、Feedback、RID |
| 控制台 | 浅色企业风、显式「执行推理」、运维页 |

决策优先级：`安全除霜` > `能耗` > `用户偏好` > `PMV` > `LLM`
