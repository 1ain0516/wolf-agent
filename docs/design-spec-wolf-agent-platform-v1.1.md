# Wolf Agent v1 — Design Spec

## 1. 定位

一个**旁观模式（AI vs AI）** 的狼人杀对局引擎，核心目标：

1. 跑通 9 人标准局的完整流程
2. 生成统一的 canonical event log
3. 为后续模式 B（参战）/ C（法官）以及回放/记忆/评价提供可靠的数据基座

> v1 **不做**：模式 B 真人参战、模式 C 法官、回放 UI、成长记忆注入、社会实验评价。这些放在 v1.1/v2。

## 2. v1 固定规则

| 规则 | 值 |
|------|----|
| 玩家人数 | 9 人固定 |
| 角色分配 | 3 狼人 + 1 预言家 + 1 女巫 + 4 村民 |
| 胜利条件 | **屠边规则**：狼人全灭则好人胜；狼人数量 ≥ 好人（神职+村民）数量则狼人胜 |
| 夜晚顺序 | ① 狼人刀人 → ② 预言家验人 → ③ 女巫行动 → ④ 天亮结算 |
| 狼人刀人 | 每晚商议后确认 1 个击杀目标，不可不刀 |
| 预言家验人 | 每晚验 1 人，结果格式：`{"target": int, "is_wolf": bool}` |
| 女巫解药 | 一整局仅 1 次；首夜可以自救？**可以**；首夜是否知道刀口？**知道** |
| 女巫毒药 | 一整局仅 1 次，可与解药同夜使用 |
| 投票平票 | **重投一次**。仍平票 → **无人出局**（流局） |
| 遗言 | 首夜被杀 + 白天被投出 → **有遗言**；其他死亡 → **无遗言** |
| 发言限制 | 每轮白天每人最多 3 次发言，每次 ≤ 200 字；全场自由辩论 2 轮 |
| 首夜保护 | 女巫首夜可以自救 |

## 3. 技术架构

### 3.1 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| Agent 框架 | **LangGraph** | 状态机天然匹配回合制游戏 |
| 后端 | **Python + FastAPI** | 现有 Hermes 生态 |
| AI 模型 | DeepSeek V4 Flash | 你已有的 key，不额外花钱 |
| 前端 | **先 CLI 可跑，再接 React** | v1 不做完整 UI |
| 可视化 | 像素小人 → v1.2 |

### 3.2 LangGraph 状态机（v1）

```
[INIT] → [ASSIGN_ROLES] → [NIGHT] → [DAY] → [VOTE] → [EXECUTION] → [CHECK_WINNER]
                               ↑                                          │
                               └──────────────────────────────────────────┘ (continue)
                                                                          │
                                                                       [END]
```

各阶段职责：

| 阶段 | 说明 |
|------|------|
| `INIT` | 创建 9 个 Agent 实例，分配 MBTI |
| `ASSIGN_ROLES` | Fisher-Yates shuffle 分配 3狼+1预言家+1女巫+4村民 |
| `NIGHT` | 子图：狼人密道 → 预言家验人 → 女巫行动 → 结算死亡 |
| `DAY` | 依次发言 + 自由辩论 |
| `VOTE` | 所有存活玩家投票 + 计票 + 平票处理 |
| `EXECUTION` | 公布投票结果 + 处决/流局 |
| `CHECK_WINNER` | 检查屠边条件 → WINNER / CONTINUE |

### 3.3 双空间通信（v1）

| 空间 | 可见范围 | 时间段 | 用途 |
|------|---------|--------|------|
| **公共板** | 所有存活玩家 | 白天 | 发言、投票 |
| **狼人密道** | 仅狼人阵营 | 夜晚 | 商议刀人 |

v1 两个空间都是 AI 之间通信，无真人介入。

### 3.4 MBTI 人格（v1）

v1 先做 **4 套**代表人格，接口保留 16 套扩展位：

| MBTI | 风格 | 策略倾向 |
|------|------|---------|
| **ENTJ** | 激进领袖 | 主动控场、带投票节奏、狼人时倾向自刀骗药 |
| **INTP** | 逻辑分析 | 靠投票记录推理、发言简短、狼人时潜伏不暴露 |
| **ESFJ** | 社交调和 | 活跃气氛、容易透露信息、跟票倾向高 |
| **INFJ** | 直觉洞察 | 发言模糊但直觉准、预言家时验人方向有策略 |

每个 Agent 系统 prompt 包含 MBTI 人格描述。v1 不做 Agent 间记忆传递（记忆系统放在 v2）。

## 4. 对局流程

```
开始
 │
 ├── 分配角色 (3狼 + 1预言家 + 1女巫 + 4村民)
 │
 ├── 晚上 ── 狼人密道商议 → 确认刀人目标
 │                 ↓
 │          ── 预言家验人
 │                 ↓
 │          ── 女巫行动（救/毒/不操作）
 │                 ↓
 │          ── 天亮结算：公布昨晚死亡
 │
 ├── 白天 ── 按座位顺序发言 (每人≤3次)
 │                 ↓
 │          ── 自由辩论 (2轮)
 │                 ↓
 │          ── 投票 → 计票 → 平票? → 重投/流局
 │
 ├── 处决 ── 公布身份 → 遗言（如有）
 │
 └── 检查胜负 → 有人赢? → END
                     │
                      └→ 下一夜
```

## 5. Canonical Event Log（统一事件源）

### 5.1 设计原则

所有 UI 渲染、统计、回放、记忆**都派生自唯一一个 append-only 事件流**。不存在独立的 replay JSON、memory JSON、UI state——它们都是事件流的视图。

### 5.2 最小事件类型（v1）

```
game_started
role_assigned
phase_started
message_posted        ← 公开板或狼人密道的发言
action_submitted      ← 狼人刀人、预言家验人、女巫行动
vote_cast             ← 每个玩家投票
vote_resolved         ← 计票结果 + 平票处理
player_eliminated     ← 死亡事件（含死因、遗言）
phase_resolved        ← 阶段结算摘要
game_ended            ← 胜负

[v2 追加]
agent_reflection_created
judge_decision
```

### 5.3 事件体结构

```json
{
  "event_id": "evt-0007",
  "game_id": "wolf-v1-001",
  "timestamp": "2026-05-21T15:30:00Z",
  "type": "message_posted",
  "channel": "public_board",
  "visibility": "public",
  "from_player": 3,
  "content": "我怀疑5号，他昨晚投票很奇怪",
  "strategy_summary": "尝试引导怀疑对象以减轻自身压力"
}
```

### 5.4 `visibility` 可见性字段

每个事件携带 `visibility`，前端按 `current_role + mode` 过滤：

| 值 | 可见范围 |
|----|---------|
| `public` | 所有存活玩家 |
| `wolf_den` | 仅狼人阵营 |
| `role_private:<player_id>` | 仅该角色本人（预言家验人结果）|
| `judge_only` | 仅法官模式 |
| `debug_only` | 仅旁观模式 + 调试日志 |

v1（模式 A 旁观）：`debug_only` 以外的全部可见。

### 5.5 事件文件存储

每局生成一个文件：

```
D:\agent session\wolf-agent\games\
├── wolf-v1-001.events.jsonl    ← append-only 事件流 (JSONL)
└── wolf-v1-001.summary.json    ← 对局长览（game_ended 派生）
```

- `.events.jsonl` — 每行一个 JSON 事件，只追加不修改
- `.summary.json` — 最终状态快照，方便下游读取

### 5.6 事件从 v1 到 v2 的扩展

| v1 | v2 追加 | 说明 |
|----|---------|------|
| 10 种事件类型 | + `agent_reflection_created` | 记忆系统 |
| `visibility`: 4 级 | + 前端筛选 UI | 回放视图 |
| 存储为 JSONL | + 回放索引 + 查询接口 | 回放 UI |

## 6. Agent 人格与发言约束

### 6.1 发言策略摘要

**不存储或展示原始链式推理（CoT）**。每个 Agent 发言时附带一条 `strategy_summary` 字段：

```json
{
  "from_player": 3,
  "content": "我建议投2号，他昨晚没有参与讨论",
  "strategy_summary": "用沉默指责转移焦点，避免自身被投票"
}
```

- `strategy_summary` 最大 80 字
- 旁观模式（v1）展示策略摘要
- 模式 B/C 默认隐藏，对局结束后作为回放信息开放

### 6.2 发言约束

| 规则 | 值 |
|------|----|
| 每轮最多发言次数 | 3 次 |
| 单次发言最大字数 | 200 字 |
| 辩论轮数 | 2 轮（全部发言后） |
| 禁止场外信息 | Agent 不能提及"我是AI"、"游戏外"等 |

### 6.3 MBTI 风格映射

每局开始前，每个 Agent 接收以下形式的 system prompt：

```
你是 3 号玩家，身份为【村民】。
你的性格是【ISTJ】：务实、理性、相信投票记录。
发言风格：简洁，引用事实，不做情绪化指责。
策略倾向：先观察一轮再表态，不轻易改票。
```

v1 提供 4 套模板（ENTJ/INTP/ESFJ/INFJ），接口预留 16 套扩展位。

## 7. 运行与验收

### 7.1 CLI 运行

```
python -m wolf_agent run_spectate --seed 42
```

输出：
- 终端展示实时代理发言
- 事件流写入 `games/wolf-v1-XXX.events.jsonl`
- 最终打印 winner + 对局文件路径

### 7.2 v1 验收标准

| 检查项 | 具体标准 |
|--------|---------|
| 完整对局 | 用固定 seed 跑完 1 局 9 人 AI vs AI（约 5-15 分钟） |
| 事件文件 | 生成 `games/<game_id>.events.jsonl`，包含所有 10 种事件类型 |
| 内容覆盖 | JSON 中包含公开发言、狼人密道、投票、夜晚行动、死亡、胜负 |
| 单元测试 ≥3 | `test_winner_check` / `test_vote_resolution` / `test_night_cycle` |
| 端到端脚本 | `run_spectate_game --seed 42` 输出 winner + log path |
| 可重复性 | 同一 seed 产生相同对局（确定性） |
| 边界覆盖 | 平票重投→流局、狼人全灭→好人胜、狼人≥好人→狼人胜 |

## 8. 项目交付

```
D:\agent session\wolf-agent\
├── src\
│   ├── engine/              ← LangGraph 状态机 + 规则
│   ├── agents/              ← MBTI prompt 模板 + Agent 封装
│   ├── events/              ← Canonical Event Log 写入/读取
│   └── cli/                 ← CLI 入口
├── tests/
│   ├── test_winner_check.py
│   ├── test_vote_resolution.py
│   └── test_night_cycle.py
├── games/                   ← 对局日志输出目录
├── requirements.txt
└── README.md
```

## 9. 后续版本预览

| 版本 | 新增 |
|------|------|
| v1.1 | 模式 B 真人参战 + 超时兜底 + 重连摘要 |
| v1.2 | 模式 C 法官 + 基础 React 对局页 + 像素小人静态展示 |
| v2 | 成长记忆注入 + 回放 UI + 社会实验评价 + 剩余 12 套 MBTI |

## 附录 A: 为什么这么做

### Codex Pre-Review 指出的核心问题与改动对照

| Codex 发现 | v1 改动 |
|-----------|---------|
| v1 范围过大 | 收敛到旁观模式 + 9 人 + 核心状态机 + JSON log |
| 规则未冻结 | §2 固定 9 人规则，明确胜负/遗言/平票/夜晚顺序 |
| 内心独白属于展示原始推理链 | 改成 `strategy_summary` 字段，不存储 CoT |
| 无统一事件源 | §5 Canonical Event Log，10 种事件，append-only JSONL |
| 可见性未定义 | 每个事件带 `visibility` 字段 |
| MBTI 朋友模拟有误导风险 | 推迟到 v2，v1 只做 4 套人格模板 |
| 缺少验收标准 | §7.2 验收标准 7 项，含单元测试和 e2e |
| 文档缺少 §5 | §5 改为 Canonical Event Log |
