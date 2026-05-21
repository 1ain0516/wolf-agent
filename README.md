# Wolf Agent v1

AI vs AI 狼人杀对局引擎（旁观模式）。

## 快速开始

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖（测试）

# 设置 LLM API（DeepSeek 兼容格式）
set DEEPSEEK_API_KEY=your_key_here

# 跑一局（需 API key，~6min）
python -m wolf_agent run_spectate --seed 42

# 跑一局（stub 模式，确定性 mock，无需 key，~1s）
python -m wolf_agent run_spectate --seed 42 --stub
```

## 输出

- 终端显示实时对局（每轮夜晚/白天/投票/处决实时输出）
- `games/<game_id>.events.jsonl` — 完整事件流（10 种事件类型）
- `games/<game_id>.summary.json` — 对局摘要

## 测试

```bash
python -m pytest tests/ -v
```

14 tests（10 单元 + 4 e2e mock），全部通过。

## 架构

```
wolf_agent/
├── engine/    LangGraph 状态机（7 节点 + 循环）
├── agents/    MBTI 人格模板 + Agent 封装 + LLM 客户端
├── events/    Canonical Event Log（append-only JSONL）
└── cli/       CLI 入口
```
