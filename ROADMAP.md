# Wolf Agent 开发路线图

## 当前状态：v2.2-alpha ✅（Codex 复审通过）

v2.2 是一个"跑完再回放"的游戏验证页面。用户在网页上点开始→选参数→等跑完→自动进入回放。

## 架构速览

```
wolf_agent/
├── web.py              Flask 后端（API + run job + 回放聚合）
├── engine/game.py      游戏引擎（LangGraph 状态机，12 阶段，_build_and_run 是入口）
├── cli/main.py         CLI 入口 + StubLLM（16人格 mock）
├── agents/
│   ├── agent.py        Agent 类（玩家，组合 LLM + personality + memory）
│   ├── llm.py          LLMClient（DeepSeek API 调用）
│   └── personality.py  16 SBTI 人格模板（talk/aggression/trust/lie/independence）
└── events/
    └── __init__.py     EventLog（append-only JSONL，每次 flush）

web/
└── index.html          Vue 3 单文件前端（600+行，待拆分）

关键 API：
  POST /api/runs             创建批量游戏（后台线程）
  GET  /api/runs/<id>        轮询进度
  GET  /api/games/<id>/replay  回放聚合数据
```

## v2.3 要做什么

### P0：真正实时观战

**问题：** `_build_and_run(initial)` 是同步阻塞函数，跑在后台线程里 3-8 分钟不返回。v2.2 只能显示 loading，跑完再加载回放。

**已尝试的失败方案：**
- monkey-patch EventLog.append → 写入时更新 RUNS dict，前端轮询 `/live`。失败了，因为在函数返回前外部看不到事件时序。
- 捕获 stdout → LiveStream(StringIO)。同样失败，stdout 只在函数返回后可用。

**Codex 推荐的 v2.3 方案：EventLog observer/sink**

```
EventLog 写入事件 → 通知 observer → observer 推送给前端
```

不改 game.py 的同步控制流，只在 EventLog 层挂 observer。前端用 SSE 接收事件流，逐事件更新棋盘状态。

**入口文件：** `wolf_agent/events/__init__.py` 的 `EventLog.append()` 方法（line 69），每次写入都 `flush()`。

### P1：回放时间轴播放

当前回放是静态的（选轮次→看该轮所有消息）。需要：
- 播放/暂停/加速按钮
- 逐事件推进：角色揭晓 → 首轮发言 → 投票 → 出局 → 遗言 → 下一轮
- Canvas 棋盘随事件变化（玩家高亮、死亡标记、角色色环）

### P1：Real 模式体验

- 当前 9 人局约 5-8 分钟
- Real 模式下 LLMClient 串行调用 API，可考虑并行（多个玩家的发言可以同时调）
- 添加流式输出（SSE/WebSocket）显示"正在等待 3号发言..."
- 运行中取消按钮（当前无法中断）

### P2：记忆系统可视化

- 结算页已显示单局 reflection 文本
- 需要跨对局视图：同一人格在多局中的参数漂移
- 记忆强度曲线、人格对阵胜率

### P2：前端拆分

`web/index.html` 已 600+ 行，建议拆为：
```
web/
├── index.html    （纯 HTML 结构）
├── app.js        （Vue 3 所有 JS 逻辑）
└── styles.css    （所有 CSS）
```

## 技术债

| 项目 | 说明 |
|------|------|
| EventLog monkey-patch | v2.2 已回退，v2.3 重做时用 observer 模式，不要 monkey-patch |
| `/api/runs/<id>/live` | v2.2 已删除，v2.3 重做时用 SSE 替代轮询 |
| `web.py` run_batch_games | 当前用 `try/finally` 保护 LLMClient，干净但需要锁 |
| games/ 目录 | 已在 .gitignore，不要提交生成数据 |
| start.ps1 | 不含 API key，用户需设 `$env:DEEPSEEK_API_KEY` |

## 开发环境

```powershell
# Python 3.12（不要用 3.14，Flask 装在 3.12）
$PY = "C:\Users\24485\AppData\Local\Programs\Python\Python312\python.exe"

# 启动（Stub 模式，免费快速）
& $PY -m wolf_agent web --port 5001

# 启动（Real 模式，需要 DeepSeek API key）
$env:DEEPSEEK_API_KEY = "sk-xxx"
& $PY -m wolf_agent web --port 5001
```

## 验证命令

```powershell
# 编译检查
& $PY -m py_compile wolf_agent\web.py

# 导入检查
& $PY -c "from wolf_agent.web import app; print(app.name)"

# 前端 JS 语法检查
node --check web\index.html   # 或提取 inline script 后检查
```

## 设计文档

`D:\agent session\2026-05-23_wolf-agent-v2-SBTI-Design-Spec\`

| 文件 | 内容 |
|------|------|
| `design-spec-wolf-agent-v2.2-game-page.md` | v2.2 设计规格 |
| `handoff-to-claude-code-wolf-agent-v2.2-game-page.md` | 实现交付单 |
| `handoff-to-codex-v2.2-live-streaming-issue.md` | 实时方案的根因分析+四种方案对比 |
| `codex-final-review-wolf-agent-v2.2-game-page.md` | Codex 审查意见 |
| `codex-p1-p2-fixes.md` | 审查修复记录 |
| `feature-report-v2.2-final.md` | 最终功能报告 |

## Codex 审查记录

- 初查：P1 memory 类型不匹配、P1 API key 泄露、P2 strategy_summary 字段错误
- 修复：commit 24c284b
- 复审：通过 ✅
