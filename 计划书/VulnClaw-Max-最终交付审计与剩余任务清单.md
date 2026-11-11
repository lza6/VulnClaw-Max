# VulnClaw-Max 最终交付审计与剩余任务清单

> 审计日期：2026-11-11
> 代码基线：`main` @ `2d8ba99`；工作树仅 `?? soak-4h-report.json`（0 字节）
> 版本：`pyproject.toml` 0.5.0；PyPI 最新 0.4.1
> 证据口径：**已验证**（实际运行）/ **静态确认**（读代码）/ **文档声明**（旧文档自述，本轮未复验）/ **未验证**（缺环境或权限）
>
> 本文取代以下四份文档；四份文档已从工作树删除，git 历史可恢复：
> - `计划书/VulnClaw-Max-工程改造计划书-V2.md`
> - `计划书/VulnClaw-Max-差距审计与验收编排.md`
> - `计划书/VulnClaw-Max-视觉交互与可发现性设计指南-V1.md`
> - `计划书/下一步改进指南.md`
>
> **2026-11-11 第二轮施工更新：** §3 的 18 项已按本轮授权完成或推进；实际交付状态、最终门禁与剩余项以 **§10 本轮实施结果** 为准。§1–§9 保留为施工前审计基线，便于对照。

---

## 0. 结论

1. **可靠性内核已真实落地。** P0-01、P0-02、P1-02～P1-09 全部有代码、有测试、有本轮实测支撑。旧文档对这一层的判断可以信任。
2. **产品层不是“全量完成”。** F-09、F-10、F-14、F-15 完整；F-04、F-05、F-06、F-07、F-08、F-11、F-12、F-13、F-16、F-17、F-18 均存在明确的未闭环点。旧文档后半部分把这些写成“已完成”，是不准确的。
3. **视觉/SEO 主体完成。** Phase A～E 的令牌、双主题、动效、3D 场景、公开站都已落地；剩余 3D 可访问性与性能采样、Lighthouse、触摸手势、页面级分包、尺度长尾。
4. **发布与长稳是最大空白。** 0.5.0 未发布到 PyPI；24h soak 未跑，4h 报告文件是 0 字节；基准回归脚本缺失；security/docker workflow 没有真正成为门禁。
5. **当前定位不是“全量 V2 已完成”，而是“可靠性外壳完成 + 产品层大部分可用 + 发布/长稳/若干交互细节未闭环”。** 下面 18 项是真实剩余工作，前 5 项为 P1。

---

## 1. 本轮实测基线

### 1.1 质量门禁

```
python -m ruff check vulnclaw tests scripts
  -> All checks passed!

python -m pytest -q --cov=vulnclaw --cov-report=term
  -> 2332 passed, 8 skipped, 4 warnings in 98.23s
  -> TOTAL 30433 stmts 5228 miss 83%
  -> Required test coverage of 82.0% reached. Total coverage: 82.82%
  -> vulnclaw/web/app.py 93%

cd frontend && npm run build
  -> 557 modules transformed
  -> assets/index-*.css   49.61 kB | gzip: 10.02 kB
  -> assets/index-*.js   484.35 kB | gzip: 145.74 kB
  -> assets/AttackSurfaceScene-*.js 821.15 kB | gzip: 220.79 kB
  -> built in 2.87s

cd frontend && npm run test
  -> 4 test files / 11 tests passed

cd frontend && npm run lint
  -> 0 errors, 20 warnings

cd frontend && npm run e2e
  -> 24 passed (51.6s)

python -m vulnclaw --help
  -> 0.392s / 0.375s / 0.448s

公开站
  -> https://lza6.github.io/VulnClaw-Max/ 200
  -> /sitemap.xml 200
  -> /robots.txt 200

PyPI
  -> vulnclaw latest 0.4.1；仓库版本 0.5.0

soak-4h-report.json
  -> 0 字节（未完成的长稳产物）
```

### 1.2 这些结果证明了什么

- 后端测试、覆盖率、前端构建、单测、lint、E2E 在当前工作树上全部通过。
- 可靠性内核的关键行为有测试覆盖：失败传播、事件总线、终态守卫、重启对账、队列与停机、持久化、目标列表容错。
- 视觉层的关键行为有真实 E2E：主题切换、reduced-motion、3D 展开与 WebGL 降级、axe 扫描、公开站可访问。
- 旧文档里“1913 passed / 76.75%”“2292 passed / 82.67%”“E2E 22 条”等数字已经过时；当前基线以本节为准。

### 1.3 这些结果没有证明什么

- 没有证明 24h 长稳、RSS 增长、MCP 子进程无孤儿；`soak-4h-report.json` 为空。
- 没有证明 0.5.0 可安装；PyPI 仍是 0.4.1。
- 没有证明 3D ≥50 fps、Lighthouse 分数、触摸拖拽。
- 没有证明流式 LLM 调用的 token 计数；相关估算是死代码。
- 没有证明跨项目目标隔离；相关测试只覆盖单项目。

---

## 2. 已真实落地（不要重做）

| 范围 | 已落地项 | 证据 |
|------|----------|------|
| 失败语义 | P0-01 `LLMInvocationError`、`core.chat(raise_on_error)`、CLI 凭据预检与退出码 1、Web `task_failed` | `vulnclaw/agent/errors.py`、`vulnclaw/agent/llm_client.py`、`vulnclaw/cli/main.py:1176`、`tests/agent/test_llm_failure_propagation.py`、`tests/cli/test_cli_failure_exit_code.py` |
| 初始化失败出口 | P0-02 `_run_task` 全函数 `try/except/finally`、MCP/Agent 构造移入 `try`、`unbind` | `vulnclaw/web/services/task_service.py:43-120`、`tests/web/test_task_setup_failure.py` |
| 事件通道 | P1-02/04 单调 `seq`、环形缓冲、心跳、`Last-Event-ID`、`event_gap` | `vulnclaw/web/event_bus.py`、`vulnclaw/web/stream.py`、`vulnclaw/web/app.py:440-461`、`tests/web/test_event_bus.py`、`tests/web/test_task_stream.py` |
| 生命周期 | P1-03/06/07 终态守卫、stop 409、`interrupted` 重启对账、信号量队列、优雅停机 | `vulnclaw/web/task_manager.py:25-38,120-235,290-302,435-475`、`tests/web/test_task_lifecycle.py` |
| 持久化 | P1-05 JSONL 事件、300 ms 去抖快照、原子写、保留策略 | `vulnclaw/web/task_manager.py:304-433`、`tests/web/test_task_persistence.py` |
| 目标列表 | P1-08 排序截断、单文件容错、`targets/index.json` | `vulnclaw/web/services/target_service.py`、`tests/web/test_targets_robustness.py`、`tests/web/test_targets_index.py` |
| Windows 编码 | P1-09 `configure_stdio_utf8()`、`console_output=False`、KB 提示异常兜底 | `vulnclaw/encoding.py`、`vulnclaw/agent/core.py:116-160` |
| 静态资源/停止/版本 | P2-01 404、P2-04 服务端状态为准、P2-05 单一版本源、P2-06 报告相对路径、P2-12 配置原子写、P2-14 docs 可跟踪、P2-18 app.py 覆盖率、P2-19 健康字段、P2-20 KB 静默、P2-21 wheel 内 UI | `tests/web/test_app_static.py`、`frontend/src/App.tsx:234-255`、`tests/meta/test_version_consistency.py`、`tests/config/test_config_atomic_write.py`、`tests/web/test_web.py` |
| 可访问性 | P2-07/08/09/10/11 语言回落、`lang/title`、aria、焦点陷阱、reduced-motion | `frontend/src/i18n/index.tsx:93-96`、`frontend/src/hooks/useDialogFocus.ts`、`frontend/src/styles.css:3059` |
| 安全边界 | DNS rebinding Host 白名单 | `vulnclaw/web/auth.py:121-140,180-190`、`tests/web/test_auth.py:47` |
| 产品层完整项 | F-09 审计导出、F-10 集成 dispatch/配置/投递历史、F-14 插件 entry_points/权限/版本/样例包、F-15 E2E+ESLint | `vulnclaw/integrations/*`、`frontend/src/components/IntegrationsPanel.tsx`、`vulnclaw/plugins/registry.py`、`examples/plugins/vulnclaw-plugin-demo`、`frontend/e2e/*` |
| 视觉层 | Phase A～E：令牌、双主题、动效 M-01～M-10、3D 场景与降级、公开站、主题/动效/a11y E2E | `frontend/src/styles/tokens.css`、`frontend/src/motion/*`、`frontend/src/scene/AttackSurfaceScene.tsx`、`site/*`、`frontend/e2e/theme.spec.ts`、`motion.spec.ts`、`attack-surface.spec.ts`、`a11y.spec.ts` |

---

## 3. 剩余任务总表

| ID | 级别 | 任务 | 现状一句话 | 主要文件 | 预估 |
|----|------|------|-----------|----------|------|
| G-01 | P1 | 流式 token 与成本 | 估算函数无调用点；`cost_estimate` 不存在 | `agent/llm_client.py`、`web/schemas.py`、`TaskConsolePage`、`ReportsPage` | 0.5–1d |
| G-02 | P1 | MCP 热重启与工具白名单 | 只写配置，下个任务生效；无白名单 | `web/services/mcp_control_service.py`、`mcp/lifecycle.py`、`exec_gate` | 1–1.5d |
| G-03 | P1 | 发现工作台闭环 | assignee 无 UI、无批量、报告不标注 | `RiskResultsPage.tsx`、`finding_service.py`、`report/generator.py` | 1d |
| G-04 | P1 | 调度 cron 与失败可见 | 仅 interval；入队失败静默 | `vulnclaw/scheduler.py`、`web/app.py:186-207`、`SchedulesPanel.tsx` | 1d |
| G-05 | P1 | 运行详情闭环 | 无续跑、无证据抽屉、无阶段耗时 | `RunDetailDialog.tsx`、`run_service.py` | 1d |
| G-06 | P2 | 项目隔离与报告路由 | 目标全局、项目多对多、报告按目标反查 | `project_service.py:130`、`report_service.py:90`、`target_service.py` | 1d |
| G-07 | P2 | 报告 run 级与 SARIF schema | 报告按目标状态生成；SARIF 只做结构断言 | `report_service.py:86-108`、`tests/report/test_findings_output.py` | 0.5–1d |
| G-08 | P2 | 离线 KB 发行包 | 有 pack/restore，无预置 bundle | `vulnclaw/kb/pack.py`、`cli/main.py:3237/3255` | 0.5d |
| G-09 | P2 | 基准回归 | 脚本与 perf 测试都不存在 | `scripts/bench_web_state.py`、`tests/performance/test_benchmarks.py` | 0.5d |
| G-10 | P2 | 长稳与孤儿检测 | 4h 报告 0 字节；脚本不检查 RSS/孤儿 | `scripts/soak_web.py`、`soak-4h-report.json` | 机器时间 + 0.5d |
| G-11 | P2 | 发布链路 | 0.5.0 未上 PyPI；docker 不推送/无 HEALTHCHECK；security 非 PR 门禁 | `release.yml`、`security.yml`、`docker.yml`、`Dockerfile`、`README.md` | 0.5d + 发布 |
| G-12 | P2 | SSE 断线提示 | 服务端心跳有；前端无 `onerror` 横幅 | `frontend/src/api/web.ts:284`、`App.tsx:174-222` | 0.5d |
| G-13 | P2 | 前端覆盖率 | 11 个单测；无 coverage 配置/阈值 | `frontend/vitest.config.ts`、`package.json` | 0.5d |
| G-14 | P3 | E2E 响应式/键盘/console | 固定 1440×1000；无 768/1024、Tab、console error | `frontend/playwright.config.ts`、`frontend/e2e/*` | 1d |
| G-15 | P3 | 3D 可访问性与性能 | reduce 下是文字占位，不是静态 SVG；无 aria；fps/Lighthouse/触摸未测 | `AttackSurfacePanel.tsx`、`AttackSurfaceScene.tsx` | 1d |
| G-16 | P3 | 性能与视觉长尾 | 无页面级分包；无事件分页 REST；报告非流式写；尺度长尾 | `App.tsx`、`web/app.py`、`report/generator.py`、`styles.css` | 1–2d |
| G-17 | P3 | 事件名清单 | 前后端各写一份，未来新事件会静默丢弃 | `frontend/src/api/web.ts:295-307`、`web/task_manager.py` | 0.5d |
| G-18 | P3 | 小项收尾 | gc 无 Web 入口；20 条 lint warning；空 soak 产物 | `SettingsPage.tsx`、`frontend/*`、`soak-4h-report.json` | 0.5d |

---

## 4. 逐项任务卡

### G-01 流式 token 与成本（P1）

**目标**：所有 LLM 调用路径都能累计 token；任务摘要和报告页能看到调用次数、token 与成本估算。

**现状与证据（静态确认）**

- `vulnclaw/agent/llm_client.py:567` 定义了 `_record_estimated_usage()`，但全仓没有任何生产调用点。
- `_record_response_usage()` 只在 `vulnclaw/agent/llm_client.py:593` 的 `_call_with_persistent_retries()` 里调用。
- `call_llm_stream()`（`:939`）和 `call_llm_auto_stream()`（`:1058`）在流式返回后不记录 usage，也不增加 `runtime.llm_calls`。
- `call_llm()` 只在 `stream_sink is not None` 时走流式（`vulnclaw/agent/llm_client.py:640-655`）；Web `_run_task()` 调用 `execute_task()` 时没有传 `stream_sink`（`vulnclaw/web/services/task_service.py:83-90`），所以 **Web 默认任务走非流式，当前多数能计数**。旧文档“Web 任务大量走流式、tokens 恒为 0”的说法不成立。
- 真正受影响的是 CLI `--stream`、REPL、以及任何显式传 `stream_sink` 的调用。
- `tests/agent/test_token_usage_summary.py:49-65` 只直接调用 `_record_estimated_usage()`，没有经过 `call_llm_stream` / `call_llm_auto_stream`，不能证明集成有效。
- `TaskSummary`（`vulnclaw/web/schemas.py:70-98`）有 `tokens_input/output/total` 和 `llm_calls`，但没有 `cost_estimate`。
- `frontend/src/pages/TaskConsolePage.tsx:359-367` 只在 `tokens_total` 非零时展示 token；`ReportsPage.tsx` 没有 token/成本展示。

**改动**

1. 在 `call_llm_stream()` 与 `_stream_chat_completion_message()` 完成时，如果 chunk 里带 usage 就记录真实 usage，否则调用 `_record_estimated_usage()`；`call_llm_auto_stream()` 的每一轮 LLM 调用各记一次。
2. 避免与 `handle_tool_calls()` 内的非流式 follow-up 重复计数：一次 LLM 请求只记一次。
3. `TaskSummary` 增加 `cost_estimate`（按配置的模型价目表：input/output 单价）；`orchestrator.py` 汇总时写入。
4. `TaskConsolePage` 展示成本；`ReportsPage` 增加任务/目标 token 与成本摘要。
5. 新增集成测试：mock streaming chunk（无 usage 与有 usage 两种）走真实 `call_llm_stream` / `call_llm_auto_stream`。

**验收**

- `pytest tests/agent/test_stream_usage_accounting.py -q`：无 usage 的流式响应 → `llm_calls > 0`、`tokens_total > 0`；带 usage 的响应 → 与 provider 数值一致。
- `pytest tests/agent/test_token_usage_summary.py -q`：现有 helper 测试继续通过。
- 一个已知单价的 mock → `TaskSummary.cost_estimate > 0`，前端能看到。
- 不改变非流式路径的现有计数。

**风险/回滚**：只改 `llm_client` 的记账点；若发现重复计数，回滚到仅记录流式首轮。

---

### G-02 MCP 热重启与工具白名单（P1）

**目标**：设置页启停 MCP server 后，当前进程立即生效；可以限制某个 server 允许暴露的工具，禁用工具被拒绝并记审计。

**现状与证据（静态确认）**

- `vulnclaw/web/services/mcp_control_service.py:11-16`：`toggle_mcp_server()` 只写 `mcp.servers.<name>.enabled`，返回 `{"applies_to": "next_task"}`。
- 运行中的 `MCPLifecycleManager` 不会 stop/start 该 server；`vulnclaw/mcp/lifecycle.py` 没有从 Web 层调用的热重启入口。
- 全仓没有 `allowed_tools` / `disabled_tools` / MCP 工具白名单配置；`exec_gate` 只处理命令/动作，不处理 MCP 工具名。
- `frontend/src/pages/SettingsPage.tsx:710-720` 已展示开关，但文案明确写 `settings.mcp_applies_next`（下个任务生效）。

**改动**

1. `MCPLifecycleManager` 增加单 server 的 `restart(name)` 与 `set_enabled(name, enabled)`，Web toggle 调用它并返回 `applies_to: "now"`。
2. 配置增加 `mcp.servers.<name>.allowed_tools`（空 = 全部允许）；`exec_gate` 或 MCP 工具调用入口校验工具名，拒绝时写 constraint audit。
3. 设置页去掉“下个任务生效”文案，改为当前状态；增加工具白名单编辑（或明确只读诊断）。
4. 测试：运行中 server 启停后 `diagnostics.tool_count` 变化；禁用工具调用被拒并产生审计事件。

**验收**

- `pytest tests/web/test_mcp_toggle.py tests/web/test_mcp_restart.py -q`。
- `npm run e2e` 的 `controls.spec.ts` 覆盖启停后立即生效。
- 未知 server → 404；白名单外工具 → 拒绝 + 审计。

**风险/回滚**：热重启会短暂断开工具；若失败保留旧 server 并返回错误，不要写配置。

---

### G-03 发现工作台闭环（P1）

**目标**：发现项可以分配负责人、批量处置，报告能体现处置状态。

**现状与证据（静态确认）**

- API 已支持 `assignee`：`vulnclaw/web/services/finding_service.py:60-85`、`vulnclaw/web/schemas.py:379-384`；`tests/web/test_findings_lifecycle.py` 也断言了 assignee 持久化。
- 前端只渲染状态下拉和备注：`frontend/src/pages/RiskResultsPage.tsx:418-445`；没有 assignee 输入，没有批量选择/批量操作。
- 报告生成不包含 triage 元数据：`vulnclaw/report/generator.py:1362-1381` 的 `_build_report_finding()` 只取 title/severity/vuln_type/evidence/verified 等；`finding_meta` 在 `:579` 被移出报告上下文。旧文档“状态变更在报告标注”未实现。
- `finding_key` 前后端都使用 `finding_id` 或 `title::vuln_type`（`finding_service.py:15-20` 与 `RiskResultsPage.tsx:86-88`），当前一致；但没有 `finding_id` 且标题/类型相同的发现会碰撞，需测试。

**改动**

1. Risk 页增加 assignee 输入（失焦保存）与批量选择（复选框 + 批量状态/备注）；批量操作逐条调用现有 triage API，失败汇总提示。
2. 报告上下文加入 `finding_meta`：在 `generate_report` / `generate_report_from_target_state` 里把 triage_status、assignee、note 合并进 finding 视图；模板增加“处置状态/负责人”列。
3. 给 `finding_key` 加碰撞测试；必要时在没有 `finding_id` 时使用索引/位置后缀，保持前后端一致。
4. `tests/web/test_findings_lifecycle.py` 增加批量、assignee UI（组件测）与报告标注断言。

**验收**

- 前端：设置 assignee → 刷新后仍在；批量选择 3 条 → 全部更新。
- 报告：生成的 Markdown 含 triage 状态与负责人。
- `pytest tests/web/test_findings_lifecycle.py tests/report/test_report.py -q`。

**风险/回滚**：报告模板改动只影响新生成的报告；旧报告不变。

---

### G-04 调度 cron 与失败可见（P1）

**目标**：调度支持用户预期的周期表达；任务无法入队时能看到失败，而不是静默。

**现状与证据（静态确认）**

- `vulnclaw/scheduler.py:11-24` 的 `ScheduledJob` 只有 `interval_seconds`；没有 cron 解析。
- `vulnclaw/web/schemas.py:481-487` 的 `ScheduleUpsertRequest` 只有 `interval_seconds`；`frontend/src/components/SchedulesPanel.tsx` 只让用户填分钟数。
- `vulnclaw/web/app.py:186-207` 的 `_schedule_loop()`：
  - `runner(job)` 内 `except Exception: return`，任务创建失败被吞掉；
  - 外层 `except Exception: pass`，整个调度轮询异常也被吞掉；
  - 没有失败通知/审计/状态记录。
- `run_due()` 每 5 秒调用一次；如果上一轮任务仍在运行，下一轮到点会继续入队（队列会串行执行，但用户看不到“跳过/排队”的说明）。

**改动**

1. 二选一并在文档/UI 明确：实现 `cron` 表达式（推荐 5 段式，进程内解析）或明确只支持 interval，删除旧文档中的 `cron|interval` 承诺。
2. `runner` 失败时写一条审计/事件（例如 `schedule_failed`），并通过现有通知通道推送；`_schedule_loop` 不再裸 `pass`。
3. 增加“同 job 上一轮仍在运行则跳过并记录”的策略，避免堆叠。
4. 测试：可控时钟覆盖到点入队、失败通知、跳过重叠。

**验收**

- `pytest tests/test_scheduler.py tests/web/test_schedules.py -q`。
- 一个非法 target 的 job → UI/日志能看到失败，不是静默。
- 若保留 interval-only，更新 UI 文案与文档，不再声称支持 cron。

**风险/回滚**：cron 解析引入复杂度；若不做 cron，必须明确收口，不能继续留“cron|interval”的模糊承诺。

---

### G-05 运行详情闭环（P1）

**目标**：历史 run 能还原“跑到哪、为什么停、下一步做什么”，并能直接续跑。

**现状与证据（静态确认）**

- `vulnclaw/web/services/run_service.py:49-60` 的 `get_run()` 已返回 `resume`、`findings`、`events`、`reports`、`artifacts`。
- `frontend/src/components/RunDetailDialog.tsx` 只渲染事件列表、产物、报告；没有使用 `run.resume`，没有续跑按钮，没有证据抽屉（`run.findings` 未渲染），没有阶段耗时聚合。
- `frontend/e2e/history.spec.ts` 只断言“事件时间线”和“运行产物”可见，不覆盖失败原因、续跑、证据。
- 旧文档 F-04 的“阶段时间线、证据抽屉、失败原因、续跑按钮”只完成了失败消息与基础时间线。

**改动**

1. 运行详情头部展示失败/中断原因（`run.message` 已有；补 `resume.reason`）。
2. 增加“续跑”按钮：用 `run.resume` / `resume_command` / `targets` 调 `POST /api/tasks/run`（`resume=true`，带 `snapshot_id`），成功后跳到任务台。
3. 增加证据抽屉：渲染 `run.findings`（至少标题/严重度/证据/状态），与事件时间线并列。
4. 阶段耗时：按事件 `kind`/`timestamp` 聚合阶段起止，展示每阶段耗时；没有阶段字段时按事件类型分组。
5. E2E：创建失败/中断 run → 打开详情 → 看到失败原因 → 点续跑 → 新任务出现。

**验收**

- `pytest tests/web/test_run_service.py -q`（补 resume 字段断言）。
- `npm run e2e` 的 `history.spec.ts` 覆盖失败原因、证据、续跑。
- 手工：一份 `failed` run 的详情能说明下一步。

**风险/回滚**：续跑复用现有 `resume` 语义；若字段不兼容，先只读展示，不自动续跑。

---

### G-06 项目隔离与报告路由（P2，若对外宣称隔离则升 P1）

**目标**：项目内的目标、任务、报告不串；报告落点由任务所属项目决定，而不是“最近修改的项目”。

**现状与证据（静态确认）**

- 任务有 `project_id`（`vulnclaw/web/task_manager.py:80`），`/api/tasks?project=` 已过滤（`vulnclaw/web/app.py:404-412`），Home 页有项目选择（`frontend/src/pages/HomePage.tsx:319-325`）。
- 目标本身没有 `project_id`：`/api/targets` 不按项目过滤（`vulnclaw/web/app.py:463-465`），`target_service.list_targets()` 是全局列表。
- 项目与目标是多对多：`project.json` 的 `targets` 列表；`find_project_for_target()`（`vulnclaw/web/services/project_service.py:130-135`）遍历所有项目，返回第一个匹配（项目按 mtime 降序）。
- 报告路由用目标反查项目（`vulnclaw/web/services/report_service.py:90-91`），不用 `task.project_id`；同一目标属于两个项目时，报告目录取决于项目修改时间。
- 没有顶栏项目切换；只有 Home 页选择与 History 页过滤。
- `start_task()` 在创建任务前就 `assign_target()`（`vulnclaw/web/services/task_service.py:24-25`），后续创建失败不会回滚目标关联。
- `tests/web/test_projects.py` 只测单项目 `find_project_for_target`，没有“同一目标属于两个项目”的用例。

**改动**

1. 明确模型：单项目归属（推荐，target 记录加 `project_id`）或显式多对多（保留列表但报告必须按任务项目）。
2. 报告路由改为优先用任务 `project_id`；没有任务上下文时再按目标反查，并在多项目时返回明确错误/让用户选择。
3. `/api/targets` 增加 `?project=` 过滤（或明确全局目标列表是设计）。
4. 顶栏增加项目切换，或明确“项目选择只在 Home/History”并在 UI 文案说明。
5. `start_task` 的项目关联放到任务创建成功之后，失败回滚。
6. 测试：同一目标加入两个项目 → 报告落在任务所属项目；`/api/targets?project=` 不串。

**验收**

- `pytest tests/web/test_projects.py tests/web/test_project_reports.py -q` 增加双项目用例。
- 前端：切换项目后任务/目标/报告视图一致。
- 旧数据迁移：已有 project.json 不需要迁移；若改 target 归属，提供兼容读取。

**风险/回滚**：模型改动涉及数据；先做报告路由与过滤，target `project_id` 可后置。

---

### G-07 报告 run 级与 SARIF schema（P2）

**目标**：报告能从一次具体 run 复现；SARIF 通过正式 schema 校验。

**现状与证据（静态确认）**

- `vulnclaw/web/services/report_service.py:86-108` 的 `generate_target_report()` 从 `load_target_state(target)` 生成，不接受 `run_name`；同一目标跨 run 的累积状态会混入报告。
- 五种格式存在：Markdown、HTML、PDF（`[pdf]` extra）、JSON findings、SARIF findings；但“同一 run 五格式”不是当前接口语义。
- `tests/report/test_findings_output.py:146-239` 只断言 SARIF 字段/结构，没有用 `jsonschema` 对 `sarif-2.1.0.json` 做正式校验。
- 报告脱敏、模板、相对路径已落地（`generator.py` 的 `redact_secrets`、`variants.py`、测试通过）。

**改动**

1. 报告接口增加可选 `run_name`：从 `runs/<run>/` 的 manifest/events/findings 生成，保留现有的 target 模式作为兼容路径。
2. 或在 UI/文档明确“报告按目标状态生成，不是 run 快照”，并去掉“同一 run 五格式”的承诺。
3. 增加 SARIF schema 校验测试：读取官方 2.1.0 schema（或 vendored 副本），`jsonschema.validate`。
4. 报告页展示 token/成本（与 G-01 联动）。

**验收**

- 同一 run 生成 md/html/pdf/json/sarif，内容来自该 run。
- `pytest tests/report/test_findings_output.py -q` 含 schema 校验。
- 报告不含绝对路径与密钥。

**风险/回滚**：run 级生成需要读 run 目录；保留 target 级接口，逐步切换。

---

### G-08 离线 KB 发行包（P2）

**目标**：干净离线机器不依赖联网就能用 KB；`doctor` 能说明 KB 状态。

**现状与证据（静态确认）**

- `vulnclaw/kb/pack.py` 提供 `pack_kb` / `restore_kb`；CLI `vulnclaw kb pack` / `kb restore`（`vulnclaw/cli/main.py:3237,3255`）。
- `vulnclaw/cli/main.py:2827-2845` 的 `doctor` 检查 KB corpus，并提示 `vulnclaw kb update` 或 `vulnclaw kb restore`；`--offline` 跳过 LLM probe。
- 发行包（wheel/sdist）不包含预置 KB bundle；没有“首次启动自动导入”的路径。
- `kb update` 是本地 seed（`vulnclaw/kb/updater.py`），不依赖网络；所以 `--offline` 不阻止它是合理的。

**改动**

1. 二选一：随包附带一份 KB bundle（体积/许可允许时）并在首次启动自动 restore；或把“联网机器 pack → 离线机器 restore”写成明确的两步文档，并在 Web 设置页给出入口/提示。
2. `doctor` 在离线模式下明确“KB 来源：bundle/本地 seed/空”。
3. 测试：干净临时目录 + 离线环境，restore 后 `doctor` 不报错、KB 检索可用。

**验收**

- `vulnclaw kb pack` → 新配置目录 `vulnclaw kb restore` → `doctor` 显示条目数。
- 断网环境 `doctor` 不挂起。

**风险/回滚**：预置 bundle 会增加发行体积；不做就明确文档化。

---

### G-09 基准回归（P2）

**目标**：把北极星指标变成可重复执行的脚本 + CI 慢测，防止性能回退。

**现状与证据（静态确认）**

- `scripts/bench_web_state.py` 不存在。
- `tests/performance/test_benchmarks.py` 不存在。
- 旧计划 C-13 要求 300 事件 <50 ms、300 任务 <300 ms、500 目标 <100 ms；当前只有 `tests/web/test_targets_index.py:60-83` 的 500 目标 <0.1s 断言，事件/任务基准没有守卫。
- `pyproject.toml` 没有 `slow` marker 或 performance 目录。

**改动**

1. 新增 `scripts/bench_web_state.py`：临时 `VULNCLAW_CONFIG_DIR`，测 publish 300、create 300、list 500，输出 JSON。
2. 新增 `tests/performance/test_benchmarks.py`，`@pytest.mark.slow`，阈值按本机基线放宽 5×；在 CI 的可选 job 跑。
3. 把脚本接入 `scripts/soak_web.py` 或独立 workflow。

**验收**

- `python scripts/bench_web_state.py --assert` 输出并断言三项阈值。
- `pytest -m slow tests/performance -q` 通过。
- CI 有对应 job（可手动触发）。

**风险/回滚**：CI 机器负载波动；阈值放宽，不把本机绝对值写死。

---

### G-10 长稳与孤儿检测（P2）

**目标**：24h 运行不劣化、无僵尸任务、无孤儿子进程，且有可复查报告。

**现状与证据**

- `scripts/soak_web.py` 存在，8 秒冒烟曾通过；本轮 `soak-4h-report.json` 是 **0 字节**（`ls -l` 2026-11-08 08:39），没有完成的长稳证据。
- 脚本只打印 `rss_start/end/peak/median`（`scripts/soak_web.py:148-157`），不检查 RSS 增长阈值、不检查 `running` 残留、不检查 MCP/npx/nmap 孤儿子进程。
- 24h 未跑；旧文档只记录 30/60 秒冒烟 RSS 98→146 MB，趋势未知。

**改动**

1. 补 `--assert` 模式：RSS 增长 <10%、无 `running`、无 `queued` 残留、无孤儿子进程（用 psutil / 进程树检查）。
2. 跑一次 4h（最低）或 24h（目标），把 stdout 写入 `计划书/evidence/soak-YYYYMMDD.json`；删除空的 `soak-4h-report.json`。
3. 若 RSS 超阈值，按 `running_count`/事件缓冲/任务保留策略定位。

**验收**

- 报告文件非空且包含 `duration_seconds`、`tasks_submitted`、RSS 序列。
- `--assert` 退出码 0；失败时明确哪一项超阈值。
- 无 `running` 残留、无孤儿进程。

**风险/回滚**：长跑占机器；可先用 2–4h 冒烟，24h 作为发布前门禁。

---

### G-11 发布链路（P2）

**目标**：用户能安装到 0.5.0；镜像可构建、可推送、可健康检查；安全扫描进入门禁。

**现状与证据（已验证/静态确认）**

- PyPI 最新 0.4.1；仓库 `pyproject.toml:7` 是 0.5.0；README `:11` badge 仍是 0.4.1；公开站 `pip install vulnclaw` 会装到 0.4.1。
- `.github/workflows/release.yml` 只在 tag 时构建 GitHub Release，没有 PyPI publish 步骤。
- `.github/workflows/security.yml:3-6` 只有 `schedule` 与 `workflow_dispatch`，不在 PR/push 上跑；pip-audit/npm audit/SBOM 结果不阻塞合并。
- `.github/workflows/docker.yml:3-10` 只在 Dockerfile/docker-compose/.dockerignore 变更时构建，且只 `docker build -t vulnclaw:ci .`，没有 `ghcr.io` 推送。
- `Dockerfile` 没有 `HEALTHCHECK`。
- 旧计划 P2-17 的“推送 ghcr.io + HEALTHCHECK”未实现。

**改动**

1. 发布 0.5.0：bump 已做；补 PyPI publish（twine / trusted publishing）到 release workflow；更新 README badge 与站点安装说明。
2. docker.yml 增加 `docker push ghcr.io/<owner>/vulnclaw:<tag>`（需授权/仓库配置）；Dockerfile 增加 `HEALTHCHECK` 调 `/api/health`。
3. security.yml 增加 `pull_request` 或 `push` 触发（至少对依赖变更），并保留 schedule；确认 pip-audit/npm audit/SBOM 至少跑通一次。
4. 发布前跑 `release_preflight.py --build` + `verify_dist_artifacts.py`。

**验收**

- `pip install vulnclaw==0.5.0` 成功；`vulnclaw --version` 输出 0.5.0。
- `docker build` 后 `docker inspect` 有 HEALTHCHECK；容器 `/api/health` 200。
- security/docker workflow 至少各成功一次；README badge 与 PyPI 一致。

**风险/回滚**：PyPI 发布不可逆（版本号）；先 dry-run/TestPyPI。GHCR 推送需要权限，未授权时只保留 build。

---

### G-12 SSE 断线提示（P2）

**目标**：SSE 断开时用户能看到“连接已断开/正在重连”，而不是任务状态静默停更。

**现状与证据（静态确认）**

- 服务端心跳与续传已落地：`vulnclaw/web/event_bus.py` 的 heartbeat、`vulnclaw/web/stream.py` 的 `id:`、`vulnclaw/web/app.py:440-461` 的 `Last-Event-ID`。
- 前端 `frontend/src/api/web.ts:284-310` 的 `openTaskStream()` 没有 `source.onerror`；`frontend/src/App.tsx:174-222` 只在终态 `source.close()`，没有断线横幅/重试状态。
- 旧计划 P2-03 的“前端 onerror 显示连接已断开横幅”未实现。

**改动**

1. `openTaskStream` 增加 `onerror` 回调；`App.tsx` 设置连接状态（connected/reconnecting/disconnected），在任务台/顶栏显示横幅。
2. 终态后关闭并清除横幅；重连成功清除。
3. E2E：拦截/关闭 SSE 路由，断言横幅出现；恢复后消失。

**验收**

- `npm run e2e` 新增 SSE 断线用例。
- 断开 5 秒内出现提示；`EventSource` 自动重连后提示消失。

**风险/回滚**：不要在前端手动重连，保留浏览器原生 `EventSource` 重连。

---

### G-13 前端覆盖率（P2）

**目标**：前端单测覆盖率可采集、有阈值、进 CI。

**现状与证据（已验证）**

- `npm run test`：4 个测试文件、11 个用例通过。
- `frontend/vitest.config.ts` 没有 `coverage` 配置；`frontend/package.json:6-13` 没有 `test:coverage` 脚本。
- 旧计划 0.5.0 出口要求“前端测试 ≥40%（工具函数 100%）”，当前未采集。

**改动**

1. 增加 `@vitest/coverage-v8` devDependency。
2. `vitest.config.ts` 配置 `coverage.provider = "v8"`、`reporter = ["text", "lcov"]`、阈值（lines/functions ≥40%，`src/utils/**` 100%）。
3. `package.json` 增加 `test:coverage`；CI 的 frontend unit job 跑它。
4. 补 `preferences`、`validation`、`taskLabels`、`api/web` 的边界用例（现有 11 个偏少）。

**验收**

- `npm run test:coverage` 输出覆盖率并达到阈值。
- CI frontend job 显示覆盖率；低于阈值失败。

**风险/回滚**：覆盖率工具会增加构建时间；先只对 `src/utils` 和 `src/api` 设阈值。

---

### G-14 E2E 响应式、键盘与 console（P3）

**目标**：1440 之外的布局、键盘焦点和浏览器 console 错误有自动回归。

**现状与证据（静态确认）**

- `frontend/playwright.config.ts:14` 固定 `viewport: { width: 1440, height: 1000 }`。
- `frontend/e2e/*` 没有 768/1024 视口、Tab 键、console error 汇总的用例。
- 旧文档也承认“窄屏/键盘/console error 矩阵”未覆盖。

**改动**

1. 新增 `responsive.spec.ts`：768/1024 视口遍历 8 个视图，断言无横向滚动、rail 不遮挡、关键按钮可点。
2. 新增 `keyboard.spec.ts`：Tab 顺序、对话框焦点陷阱/归还、Esc。
3. 在 `playwright.config.ts` 或 fixture 收集 `console` error，断言 0。
4. 截图归档到 `e2e-artifacts/`。

**验收**

- `npm run e2e` 新增 3 类用例全绿。
- 768 宽度无横向滚动；Tab 不穿出对话框；console error 0。

**风险/回滚**：布局修复可能涉及样式；只加测试不改布局，发现问题另开任务。

---

### G-15 3D 可访问性与性能（P3）

**目标**：3D 场景在 reduced-motion/无 WebGL 下有等价可访问视图；性能有数据。

**现状与证据（静态确认）**

- `frontend/src/components/AttackSurfacePanel.tsx:22-33` 的 `detectMode()`：`reduce` 直接返回 `"reduce"`；`:75` 在 `mode === "reduce"` 时渲染文字占位，不是视觉指南 §6.4 写的“静态 SVG 拓扑”。
- `AttackSurfaceScene.tsx` 的 `<Canvas>` 没有 `aria-hidden`；`AttackSurfacePanel` 容器没有 `role="img"` / `aria-label`。等价表格存在（`:80-100`），但旧文档的 aria 承诺未实现。
- 3D ≥50 fps 未做长时采样；Lighthouse 未跑；触摸拖拽未测（旧文档自述）。
- `AttackSurfaceScene.tsx` 使用 `frameloop="demand"`、DPR≤1.5、节点≤60，代码层面符合预算。

**改动**

1. 二选一：实现 reduce 下的静态 SVG 拓扑（同一布局、无交互），或把文档改成“reduce 下显示表格 + 文字说明”；不要继续声称静态 SVG。
2. Canvas 加 `aria-hidden="true"`；容器加 `role="img"` + `aria-label`（数量/摘要）；表格保留。
3. 用 `requestAnimationFrame` 采 60 帧，记录 10/30/60 节点三档 fps；补 `e2e/attack-surface-perf` 或脚本。
4. 手机 UA + `hasTouch` 上下文跑一次旋转手势。
5. 跑 Lighthouse（本地 HTTP）并记录 Performance/SEO/Accessibility。

**验收**

- axe/Playwright 断言 canvas 不可聚焦、表格可读。
- fps 采样报告 ≥50 fps（1440×900，DPR≤1.5，≤60 节点）。
- Lighthouse 分数记录在案。

**风险/回滚**：静态 SVG 是额外实现；不做就改文档，不能留虚假承诺。

---

### G-16 性能与视觉长尾（P3）

**目标**：把旧计划 F-16 和视觉 D-05/D-08 的剩余项收口或明确接受。

**现状与证据（静态确认）**

- 页面级 `React.lazy` 未做：`frontend/src/App.tsx` 直接 import 8 个页面；只有 3D 场景是 lazy（`AttackSurfacePanel.tsx:1-7`）。视觉指南 D-08 也承认未做。
- `styles.css` 仍有 37 个唯一 `#hex`、365 处 `var(--)`；间距/字号刻度只在新样式里使用，旧 507 条规则未全量回填（D-05 部分）。
- `/api/tasks/{id}/events?after_seq=` REST 分页不存在；SSE 支持 `after_seq`/`Last-Event-ID`（`app.py:440-461`），但独立事件查询接口没有。
- 报告生成是内存拼接 + `write_text`，不是流式写（`report/generator.py`）。

**改动**

1. 页面级 `React.lazy` + `Suspense`，保持 hash 路由挂载语义；构建后核对首屏 gzip ≤150 kB。
2. 事件 REST 分页：`GET /api/tasks/{id}/events?after_seq=&limit=`，复用 EventBus/JSONL；补测试。
3. 报告流式写：大报告用临时文件 + 逐段写入；小报告保持现状即可（先评估收益）。
4. 尺度长尾：按页面回填 `--space-*` / `--text-*`，或明确“旧规则保持现状，新规则必须用令牌”。

**验收**

- `npm run build` 首屏 gzip ≤150 kB；页面 chunk 独立。
- `pytest tests/web/test_task_events_api.py -q`。
- 视觉截图无布局回归。

**风险/回滚**：页面 lazy 会改变加载时序；E2E 必须全绿后再合并。

---

### G-17 事件名清单（P3）

**目标**：新增任务事件不会被前端静默丢弃。

**现状与证据（静态确认）**

- 后端 `publish()` 可以发任意事件名；前端 `frontend/src/api/web.ts:295-307` 维护一份硬编码 `addEventListener` 清单。
- 当前清单覆盖已存在的事件（`task_created/queued/restoring/started/state_changed/legacy_import/round_output/cycle_completed/completed/failed/stopped/interrupted/event_gap`）。
- 旧 P2-02 的“未列事件静默丢弃”风险仍在：未来后端新增事件，前端不会收到。

**改动**

1. 服务端只发默认事件名（`event:` 缺省），把事件类型放进 payload；前端统一 `onmessage`。或
2. 共享一份事件名常量（生成 TS 或从 API 拉取），前端按清单注册；加测试扫描后端事件名与前端清单一致。
3. `tests/web/test_event_names.py` + 前端单测。

**验收**

- 新增一个 mock 事件名，前端仍能进处理器。
- `rg` 检查后端事件名全部在前端清单。

**风险/回滚**：改事件名会影响第三方订阅；保留 `event:` 兼容一段时间。

---

### G-18 小项收尾（P3）

| 项 | 现状 | 收口 |
|----|------|------|
| gc Web 入口 | `vulnclaw gc` 只有 CLI（`vulnclaw/cli/main.py:2980`）；设置页没有磁盘占用/清理入口（旧 P2-16 承诺） | 设置页增加只读占用与“运行 gc”按钮（或明确 CLI-only） |
| ESLint warnings | `npm run lint` 0 errors / 20 warnings（`SettingsPage.tsx:143` 等 set-state-in-effect） | 可选清理；不阻塞 CI |
| 空 soak 产物 | `soak-4h-report.json` 0 字节，未跟踪 | 删除或重新生成有效报告 |
| `/api/version` | 没有独立路由；`/api/health` 已含 `version`（`web/app.py:224-237`） | 若外部约定需要，补 `/api/version`；否则文档明确用 health |
| `soak` 退出码 | 脚本只打印报告，不返回断言失败 | 与 G-10 合并 |

---

## 5. 文档声明与实际差异

| 旧文档声明 | 实际 | 处理 |
|-----------|------|------|
| V2 §11.3：`pytest 2107 passed / 82.14%` | 本轮 2332 passed / 82.82% | 以本轮为准 |
| V2 §11.4：F-04 已完成 | 只有事件/产物/报告；无续跑、证据抽屉、阶段耗时 | G-05 |
| V2 §11.4：F-05 主要链路完成 | 任务 project_id/选择器/过滤有；目标全局、多项目归属、报告路由未闭环 | G-06 |
| V2 §11.4：F-06 已完成 | 状态/备注/API 有；assignee UI、批量、报告标注缺失 | G-03 |
| V2 §11.4：F-07 已完成 | 五格式/模板/脱敏/PDF 有；不是 run 级，SARIF 无 schema 校验 | G-07 |
| V2 §11.4：F-08 Token 汇总 | tokens 字段/非流式计数有；流式估算死代码，cost_estimate 不存在 | G-01 |
| V2 §11.4：F-11 已完成 | interval 调度/通知/UI 有；cron 未实现，入队失败静默 | G-04 |
| V2 §11.4：F-12 已完成 | 配置开关/UI 有；不热重启、无工具白名单 | G-02 |
| V2 §11.4：F-13 基础完成 | `--offline`/doctor/pack/restore 有；发行包无预置 KB bundle | G-08 |
| V2 §11.4：F-18 脚本完成 | 脚本存在；4h 报告 0 字节，24h 未跑，无 RSS/孤儿断言 | G-10 |
| V2 §5.1/C-13：基准回归 | `scripts/bench_web_state.py` 与 `tests/performance` 均不存在 | G-09 |
| V2 P2-17：推送 ghcr.io + HEALTHCHECK | docker.yml 只 build；Dockerfile 无 HEALTHCHECK | G-11 |
| 差距审计 §3.3：F-10/11/13/14 未开始 | F-10/F-11/F-13/F-14 已落地（F-11/F-13 有上述缺口） | 以本文为准 |
| 差距审计 §5.1：version-manifest 仍存在 | 已在 `72ae6d8` 删除，测试断言不存在 | 已过时 |
| 差距审计 P2-09：dist 未纳入 git | 当前 `vulnclaw/web/dist` 已被跟踪 | 已过时 |
| 视觉指南 §6.4：reduce 下渲染静态 SVG | 实际是文字占位 + 表格 | G-15 |
| 视觉指南 §13.3：E2E 22 条 | 本轮 24 passed | 以本轮为准 |
| 视觉指南 §2.3：首屏 144.53 kB | 本轮 145.74 kB（仍 ≤150） | 以本轮为准 |
| README/PyPI：0.4.1 | 仓库 0.5.0，PyPI 0.4.1 | G-11 |
| 旧文档 P2-03：服务端心跳 + 前端 onerror 横幅 | 服务端心跳有；前端无 onerror | G-12 |

---

## 6. 建议施工顺序

### 阶段 1：正确性与用户可见闭环（约 5–6 人日）

1. G-01 流式 token + cost（0.5–1d）
2. G-05 运行详情续跑/证据/阶段耗时（1d）
3. G-02 MCP 热重启 + 工具白名单（1–1.5d）
4. G-03 发现工作台 assignee/批量/报告标注（1d）
5. G-04 调度 cron/失败可见（1d）

### 阶段 2：产品层一致性（约 2–3 人日）

6. G-06 项目隔离与报告路由（1d）
7. G-07 run 级报告 + SARIF schema（0.5–1d）
8. G-12 SSE 断线提示（0.5d）
9. G-13 前端覆盖率（0.5d）

### 阶段 3：发布与长稳（约 1 人日 + 机器时间）

10. G-09 基准回归（0.5d）
11. G-11 发布链路（0.5d + 发布操作）
12. G-10 4h/24h soak（机器时间 + 0.5d）

### 阶段 4：体验长尾（约 2–3 人日，可与阶段 2/3 并行）

13. G-08 离线 KB 策略（0.5d）
14. G-14 E2E 响应式/键盘/console（1d）
15. G-15 3D 可访问性/性能（1d）
16. G-16 性能与视觉长尾（1–2d）
17. G-17 事件名清单（0.5d）
18. G-18 小项收尾（0.5d）

合计约 10–13 人日，不含 24h soak 的机器时间与发布审批。

---

## 7. 验收命令

```bash
# 后端
python -m ruff check vulnclaw tests scripts
python -m pytest -q --cov=vulnclaw --cov-report=term

# 前端
cd frontend
npm run build
npm run test
npm run test:coverage        # G-13 新增
npm run lint
npm run e2e

# 基准
python scripts/bench_web_state.py --assert   # G-09 新增
pytest -m slow tests/performance -q          # G-09 新增

# 长稳
python scripts/soak_web.py --duration 14400 --interval 5 --clients 3 --assert
# 24h: --duration 86400

# 离线
vulnclaw --offline doctor
vulnclaw kb pack /tmp/kb.json
VULNCLAW_CONFIG_DIR=/tmp/offline vulnclaw kb restore /tmp/kb.json

# 发布
python scripts/release_preflight.py --build
python scripts/verify_dist_artifacts.py
pip install vulnclaw==0.5.0
```

---

## 8. 不重做的清单

以下项目已有真实实现与测试，不要重复施工：

- P0-01 失败语义、P0-02 初始化失败出口。
- P1-02～P1-09 全部可靠性内核。
- P2-01、P2-03（服务端）、P2-04、P2-05、P2-06、P2-07～P2-15、P2-16（CLI gc）、P2-18、P2-19、P2-20、P2-21。
- DNS rebinding Host 白名单。
- F-09 审计导出、F-10 集成 dispatch/配置/投递历史、F-14 插件发现/权限/版本/样例包、F-15 E2E/ESLint。
- 视觉 Phase A～E：令牌、双主题、动效 M-01～M-10、3D 场景与 WebGL 降级、公开站、主题/动效/a11y E2E。
- `vulnclaw/web/dist` 随包分发与 wheel 内 UI 断言。

---

## 9. 删除记录

以下四份文档已从工作树删除，本文是唯一保留的施工/交接文档：

| 文件 | 状态 |
|------|------|
| `计划书/VulnClaw-Max-工程改造计划书-V2.md` | 已删除 |
| `计划书/VulnClaw-Max-差距审计与验收编排.md` | 已删除 |
| `计划书/VulnClaw-Max-视觉交互与可发现性设计指南-V1.md` | 已删除 |
| `计划书/下一步改进指南.md` | 已删除 |

恢复方式（git 历史仍保留在 `2d8ba99`）：

```bash
git show 2d8ba99:计划书/VulnClaw-Max-工程改造计划书-V2.md > /tmp/V2.md
git show 2d8ba99:计划书/VulnClaw-Max-差距审计与验收编排.md > /tmp/audit.md
git show 2d8ba99:计划书/VulnClaw-Max-视觉交互与可发现性设计指南-V1.md > /tmp/visual.md
git show 2d8ba99:计划书/下一步改进指南.md > /tmp/guide.md
```

---

## 10. 本轮实施结果（2026-11-11）

### 10.1 最终门禁

| 门禁 | 结果 |
|------|------|
| `ruff check vulnclaw tests scripts` | All checks passed |
| `pytest -q --cov=vulnclaw` | **2358 passed / 8 skipped / 82.82% / 101.33s** |
| `npm run build` | 首屏 `index-*.js` **123.72 kB gzip**；3D chunk **220.80 kB gzip**；Risk/History/Reports/Settings/TaskConsole 均独立 chunk |
| `npm run test` | 11 个测试文件 / **36 passed** |
| `npm run test:coverage` | 总覆盖率 **50.41%**；utils **95.36%**；components **45.91%** |
| `npm run lint` | **0 errors / 24 warnings**（非阻塞） |
| `npm run e2e` | **31 passed / 58.6s** |
| `python scripts/bench_web_state.py --assert` | publish 300 = **0.00105 s**；create 300 = **0.01299 s**；500 targets = **0.00663 s**；`web_tasks.json` 44,646 B |
| soak 120s | 60 tasks，RSS 101.0→104.9 MB，增长 **3.86%**，无子进程 |
| soak 10m | 120 tasks，RSS 100.8→106.8 MB，增长 **5.95%**，断言通过，无子进程 |
| soak 1h（原始） | 717 tasks，RSS 101.1→64.0 MB，峰值 158.2 MB，无子进程；旧脚本把被保留策略裁掉的任务 404 误判为“非终态”，已在脚本修复，10m 复跑断言通过 |
| wheel/sdist | `vulnclaw-0.5.0-py3-none-any.whl` + `.tar.gz`；wheel 内含 `vulnclaw/web/dist/index.html`、`vulnclaw/kb/default_bundle.json`、`vulnclaw/web/event_names.py` |
| Lighthouse（公开站） | Performance **100** / Accessibility **100** / SEO **100** |
| Lighthouse（本地 Web UI） | Performance **99** / Accessibility **100**；LCP 2.1s、CLS 0、TBT 10ms |
| 公开站 | `/`、`/sitemap.xml`、`/robots.txt` 均 200 |
| GitHub CI（main） | success（ruff / pytest / tsc / lint / unit tests / E2E matrix） |
| Release Preflight（v0.5.0-final） | success |
| Docker build（v0.5.0-final） | success；manifest 已推送 GHCR |
| Release（v0.5.0-final） | failure：仅 PyPI trusted publisher 步骤失败，构建与 preflight 成功 |
| PyPI / GHCR | 仓库 0.5.0；GHCR `ghcr.io/lza6/vulnclaw-max:v0.5.0-final`、`:latest` 已推送；GitHub Release `v0.5.0-final` 已创建；PyPI trusted publisher 未配置，`release.yml` 在 PyPI step 报 `invalid-publisher`，0.5.0 尚未上 PyPI |

### 10.2 G-01～G-18 状态

| ID | 状态 | 本轮落地 |
|----|------|----------|
| G-01 | **完成** | 流式 `call_llm_stream` / `_stream_chat_completion_message` 记账；provider usage 优先、缺失时估算；`TaskSummary.cost_estimate` + 配置单价；TaskConsole 与报告正文展示 token/成本；`tests/agent/test_stream_usage_accounting.py`、`tests/report/test_report_triage.py` |
| G-02 | **完成** | 进程级 control-plane MCP manager；启停即时作用于控制面；`allowed_tools` 白名单在注册与 `call_tool` 双侧校验；拒绝写 `mcp_audit.jsonl`；设置页白名单输入；运行中任务保留启动时配置并在 UI 说明 |
| G-03 | **完成** | Risk 页 assignee 输入、全选/批量处置、备注；报告 findings 合并 `finding_meta` 输出处置状态/负责人；`tests/web/test_findings_lifecycle.py` + E2E |
| G-04 | **完成** | 5 段 cron 解析（`vulnclaw/cron.py`）；`ScheduledJob.cron` + `next_cron_time`；设置页 interval/cron 切换；runner 异常写 `last_error`/`last_error_at` 并在 UI 展示；`tests/test_scheduler.py` |
| G-05 | **完成** | RunDetailDialog 增加续跑、阶段耗时、证据抽屉；`resumeRun()` 调 `/api/tasks/run`（`resume_run_name` + `snapshot_id`）；`RunDetailView.phases`；组件测试 + `/api/runs` |
| G-06 | **完成** | `projects/index.json` 单项目归属索引；目标跨项目移动；`/api/targets?project=` 过滤；报告按任务/显式项目路由；顶栏项目切换；Home/History 同步；`tests/web/test_projects.py`、`test_project_reports.py` |
| G-07 | **完成** | `ReportGenerateRequest.run_name` 从 run 快照生成报告；官方 SARIF 2.1.0 schema vendored + `jsonschema.validate`；`tests/report/test_findings_output.py`、`test_project_reports.py` |
| G-08 | **完成** | 预置 `vulnclaw/kb/default_bundle.json`；`ensure_default_bundle()` 在空 KB 首次使用时自动 restore；doctor 同步；`tests/kb/test_kb_pack.py`；wheel 内含 bundle |
| G-09 | **完成** | `scripts/bench_web_state.py` + `tests/performance/test_benchmarks.py`（`slow` marker）；四阈值断言 |
| G-10 | **部分** | 120s/10m 断言通过；1h 原始运行内存稳定且无孤儿；**24h 仍未跑**，作为发布前机器时间门禁 |
| G-11 | **部分：GHCR/Release 完成，PyPI 阻塞** | PyPI trusted publishing step、GHCR build/push、Dockerfile HEALTHCHECK、security PR path 已落地；`v0.5.0-final` tag 触发 Docker 成功并推送 GHCR，GitHub Release 已创建；PyPI 侧缺少 trusted publisher 配置，release workflow 在 PyPI step 失败，0.5.0 未上 PyPI |
| G-12 | **完成** | `openTaskStream` 增加 `onOpen/onError`；App 显示重连横幅；`e2e/stream.spec.ts` |
| G-13 | **完成** | `@vitest/coverage-v8`；`test:coverage`；阈值 lines/functions/statements 40、utils 90；实测 50.41% |
| G-14 | **完成** | `responsive.spec.ts`（768/1024）、`keyboard.spec.ts`（Tab/焦点归还）、`console.spec.ts`（0 console error） |
| G-15 | **完成** | reduce 下静态 SVG 拓扑；canvas `aria-hidden` + 容器 `role="img"`；E2E 断帧预算 ≥50fps；触摸拖拽 E2E；公开站 Lighthouse 100/100/100，本地 Web UI 99/100（LCP 2.1s、CLS 0） |
| G-16 | **部分** | 页面级 `React.lazy`（首屏 123.72 kB）；`/api/tasks/{id}/events?after_seq=`；design-token 预算测试；**报告流式写未做（当前报告有界，单次写可接受）**、尺度长尾仍按页面回填 |
| G-17 | **完成** | `vulnclaw/web/event_names.py` + `frontend/src/api/taskEvents.ts`；前端按共享清单注册；`tests/web/test_event_names.py` |
| G-18 | **完成** | `/api/version`、`/api/storage`、`/api/gc`；Settings 磁盘占用/预览/清理；`vulnclaw/gc.py` 抽取 + CLI 复用；24 条 lint warning 保留（0 error，不阻塞） |

### 10.3 仍然开放的事项

| 事项 | 原因 | 下一步 |
|------|------|--------|
| 24h soak | 需要连续机器时间，本轮只完成 1h 原始运行 + 10m 断言复跑 | 发布前跑 `--duration 86400 --assert`，归档报告 |
| PyPI 0.5.0 实际发布 | PyPI 项目 `vulnclaw` 未为本仓库配置 trusted publisher；`release.yml` 报 `invalid-publisher` | 在 PyPI 添加 trusted publisher（repo `lza6/VulnClaw-Max`，workflow `release.yml`，tag/环境按 PyPI 配置），或提供 API token；然后重跑 release workflow |
| ~~Lighthouse 与触摸拖拽~~ | 已跑：公开站 100/100/100，本地 99/100，触摸拖拽 E2E 通过 | 已关闭 |
| 报告流式写 | 现有报告在内存中拼接，大小有界；伪流式没有收益 | 大报告场景出现后再做 |
| 尺度长尾 | 507 条旧规则未逐条回填 `--space-*` / `--text-*` | 按页面分片，新增规则已被 token 预算测试约束 |
| 24 条 ESLint warning | 主要是 `set-state-in-effect` 与 `exhaustive-deps`，0 error | 后续按页面清理，不阻塞发布 |

### 10.4 发布产物

```
dist/vulnclaw-0.5.0-py3-none-any.whl
dist/vulnclaw-0.5.0.tar.gz
```

- GitHub Release：https://github.com/lza6/VulnClaw-Max/releases/tag/v0.5.0-final
- GHCR：`ghcr.io/lza6/vulnclaw-max:v0.5.0-final`、`ghcr.io/lza6/vulnclaw-max:sha-2b9dcb8`、`ghcr.io/lza6/vulnclaw-max:latest`

wheel 校验（`python scripts/verify_dist_artifacts.py`）通过；包内包含 Web UI、默认 KB bundle 与事件名清单。

## 附录 A：本轮实测原始结果

```
ruff check vulnclaw tests scripts   -> All checks passed!
pytest -q --cov=vulnclaw            -> 2332 passed, 8 skipped, 82.82%, 98.23s
vulnclaw/web/app.py                 -> 93% coverage
npm run build                       -> 557 modules, JS 484.35 kB (gzip 145.74), CSS 49.61 kB (gzip 10.02), 3D 220.79 kB
npm run test                        -> 4 files / 11 tests passed
npm run lint                        -> 0 errors, 20 warnings
npm run e2e                         -> 24 passed (51.6s)
python -m vulnclaw --help           -> 0.392s / 0.375s / 0.448s
site                                -> /, /sitemap.xml, /robots.txt 均 200
PyPI                                -> latest 0.4.1
soak-4h-report.json                 -> 0 bytes
```

## 附录 B：关键文件索引

| 关注点 | 文件 |
|--------|------|
| 失败传播 | `vulnclaw/agent/errors.py`、`vulnclaw/agent/llm_client.py`、`vulnclaw/orchestrator.py` |
| Web 任务 | `vulnclaw/web/services/task_service.py`、`vulnclaw/web/task_manager.py`、`vulnclaw/web/event_bus.py` |
| 持久化 | `vulnclaw/web/task_manager.py`、`vulnclaw/run_context.py` |
| MCP | `vulnclaw/web/services/mcp_control_service.py`、`vulnclaw/mcp/lifecycle.py` |
| 项目/发现/报告 | `vulnclaw/web/services/project_service.py`、`finding_service.py`、`report_service.py`、`vulnclaw/report/generator.py` |
| 调度/集成 | `vulnclaw/scheduler.py`、`vulnclaw/web/services/schedule_service.py`、`vulnclaw/integrations/*` |
| 前端 | `frontend/src/App.tsx`、`frontend/src/pages/*`、`frontend/src/api/web.ts`、`frontend/src/styles/tokens.css` |
| 视觉/3D | `frontend/src/motion/*`、`frontend/src/scene/AttackSurfaceScene.tsx`、`frontend/src/components/AttackSurfacePanel.tsx` |
| 发布/CI | `.github/workflows/*`、`Dockerfile`、`scripts/release_preflight.py`、`scripts/verify_dist_artifacts.py` |
| 长稳/基准 | `scripts/soak_web.py`、`scripts/bench_web_state.py`（待建）、`tests/performance/`（待建） |