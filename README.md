# 🐺 Wolf Agent — AI 狼人杀对战平台

LangGraph 状态机 + MBTI 人格 Agent + 双空间通信 + Agent 成长记忆 + 社会实验评价。

## 🎯 完整愿景

一个支持三种模式的 AI 狼人杀平台：

| 模式 | 名称 | 用途 |
|------|------|------|
| **A — 旁观** | AI vs AI 自动对局 | 测试调参、批量统计分析 |
| **B — 参与** | 真人+AI 混战 | 自娱自乐 |
| **C — 法官** | 真人当上帝裁决生死 | 聚会娱乐 |

### 核心技术特性

- **LangGraph 状态机** — 12 阶段游戏流程（夜晚→白天→投票→处决→胜负）
- **双空间通信** — 白天公共板发言投票 + 夜晚狼人密道策略私聊
- **16 套 MBTI 人格** — 每种人格不同的发言风格/策略倾向/评价滤镜
- **Agent 成长记忆** — 每局后自我复盘+评价他人，注入下局，越玩越聪明
- **Canonical Event Log** — append-only JSONL 事件源，回放/统计/记忆统一派生
- **像素小人可视化** — 16×16 CSS pixel art + 发言/投票/死亡动画
- **社会实验评价** — 8 个 AI 从各自人格滤镜评价真人玩家，模拟不同性格朋友
- **随机角色分配** — 每局 Fisher-Yates 洗牌，同一 MBTI 不连续两局同角色
- **断线/超时兜底** — 60s 超时代发言、断线重连摘要、AI 托管完成

## 📐 技术架构

| 层 | 技术 |
|----|------|
| Agent 框架 | **LangGraph**（状态机） |
| 后端 | Python + FastAPI |
| AI 模型 | 任何 LLM API（默认 DeepSeek V4 Flash） |
| 前端 | React + Tailwind + CSS pixel art |
| 事件存储 | JSONL file-based（games/ 目录） |

### LangGraph 状态流

```
INIT → ASSIGN_ROLES → NIGHT(WolfDen→Seer→Witch→Resolve)
                                    ↓
                      DAY(Discussion→Debate)
                                    ↓
                      VOTE→VoteResolve→Execution→CheckWinner
                                                    ↓
                                              GAME_END or NIGHT(loop)
```

### 双空间通信

| 空间 | 可见范围 | 时间段 | 用途 |
|------|---------|--------|------|
| 公共板 🏛️ | 所有存活玩家 | 白天 | 发言、辩论、投票 |
| 狼人密道 🐺 | 仅狼人阵营 | 夜晚 | 商议刀人、自刀骗药 |

## 🧠 MBTI 人格系统

16 种人格 × 各自发言风格/策略倾向/评价滤镜。v1 先做 4 套：

| MBTI | 风格 | 策略倾向 |
|------|------|---------|
| ENTJ | 激进领袖 | 主动控场、带投票节奏、狼人时自刀骗药 |
| INTP | 逻辑分析 | 靠投票记录推理、发言简短、狼人时潜伏 |
| ESFJ | 社交调和 | 活跃气氛、容易跟票、容易被操纵 |
| INFJ | 直觉洞察 | 发言模糊但直觉准、预言家验人方向有策略 |

## 📋 版本路线

### v1（本期实现）— 旁观模式基础引擎

**范围：**
- 9 人标准局（3狼+1预言家+1女巫+4村民）
- 旁观模式（AI vs AI 全自动）
- LangGraph 核心状态机
- 双空间通信（公共板+狼人密道）
- Canonical Event Log（10 种事件类型，append-only JSONL）
- 4 套 MBTI 人格模板，接口预留 16 套扩展位
- 发言策略摘要（strategy_summary），不展示原始推理链
- CLI 可运行（`run_spectate --seed 42`）
- 固定规则冻结（屠边、平票重投、遗言、夜晚顺序、女巫规则）
- 每个事件携带 visibility 字段

**固定规则（v1）：**
| 规则 | 值 |
|------|----|
| 胜利条件 | **屠边**：狼全灭=好人胜；狼≥好人=狼胜 |
| 人数 | 9 人固定 |
| 角色 | 3狼+1预言家+1女巫+4村民 |
| 夜晚顺序 | 狼人刀人→预言家验人→女巫救/毒→天亮结算 |
| 女巫解药 | 1次，首夜可自救，首夜知道刀口 |
| 女巫毒药 | 1次，可与解药同夜使用 |
| 投票平票 | 重投一次，仍平票→无人出局(流局) |
| 遗言 | 首夜被杀+白天被投出→有遗言 |
| 发言 | 每人≤3次/轮，≤200字/次 |

**验收标准：**
- [ ] 固定 seed 跑完 1 局 9 人 AI vs AI
- [ ] 生成 `games/<game_id>.events.jsonl`（10 种事件齐）
- [ ] 3 个单元测试（胜负判定、投票结算、夜晚结算）
- [ ] 1 个 e2e 脚本（`run_spectate_game --seed 42`）
- [ ] 同一 seed 产生相同对局

### v1.1 — 玩家模式

- 模式 B 真人参战（打字发言+投票+夜晚行动）
- 超时兜底（60s 代发言、30s 弃权投票、45s 夜晚超时）
- 断线重连摘要
- 前端 React 基础对局页

### v1.2 — 法官模式

- 模式 C 法官裁决（投票处决确认、夜晚行动审批）
- 像素小人静态展示 + 发言动画
- 法官偷看狼人密道（可选项）

### v2 — 记忆与评价

- Agent 成长记忆（反馈生成+JSON 存储+下局注入）
- 回放 UI（时间线+关键节点标记+快捷分析）
- 社会实验评价（AI 多人格滤镜评价玩家+聚合面板）
- 剩余 12 套 MBTI 模板
- 好友角色映射（娱乐彩蛋）

## 📁 项目结构

```
wolf-agent/
├── src/
│   ├── __init__.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── state_machine.py    ← LangGraph 状态机
│   │   └── rules.py            ← 固定游戏规则
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── wolf_agent.py       ← MBTI Agent 封装
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── mbti_templates.py ← 人格 prompt 模板
│   ├── events/
│   │   ├── __init__.py
│   │   └── event_log.py        ← Canonical Event Log
│   └── cli/
│       ├── __init__.py
│       └── run_spectate.py     ← CLI 入口
├── tests/
│   ├── __init__.py
│   ├── test_winner_check.py
│   ├── test_vote_resolution.py
│   ├── test_night_cycle.py
│   └── test_e2e_spectate.py
├── games/                      ← 对局日志输出
├── docs/
│   ├── design-spec-wolf-agent-platform-v1.1.md
│   └── handoff-to-claude-code-wolf-agent-v1.md
├── .github/workflows/test.yml  ← CI
├── requirements.txt
└── README.md
```

## 👥 开发流程

**接力制**（非并行）：

```
你: git push
队友: git pull → 开发 → git push
你: git pull → 找我读新进度 → 我改代码 → git push
```

- 直接 main 单线，不需要分支/PR
- 每次 push 触发 GitHub Actions 自动跑测试
- 连 Vercel 后每次 push 自动部署 Demo

## 🔗 链接

- GitHub: https://github.com/1ain0516/wolf-agent
- Design Spec 完整版: `docs/design-spec-wolf-agent-platform-v1.1.md`
- Handoff: `docs/handoff-to-claude-code-wolf-agent-v1.md`
- Codex Pre-Review: `C:\Users\24485\Documents\hermes\codex-pre-review-wolf-agent-platform.md`
