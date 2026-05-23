# Wolf Agent — 路线图

> 写给接力的朋友：这是当前状态和后续计划，取长补短，别踩我们踩过的坑。

---

## 当前版本：v2.2（✅ 已完成，2026-05-23）

**仓库：** `github.com/1ain0516/wolf-agent` | **分支：** master

### 已实现功能

| 模块 | 内容 |
|------|------|
| 后端 API | `POST /api/runs` + `GET /api/runs/<id>` 异步 run job；`GET /api/games/<id>/replay` 回放聚合 |
| StubLLM | 16 人格各 5 条独立发言模板，不自刀/自投，人格化遗言 |
| 遗言机制 | 所有死亡触发（夜杀+票出），死亡 Agent 传入记忆，Real 模式 LLM 生成 |
| Pure 隔离 | try/finally 恢复 LLMClient，stub run 后 real run 不继承 StubLLM |
| 前端三栏 | 左侧进度+结果卡 / 中间棋盘+loading / 右侧回放面板（白天/夜晚/结算） |
| SBTI 显示 | Canvas 棋盘人格名+角色色环；消息流角色标签+人格标签 |
| States | idle / running / completed / partial_success / failed |
| 双模式 | Stub（1-50局，瞬间）/ Real（1-5局，5-8分钟/局，需 DEEPSEEK_API_KEY） |
| 启动 | 桌面脚本 `WolfAgent-启动.ps1`，默认端口 5001 |

### 已知限制

- **无真正实时**：`_build_and_run` 同步阻塞，v2.2 选方案 F（loading + 完成后回放）
- **单活跃 run**：内存 RUNS dict，HTTP 409 防并发，重启丢失
- **无持久化队列**：批量 run 靠后台线程，没有任务队列

### 关键提交

```
24c284b fix: P1 memory player_id 类型不匹配 + 删明文key + P2 strategy_summary
c291f4c fix: 白天显示投票出局玩家 + 从vote_cast计算票数
4eda6bb feat: 遗言机制 — 人格化 + 记忆感知
df6480f fix: StubLLM 重写 — 16人格独立发言 + 修复自刀/投票逻辑
```

---

## v2.3 计划：真正实时回放

### 目标

把 v2.2 的"loading → 完成后一次性回放"升级为运行中可观测。

### 核心思路

```
方案 F (v2.2):  _build_and_run() 同步阻塞 → 跑完 → 前端一次加载 ×
方案 v2.3:     EventLog observer/sink → 事件增量推送 → 前端实时渲染
```

### 技术关键点

1. **observer 层**：在 EventLog 写入时触发回调，拿到每个事件
2. **推送协议**（待定）：SSE（简单）/ WebSocket（双向）/ 增量 JSONL 轮询
3. **前端增量渲染**：收到新事件 → 追加到回放面板，不等全部跑完
4. **RUNS dict 持久化**：从内存 dict 改为可持久化 + 可队列的设计

### 预估

- 推送层：2-3h
- 前端增量渲染：2-3h
- 持久化队列：1-2h
- **总计：~6-8h**

### 踩坑预警

- observer 只解决"何时拿到事件"，不解决"前端怎么增量渲染"——推送协议必须提前确定
- 不能做完 observer 就算"实时"——没有推送层的话跟 v2.2 没区别

---

## v2.4 想法（未定案）

- 玩家隐私模式（隐藏对方角色，非上帝视角）
- 事件逐条播放 + 时间轴拖拽
- 狼人杀规则变种（更多角色、不同人数）
- 小程序迁移（Taro/uni-app）

---

## 架构约定（不要改这些）

| 约定 | 说明 |
|------|------|
| 代码放 `D:\agent project\wolf-agent\` | 不动 |
| 设计文档放 `D:\agent session\` | 不动 |
| 端口 5001 | 5000 有历史残留 POST 405 |
| games/ 整目录 gitignore | 含 memories.jsonl、events.jsonl 等 |
| `--stub` 隐含 `--no-memory` | mock 反思无意义 |
| 16 人格字段统一 `personality` | 不是 mbti 也不是 sbti |

---

## 开发流程

```
Hermes（设计/决策）→ Codex（预审）→ 修改 → handoff → 实现
```

- Hermes 出 Design Spec，不写代码
- Codex 预审找坑，Approve 后进实现
- 实现完成后 Codex 复审

---

*最后更新：2026-05-23*
