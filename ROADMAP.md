# Wolf Agent 开发路线图

## 当前状态：v2.3-alpha ✅（Codex 终审通过）

v2.3 实现了真正的实时观战——SSE 推送游戏事件，Canvas 像素小人逐事件更新棋盘，时间轴可拖拽回放。支持 Stub（免费快速）和 Real（DeepSeek API）两种模式。

## 架构速览

```
wolf_agent/
├── web.py              Flask 后端（SSE 实时流 + run job + 回放 + API key 传递）
├── engine/game.py      游戏引擎（LangGraph 12 阶段 + progress 事件 + observer 注入）
├── cli/main.py         CLI + StubLLM（16人格 mock，可配置延迟）
├── agents/
│   ├── agent.py        Agent 类（玩家）
│   ├── llm.py          LLMClient（DeepSeek，空 key 校验）
│   └── personality.py  16 SBTI 人格模板
└── events/
    └── __init__.py     EventLog + BroadcastObserver（SSE 广播 + 断线续传 + 终态错误）

web/
└── index.html          Vue 3 单文件（实时观战 + 像素小人 + 时间轴播放器 + 进度显示）

tests/
├── test_events.py          BroadcastObserver 订阅者补发测试
└── test_real_mode_config.py  API key 校验测试
```

关键 API：
```
POST /api/games/live           启动单局实时游戏（返回 game_id + stream_url）
GET  /api/games/<id>/stream    SSE 实时事件流（?last_event_id= 断线续传，?delay_ms= 事件间隔）
GET  /api/games/<id>/events    完整事件数组（供时间轴回放）
GET  /api/games/<id>/status    游戏状态（running / finished）
GET  /api/games/<id>/replay    回放聚合数据
POST /api/runs                 批量游戏（后台线程）
GET  /api/runs/<id>            批量进度
```

## v2.3 已完成

### P0：实时观战 ✅
- BroadcastObserver 多客户端广播，线程安全
- EventLog.add_observer() / remove_observer()
- _build_and_run 接受 observer 注入，CLI 零改动
- SSE /stream 端点：30s 心跳、game_end 哨兵、game_error 错误推送
- 前端 SSE EventSource 实时消费 reduceEvent 纯函数

### P1：像素小人 ✅
- 4 角色模板（狼人/预言家/女巫/村民），变宽字符串，32×40 包围盒
- 9 种发色，逐像素 Canvas 绘制
- 状态动画：发言呼吸光效、死亡灰度+飘浮、夜晚暗化

### P1：时间轴回放 ✅
- 播放/暂停/前进/后退/拖拽跳转
- 0.5x / 1x / 2x / 4x 变速
- 拖拽期间冻结播放（onDragStart/onDragMove/onDragEnd）
- 进度条：阶段标记 + 事件标记点
- 键盘快捷键：Space / ←→ / 1-4 / Home / End

### P1：Real 模式进度可见 ✅
- `progress` 事件类型：每次 LLM 调用前推送进度
- 覆盖全部阻塞点：狼人讨论/刀人/预言家查验/女巫行动/发言/辩论/投票/遗言/复盘
- 狼人击杀目标公开可见（`wolf_kill_decision`）
- 前端顶部实时显示当前行动，不进入消息流
- API key 可在 Web 界面设置，localStorage 持久化，不写环境变量

### 消息面板增强 ✅
- 白天/夜晚/系统 分栏 tab
- SBTI 人格徽标（掌控者/伪人/小丑...）
- 自动滚到底
- `game_end` 后自动加载 replay 切时间轴（最多重试 5 次）

### Stub 模式优化 ✅
- StubLLM 可配置延迟（默认 0.3s/次），一局约 40 秒
- 事件节奏可见，适合调试验证

### 测试 ✅
- 38 passed（33 原有 + 5 新增）

---

## 还没做（Claude Code 后续任务）

### P2：Token 级流式输出
**当前状态：** `progress` 事件只在 LLM 调用前推送一次，不实时更新发言内容。
**目标：** 修改 `LLMClient._call()` 支持 streaming response，逐 token 推送 `message_delta` 事件。玩家发言在 LLM 生成过程中逐字出现，不需要等返回。

**涉及文件：**
- `wolf_agent/agents/llm.py` — `_call()` 改为流式，增加回调/生成器
- `wolf_agent/engine/game.py` — `_build_day_context` 附近的 speak/vote 调用链
- `wolf_agent/events/__init__.py` — 新增 `message_delta` 事件类型
- `web/index.html` — `reduceEvent` 新增 `message_delta` case，消息气泡增量更新

### P2：批量运行实时观战
**当前状态：** `/api/runs` 批量路径用 `run_batch_games`，无 observer，无 SSE。
**目标：** 批量模式下每局也注入 BroadcastObserver，前端可选择观战当前运行的游戏。

**涉及文件：**
- `wolf_agent/web.py` — `run_batch_games` 中为每局创建 observer
- `web/index.html` — 批量模式下显示"当前正在运行"的游戏卡片

### P2：记忆系统可视化
- 结算页已显示单局 reflection 文本
- 需要跨对局视图：同一人格在多局中的参数漂移
- 记忆强度曲线、人格对阵胜率

### P2：前端拆分
`web/index.html` 已 1000+ 行，建议拆为：
```
web/
├── index.html    （纯 HTML 结构）
├── app.js        （Vue 3 所有 JS 逻辑）
└── styles.css    （所有 CSS）
```

### v2.4+：玩家视角（不做）
- 需要服务端过滤 SSE 流（防止 DevTools 看到其他玩家信息）
- 预留接口：`/stream?player_id=3`
- **当前仅支持上帝视角**

### v2.5+：TTS（不做）
- 语音播报发言内容

---

## 技术债

| 项目 | 说明 |
|------|------|
| EventLog 注入 | 已用 observer 模式，不要回退到 monkey-patch |
| `/api/runs/<id>/live` | 已废弃，使用 SSE `/api/games/<id>/stream` |
| `web.py` run_batch_games | 用 `try/finally` 保护 LLMClient |
| games/ 目录 | 已在 .gitignore，不要提交生成数据 |
| API key 管理 | Web 界面输入 + localStorage 持久化，不存入仓库 |
| `.codegraph/` | 本地索引，不提交 |

## 开发环境

```powershell
# Python 3.12（不要用 3.14）
$PY = "C:\Users\24485\AppData\Local\Programs\Python\Python312\python.exe"

# Stub 模式（免费，实时可见）
& $PY -m wolf_agent web --port 5000

# Real 模式：在浏览器 http://localhost:5000 设置里填 API Key，不需要设环境变量
```

## 验证命令

```powershell
& $PY -m pytest tests/ -q          # 38 tests
& $PY -m compileall -q wolf_agent   # Python compile check
node -e "const s=require('fs').readFileSync('web/index.html','utf8');const m=s.match(/<script>([\s\S]*)<\/script>/);new Function(m[1]);console.log('OK')"  # JS syntax check
```

## 设计文档

`D:\agent session\2026-05-24_wolf-agent-v2.3-design\`

| 文件 | 内容 |
|------|------|
| `design-spec-v2.3-P0-realtime-spectator.md` | 实时观战设计 |
| `design-spec-v2.3-P1-pixel-sprites.md` | 像素小人设计 |
| `design-spec-v2.3-P1-timeline-playback.md` | 时间轴回放设计 |
| `handoff-v2.3-to-claude-code.md` | v2.3 实现 handoff |
| `implementation-report-v2.3.md` | 实现报告 |
| `codex-final-review-v2.3.md` | Codex 终审报告 |
| `post-codex-fixes-report.md` | 终审修复报告（12 项） |
| `codex-realtime-progress-fix-report.md` | Codex progress 事件修复报告 |
