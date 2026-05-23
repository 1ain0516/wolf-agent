# Wolf Agent 开发路线图

## 当前状态：v2.2-alpha ✅

- 批量 run job（POST /api/runs + 轮询）
- 回放聚合端点（GET /api/games/<id>/replay）
- 三栏游戏验证页面（左进度+结果卡，中棋盘/loading，右白天/夜晚/结算回放）
- StubLLM：16人格独立发言 + 不自刀 + 人格化遗言
- Real 模式：DeepSeek API 驱动，LLM 自由发言
- 遗言机制：夜杀+票出均触发，人格+记忆感知
- SBTI 人格标签：Canvas 棋盘 + 消息流双显示

## 下一步：v2.3-beta

### 1. 真正实时观战（P0）

当前 _build_and_run 同步阻塞，v2.2 只能用 loading + 完成后回放（方案F）。
v2.3 方案：EventLog observer/sink 模式，挂载 observer 逐事件推送。

### 2. 时间轴自动播放

回放面板增加播放/暂停/速度控制，逐事件推进棋盘状态。

### 3. 运行中取消 + Real 模式优化 + 记忆可视化

### 4. 浏览器 QA 体系化（Playwright）

## 技术债

- web/index.html 超 600 行，建议拆分为 app.js + styles.css
- games/ 目录需加入 .gitignore
- start.ps1 不含 API key，用户需自行设置环境变量

## 关键文件

| 文件 | 作用 |
|------|------|
| wolf_agent/web.py | Flask 后端 |
| wolf_agent/engine/game.py | 游戏引擎状态机 |
| wolf_agent/cli/main.py | CLI + StubLLM |
| wolf_agent/events/__init__.py | EventLog（实时方案入口） |
| web/index.html | Vue 3 前端 |
