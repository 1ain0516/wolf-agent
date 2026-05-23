# Wolf Agent v2

**AI vs AI 狼人杀对局引擎** — 完整的 LangGraph 状态机 + SBTI 人格系统 + 成长记忆 + 批量统计。

旁观模式下，9 位 AI 玩家自主决策、互相博弈、学习成长。每局生成完整事件日志、人格分析、记忆反思。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API key（DeepSeek 兼容）
set DEEPSEEK_API_KEY=your_key_here

# 跑一局（需 API key，~6min）
python -m wolf_agent run_spectate --seed 42

# 跑一局（stub 模式，无需 key，~1s）
python -m wolf_agent run_spectate --seed 42 --stub

# 批量跑 10 局 + 统计
python -m wolf_agent run_spectate --batch 10 --stub

# 启动 web 界面（查看对局回放 + 统计）
python -m wolf_agent web

# 跑测试
python -m pytest tests/ -v
```

## 核心特性

### 1. SBTI 人格系统（16 套）

每个 AI 玩家有独特的人格，由 5 个行为参数定义：

| 人格 | 标签 | 说话欲 | 攻击性 | 信任偏见 | 谎言舒适度 | 投票独立性 |
|------|------|--------|--------|---------|-----------|----------|
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

人格影响 AI 的决策：激进型（BOSS、FUCK）倾向于主动发言和投票；保守型（MONK、OJBK）倾向于观察；欺骗型（FAKE、JOKE-R）更敢说谎。

### 2. 成长记忆系统

- 每局结束后，9 位玩家各生成自我反思（学到了什么、下次怎么改进）
- 记忆存储到 `games/<game_id>.memories.jsonl`（单局）+ `games/memories.jsonl`（全局索引）
- 下一局自动注入历史记忆（最多 3 条，strength ≥ 0.5）
- 支持 `--no-memory` 模式退化为 v1 行为（完全确定）

### 3. Canonical Event Log

完整的事件流（append-only JSONL）：
- `role_assigned` — 身份分配
- `phase_started` — 阶段开始（白天/黑夜）
- `message_posted` — 发言
- `action_submitted` — 行动（狼人杀人、预言家验证、女巫救人）
- `vote_cast` — 投票
- `player_eliminated` — 玩家出局
- `game_ended` — 游戏结束
- 等 10 种事件类型

每个事件包含：`game_id`, `round`, `phase`, `from_player`, `to_player`, `channel`, `visibility`, `content`, `metadata`

## 命令行接口

```bash
# 单局对局
python -m wolf_agent run_spectate [--seed INT] [--stub] [--no-memory] [--memory-dir PATH]

# 批量对局 + 统计
python -m wolf_agent run_spectate --batch N [--batch-seed INT] [--stub]

# 统计分析
python -m wolf_agent stats [--dir PATH] [--output PATH]

# 启动 web 界面
python -m wolf_agent web [--port 5000]
```

### 常用命令

```bash
# 快速测试（无需 API key，~1s）
python -m wolf_agent run_spectate --seed 42 --stub

# 完全确定性（v1 等效）
python -m wolf_agent run_spectate --seed 42 --stub --no-memory

# 隔离测试（空目录 → 确定性）
python -m wolf_agent run_spectate --seed 42 --stub --memory-dir ./test-memories/

# 批量跑 100 局 + 统计
python -m wolf_agent run_spectate --batch 100 --stub --batch-seed 42

# 分析已有对局
python -m wolf_agent stats --dir games/ --output stats.json

# 启动 web 查看对局回放
python -m wolf_agent web
```

## 输出文件

每局对局生成：

| 文件 | 内容 |
|------|------|
| `games/<game_id>.events.jsonl` | 完整事件流（append-only） |
| `games/<game_id>.summary.json` | 对局摘要（赢家、轮数、事件数） |
| `games/<game_id>.memories.jsonl` | 单局记忆（9 位玩家的反思） |
| `games/memories.jsonl` | 全局记忆索引（跨局） |
| `games/stats-batch-<seed>-<ts>.json` | 批量统计（胜率、人格分析） |

## Seed 确定性

| 模式 | 命令 | 行为 |
|------|------|------|
| **Production** | 默认 | 同一 seed 不同时间可能不同（记忆累积） |
| **Isolated** | `--memory-dir <空目录>` | 同一 seed → 完全相同 |
| **No-Memory** | `--no-memory` 或 `--stub` | 同一 seed → 完全确定（=v1） |

## 测试

```bash
python -m pytest tests/ -v
```

**33 tests 全部通过**：
- 10 单元测试（游戏逻辑）
- 4 e2e 测试（完整对局）
- 5 人格测试（SBTI 行为）
- 8 记忆测试（成长系统）
- 6 统计测试（批量分析）

## 架构

```
wolf_agent/
├── engine/
│   ├── game.py          LangGraph 状态机（12 阶段）
│   ├── memory.py        成长记忆系统
│   └── __init__.py
├── agents/
│   ├── agent.py         Agent 封装 + 决策逻辑
│   ├── personality.py   SBTI 人格模板（16 套）
│   ├── llm.py           LLM 客户端（DeepSeek）
│   └── __init__.py
├── events/
│   └── __init__.py      Canonical Event Log
├── cli/
│   ├── main.py          CLI 入口
│   └── __init__.py
├── web/
│   ├── app.py           Flask 后端 API
│   └── index.html       前端界面
└── tests/               单元 + e2e 测试
```

## Web 界面

启动 `python -m wolf_agent web` 后访问 `http://localhost:5000`：

- **对局回放** — 实时查看事件流、玩家状态、投票结果
- **人格分析** — 每位玩家的 SBTI 人格参数 + 行为表现
- **成长记忆** — 玩家的自我反思 + 历史记忆注入
- **批量统计** — 胜率、人格分布、策略分析
- **事件过滤** — 按类型筛选（发言、投票、死亡等）
