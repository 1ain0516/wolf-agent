# Handoff: Wolf Agent v1 Implementation

## 执行人
Claude Code — Implementation Engineer

## 规格文件
`D:\agent session\2026-05-21_Wolf-Agent-Design-Spec\design-spec-wolf-agent-platform-v1.1.md`

## v1 范围（只做这些）

1. **旁观模式（AI vs AI）** — 无真人介入
2. **9 人标准局** — 3狼+1预言家+1女巫+4村民
3. **屠边规则**
4. **双空间通信** — 公共板(白天) + 狼人密道(夜晚)
5. **Canonical Event Log** — append-only JSONL，10种事件类型
6. **4 套 MBTI 人格**（ENTJ/INTP/ESFJ/INFJ），接口保留16套扩展
7. **CLI 可运行**（`run_spectate --seed 42`），先不做 React UI
8. **发言策略摘要**（`strategy_summary`），不展示原始推理
9. **像素小人** → v1.2
10. **记忆系统** → v2

## 固定规则（务必严格实现）

| 规则 | 值 |
|------|----|
| 胜利 | 屠边：狼全灭=好人胜；狼≥好人=狼胜 |
| 夜晚顺序 | 狼人刀人→预言家验人→女巫行动→天亮 |
| 女巫解药 | 1次，首夜可自救，首夜知道刀口 |
| 女巫毒药 | 1次，可与解药同夜使用 |
| 投票平票 | 重投一次，仍平票→无人出局 |
| 遗言 | 首夜被杀+白天被投出→有遗言 |
| 发言 | 每人≤3次/轮，≤200字/次 |

## 验收标准

- [ ] 固定 seed 跑完 1 局 9 人 AI vs AI
- [ ] 生成 `games/<game_id>.events.jsonl`（10种事件齐）
- [ ] 3 个单元测试：胜负判定、投票结算、夜晚结算
- [ ] 1 个 e2e 脚本：`run_spectate_game --seed 42`
- [ ] 同一 seed 产生相同对局

## 项目结构

```
D:\agent session\wolf-agent\
├── src/engine/          ← LangGraph 状态机 + 规则
├── src/agents/          ← MBTI prompt + Agent 封装
├── src/events/          ← Canonical Event Log
├── src/cli/             ← CLI 入口
├── tests/               ← ≥3 单元测试 + 1 e2e
├── games/               ← 对局日志输出
├── requirements.txt
└── README.md
```

## 数据流

```
Agent 发言 → event_log.append(message_posted)
                     ↓
Agent 行动 → event_log.append(action_submitted)
                     ↓
投票       → event_log.append(vote_cast)
                     ↓
结算       → event_log.append(vote_resolved / player_eliminated / game_ended)
```

所有 UI、统计、回放都只读 `.events.jsonl`，不从其他源派生。

## 原 Design Spec 说明

原始完整设计在 `design-spec-wolf-agent-platform.md`（含 v1.1/v2 全部功能），但 **v1 只需实现 v1.1 版本**。v2 功能已全部移出交付范围。
