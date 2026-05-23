# Wolf Agent v2

AI vs AI 狼人杀对局引擎（旁观模式） — SBTI 人格 × 成长记忆。

## 快速开始

```bash
pip install -r requirements.txt

# 设置 LLM API（DeepSeek 兼容格式）
set DEEPSEEK_API_KEY=your_key_here

# 跑一局（需 API key，~6min）
python -m wolf_agent run_spectate --seed 42

# 跑一局（stub 模式，确定性 mock，无需 key，~1s）
python -m wolf_agent run_spectate --seed 42 --stub

# 批量跑 10 局（stub 模式）
python -m wolf_agent run_spectate --batch 10 --stub

# 统计分析已有对局
python -m wolf_agent stats --dir games/

# 跑测试
python -m pytest tests/ -v
```

## SBTI 人格系统（v2 新增）

SBTI 是 16 套 meme 人格，每套含 5 个行为数值参数（0.0-1.0）：

| SBTI | 中文标签 | 说话欲 | 攻击性 | 信任偏见 | 谎言舒适度 | 投票独立性 |
|------|---------|--------|--------|---------|-----------|----------|
| BOSS | 掌控者 | 0.85 | 0.85 | 0.20 | 0.50 | 0.20 |
| FAKE | 伪人 | 0.50 | 0.30 | 0.50 | 0.95 | 0.70 |
| THIN-K | 思考者 | 0.50 | 0.30 | 0.20 | 0.20 | 0.90 |
| FUCK | 草者 | 0.85 | 0.95 | 0.80 | 0.20 | 0.05 |
| OJBK | 无所谓人 | 0.10 | 0.20 | 0.50 | 0.50 | 0.05 |
| SHIT | 愤世者 | 0.85 | 0.85 | 0.05 | 0.50 | 0.70 |
| ZZZZ | 装死者 | 0.05 | 0.20 | 0.50 | 0.70 | 0.50 |
| MALO | 吗喽 | 0.85 | 0.30 | 0.70 | 0.30 | 0.20 |
| JOKE-R | 小丑 | 0.85 | 0.50 | 0.50 | 0.95 | 0.05 |
| LOVE-R | 多情者 | 0.50 | 0.20 | 0.95 | 0.20 | 0.20 |
| MUM | 妈妈 | 0.50 | 0.20 | 0.50 | 0.20 | 0.50 |
| IMSB | 傻者 | 0.85 | 0.30 | 0.70 | 0.50 | 0.20 |
| SOLO | 孤儿 | 0.20 | 0.70 | 0.05 | 0.50 | 0.95 |
| SEXY | 尤物 | 0.95 | 0.50 | 0.50 | 0.70 | 0.50 |
| MONK | 僧人 | 0.20 | 0.20 | 0.20 | 0.05 | 0.95 |
| DEAD | 死者 | 0.05 | 0.20 | 0.50 | 0.70 | 0.05 |

## 成长记忆系统（v2 新增）

- 每局结束后自动为 9 位玩家生成自我反思
- 存储到 `games/<game_id>.memories.jsonl`（单局备份）+ `games/memories.jsonl`（全局索引）
- 下一局注入历史记忆（最多 3 条，strength ≥ 0.5）
- `--no-memory` 模式退化为 v1 行为（完全确定）

### Seed 确定性契约

| 模式 | CLI | 行为 |
|------|-----|------|
| Production | 默认 | 同一 seed 不同时间可能不同（记忆累积） |
| Isolated | `--memory-dir <空目录>` | 同一 seed → 相同 |
| No-Memory | `--no-memory` / `--stub` | 同一 seed → 完全确定（=v1） |

## CLI

```bash
python -m wolf_agent run_spectate [--seed INT] [--stub] [--no-memory]
                                    [--memory-dir PATH] [--batch N] [--batch-seed INT]

python -m wolf_agent stats [--dir PATH] [--output PATH]
```

### 示例

```bash
# 无记忆模式（v1 等效）
python -m wolf_agent run_spectate --seed 42 --stub --no-memory

# 隔离目录测试（空目录 → 确定性）
python -m wolf_agent run_spectate --seed 42 --stub --memory-dir ./test-memories/

# 批量统计 100 局
python -m wolf_agent run_spectate --batch 100 --stub --batch-seed 42

# 分析已有对局
python -m wolf_agent stats --dir games/ --output stats.json
```

## 输出

- 终端显示实时对局
- `games/<game_id>.events.jsonl` — 完整事件流（10 种事件类型）
- `games/<game_id>.summary.json` — 对局摘要
- `games/<game_id>.memories.jsonl` — 单局记忆（v2）
- `games/memories.jsonl` — 全局记忆索引（v2）
- `games/stats-batch-<seed>-<timestamp>.json` — 批量统计（v2）

## 测试

```bash
python -m pytest tests/ -v
```

33 tests（10 单元 + 4 e2e mock + 5 人格 + 8 记忆 + 6 统计），全部通过。

## 架构

```
wolf_agent/
├── engine/    LangGraph 状态机（8 节点 + 循环） + 记忆系统
├── agents/    SBTI 人格模板（16套） + Agent 封装 + LLM 客户端
├── events/    Canonical Event Log（append-only JSONL）
└── cli/       CLI 入口（旁观/批量/统计）
```
