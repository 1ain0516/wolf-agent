# Wolf Agent v1

AI vs AI 狼人杀对局引擎（旁观模式）。

## 快速开始

```bash
pip install -r requirements.txt

# 设置 LLM API（DeepSeek 兼容格式）
set DEEPSEEK_API_KEY=your_key_here

# 跑一局
python -m wolf_agent run_spectate --seed 42
```

## 输出

- 终端显示实时对局
- `games/<game_id>.events.jsonl` — 完整事件流
- `games/<game_id>.summary.json` — 对局摘要

## 验收

```bash
python -m wolf_agent run_spectate --seed 42
# 同一 seed 产生相同对局
```
