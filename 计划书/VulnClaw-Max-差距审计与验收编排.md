# VulnClaw-Max 差距审计与验收编排

> 审计日期：2026-11-05
> 审计对象：`计划书/VulnClaw-Max-工程改造计划书-V2.md` 所定义的全量 V2，以及当前工作树的 49 个已跟踪变更、33 个新增文件
> 审计口径：代码与运行结果优先于文档；`已验证` / `静态确认` / `合理推断` / `待验证`
> 本文件只做审计与编排，不改业务代码

---

## 0. 结论

当前不是「全量 V2 已完成」，而是「**可靠性外壳基本完成 + 若干产品层底座**」。三个硬缺口必须先处理，否则继续加功能只会把问题埋得更深：

1. **P0-01 已完成闭环（本轮修复）。** 修复前 `run --engine solve` 401 仍退出 0，Web 首页无 key 点击「开始」显示「扫描完成」；根因是 solve/team/rounds/persistent 的 catch 把 fatal LLM 错误降级。已让 `structured_call`、solver 步骤循环、rounds 循环、team 计划/顾问在 fatal 错误时上抛。复测：solve/team/rounds/persistent 全部 exit 1；Web 默认 `run` 任务 `failed`。
2. **产品层只完成了底座。** F-05 只有项目记录/目标关联 API，没有 `project_id`、CLI `--project`、Web 切换器、报告路由；F-07 只把已有 JSON/SARIF 产物列出来，前端下载类型还是错的，多模板/脱敏/PDF 未接；F-10/F-11/F-13/F-14 完全未开始。
3. **四类验收只完成了一小部分。** UI 只截了首页；真实调用只验证了 401 失败和 codescan；E2E 为 0；独立代码复审正在进行，尚未出结论。

另外有 18 项「已完成但不完美」，详见第 3.2 节。它们共同的特征是：**接口存在、单测存在，但跨模块链路、异常分支、UI 交互或真实数据没有验证完**。

---

## 1. 需求逐句拆解（每句按表层、深层、反例三遍）

| # | 你的原话 | 表层要求 | 深层意图 | 反例（不能这样做） | 本次对应动作 |
|---|----------|----------|----------|--------------------|--------------|
| 1 | 看看还有什么没搞定清楚 | 列未完成项 | 不接受模糊的「差不多完成了」，要能指到文件和链路 | 只报「已实现」不报缺口 | 第 3 节矩阵 |
| 2 | 有些搞定了但不完美，有些还没开始 | 分类 | 区分「能用」和「闭环」；区分「底座」和「功能」 | 把「有 API」算成 F-05 完成 | 3.2 / 3.3 |
| 3 | 细拆提示词，先不着急动手 | 先理解再执行 | 避免继续堆功能、先锁定真实缺口和顺序 | 直接改代码、边做边猜 | 本文件 |
| 4 | 了解规则、规范、记忆 | 读 CLAUDE/rules/ICM/Beads | 以项目真实约定为准，不凭空发明流程 | 按通用习惯直接提交/推送 | 第 2 节 |
| 5 | 了解全貌和代码库真实 | 读代码、跑命令 | 文档可能过时，必须以运行结果为准 | 只复述旧指南 | 本次复核 + 401 solve 实测 |
| 6 | 先思考怎么做、真实编排 | 施工顺序、依赖、门禁 | 每步有交付物、验收、回滚；不是任务清单堆叠 | 按功能列表平铺，不管依赖 | 第 6 节 |
| 7 | 验收分 UI 截图、真实调用、真实 E2E、真实代码复审 | 四类验收 | 每类都要有可复查证据，不是「看起来可以」 | 只跑单测就宣布完成 | 第 4 节 |
| 8 | UI 截图要看按钮能不能按成功、逻辑、组件位置人性化 | 交互可用性 | 截图只是起点，要真实点击、输入、等待、看状态 | 只截首页静态图 | 4.1 + Stage 2 |
| 9 | 功能完整闭环、模块衔接、容错、稳定性、bug | 端到端闭环 | 前后端、CLI/Web、持久化、异常恢复都要串起来 | 单点接口能返回就算完成 | 第 7 节矩阵 |
| 10 | 先三思，每句话思考三遍 | 深度审查 | 找反例、边界、失败路径，而不是顺着实现解释 | 用实现细节替代需求判断 | 第 5 节 |
| 11 | 请你继续，还有很多没完成 | 继续推进 | 不要停在文档，按编排进入下一阶段 | 只交审计不落地 | 第 9 节 |

### 1.1 原任务契约（第一轮请求）的拆解

| 原要求 | 当前状态 | 缺口 |
|--------|----------|------|
| 在 `计划书/` 下新建文档 | 已完成 | `VulnClaw-Max-工程改造计划书-V2.md` |
| 检查旧文档是否过时 | 已完成 | P2-21 已修复、P1-09 可达性已修正 |
| 按真实情况重写 | 已完成 | 以实测为基线 |
| 验证文档 | 已完成 | `file:line` 引用校验、命令输出 |
| 需要拍板先提问 | 已完成 | 范围/编码/版本三项已问 |
| 全量 V2 | 部分完成 | 见 3.2 / 3.3 |
| 0.5.0 | 未发布 | 版本仍是 0.4.1，未 bump |
| 不 commit/push | 遵守 | 未提交 |

---

## 2. 规则、规范与记忆读取

### 2.1 已读取的项目约定

- 全局 CLAUDE：中文回复、证据分级、禁止伪造验证、付费 API 预算 0、Windows 规则、未经授权不 commit/push。
- 项目 CLAUDE：Beads 任务追踪、保守 git profile、交付时报告变更/验证/下一步。
- `计划书/VulnClaw-Max-工程改造计划书-V2.md`：本轮的施工契约。
- ICM 记忆：上一轮已存「0.5.0 施工（部分完成）」及旧指南复核记录。
- `.wolf/`：本仓库不存在，OpenWolf 协议不适用于本仓库；不虚构 `.wolf` 更新。
- Beads：`bd list` 中没有 VulnClaw 相关 issue；当前以计划书作为事实上的跟踪台账。

### 2.2 记忆里的关键事实

- 旧指南基线：176 个 Python 文件、65k 行、1924 用例、覆盖率 76.74%、`--help` 0.81 s。
- 本轮改造后：1969 passed / 10 skipped、覆盖率 77.05%、前端 11 个 Vitest、wheel 内含 UI。
- 旧判断已修正：`vulnclaw web` CLI 入口本来就有 UTF-8 配置，GBK 崩溃只在直接嵌入 `create_app` 时可达；P0 的根因是初始化异常没有失败出口。

---

## 3. 现状矩阵

### 3.1 已完成且已验证

| 项 | 证据 |
|----|------|
| P0-02 初始化失败出口 | `_run_task` 全函数 try/finally；`tests/web/test_task_setup_failure.py` |
| P1-02 SSE 重复 | EventBus + seq；实测 5 帧无重复 |
| P1-03 stop 篡改终态 | stop 守卫 + 409；实测已完成任务 stop → 409 |
| P1-04 队列无界 | 环形缓冲 2000；5,000 事件 1.416 s，队列封顶 |
| P1-05 写放大 | JSONL + 去抖；300 事件 0.080 s，快照 38.9 KB |
| P1-06 重启僵尸 | 非终态 → `interrupted`；`test_restart_reconciles_non_terminal_tasks` |
| P1-07 并发/停机 | 信号量 + queued + lifespan；生命周期用例 |
| P1-08 目标列表 | 先排序截断 + 坏文件跳过；500 目标 0.432 s |
| P1-09 直接嵌入 GBK | `vulnclaw/encoding.py`；Web app 调用 |
| P2-01 静态资源 404 | `resolve_web_asset` 返回 None |
| P2-03 服务端心跳 | `encode_heartbeat` + 15 s |
| P2-04 停止 UI | 服务端/列表回读 |
| P2-05 版本主源 | `__version__` + Vite define + 测试 |
| P2-06 报告 PoC 路径 | `pocs/<file>` 相对路径；原失败用例转绿 |
| P2-12 配置原子写 | tmp + os.replace |
| P2-14 docs 可跟踪 | `.gitignore` 已移除 `docs/` |
| P2-15 前端单测 | Vitest 11 passed + CI |
| P2-19 健康检查 | version/uptime/ui/tasks |
| P2-20 Web KB 提示 | `console_output=False` |
| F-04 运行详情 | `/api/runs*` + `RunDetailDialog` |
| F-06 发现处置 | `finding_meta` + API + Risk 页下拉/备注 |
| F-08 Token 汇总 | 非流式 usage 累计 + 任务台展示 |
| F-09 审计导出 | `/api/audit/export` |
| F-05 项目底座 | `project.json` + `/api/projects*` |
| F-12 MCP 开关 | `/api/mcp/toggle` |
| F-18 soak 脚本 | `scripts/soak_web.py`，8 秒冒烟 |

### 3.2 已完成但不完美

| # | 项 | 现状 | 缺口 | 证据 | 风险 |
|---|----|------|------|------|------|
| 1 | P0-01 失败语义 | 所有引擎已修 | 无（待补更多 mock 场景：429/timeout/malformed） | `run --engine solve/team/rounds`、`persistent` 401 → exit 1；Web 默认 `run` → failed | 已关闭，剩余是扩大 mock 矩阵 |
| 2 | P1 SSE | 无重复、可续传 | 环形缓冲溢出时没有 `gap` 事件；慢消费者丢事件不可见 | `EventBus.stream` 只按 seq 过滤 | P1：长跑可能静默丢事件 |
| 3 | P1 持久化 | JSONL + 0.3 s 缓冲 | 进程崩溃会丢最后 0.3 s 事件；没有 fsync；没有崩溃测试 | `_flush_events` 依赖定时器 | P2：本地可接受，需在文档写明 |
| 4 | P1 并发/停机 | 队列 + 信号量 | queued 任务在 shutdown 时可能保持 queued 到重启；没有 MCP 孤儿子进程断言 | `shutdown` 只 cancel `_running`；队列测试用 fake `_run_task` | P1：退出后状态不干净 |
| 5 | F-04 运行详情 | 弹窗、时间线、产物、报告 | 初版 `HistoryPage` 根本没有渲染 `<RunDetailDialog>`，按钮点了没反应；已补渲染；对比度/header 已修；仍无焦点陷阱/无 E2E | 真实 CDP 点击：修复前 `no dialog`，修复后正常打开 | P2：可访问性/可发现性 |
| 6 | F-06 发现处置 | 状态下拉 + 备注 | 负责人字段没有 UI；finding key 在 `vuln_type` 为空时可能前后端不一致；无 E2E | `extractFindingCards` 用 `title::vuln_type` | P1：可能更新到错误 key |
| 7 | F-08 Token | 摘要字段 + 任务台展示 | 流式调用没有记录 usage；Web 任务大多走流式，实际可能恒为 0 | `_record_response_usage` 只在非流式 retry 包装里调用 | P1：仪表盘数据不可信 |
| 8 | F-09 审计导出 | API 可用 | 前端没有导出按钮/入口 | SafetyBoundary 页只有统计，没有下载 | P1：功能不可达 |
| 9 | F-05 项目 | 记录/目标关联 API | 没有 `project_id`、CLI `--project`、Web 切换器、报告落项目目录、任务归属 | `grep project_id` 为空 | P1：只是底座，不是功能 |
| 10 | F-07 报告中心 | JSON/SARIF 可列可下载 | 前端 filter 只有 md/html；下载 JSON/SARIF 仍按 text/markdown + `.md`；无多模板/脱敏/PDF | `ReportsPage.tsx` `kindFilter`、`handleDownload` | P1：下载文件类型/扩展名错误 |
| 11 | F-12 MCP | 配置开关 API | 无 UI；不热重启，只对下一个任务生效；没有工具白名单 | `toggle_mcp_server` 返回 `applies_to: next_task` | P1：承诺与实现不一致 |
| 12 | P2-05 版本 | 主源统一 | `codescan/report.py` 仍硬编码 `0.4.1`；版本一致性测试没扫它 | `vulnclaw/codescan/report.py:218` | P2：下次 bump 必漏 |
| 13 | P2-13 启动 | 未做 | `--help` 0.848 s；顶部导入仍重 | 实测 | P2 |
| 14 | P2-16 保留 | 只有 Web 任务保留 | 没有 `vulnclaw gc`；sessions/runs/targets 只增不减 | `grep gc` 为空 | P2 |
| 15 | P2-17 发布 | frontend test 入 CI | 无 pip-audit/npm audit/SBOM/Docker workflow | `.github/workflows` 仅 ci/release | P2 |
| 16 | P2-07/08/09/10/11 | 未做 | 语言回落不一致、`html lang` 固定、硬编码 aria、无焦点陷阱、无 reduced-motion/theme-color | `index.html:2`、`ToastHost.tsx:40`、`styles.css` | P2 |
| 17 | P2-18 覆盖率 | 77.05% | `web/app.py` 56%；目标 82/90 | coverage 输出 | P2 |
| 18 | 性能目标 | 部分达标 | 300 任务 0.987 s（目标 0.3）；500 目标 0.432 s（目标 0.1）；需索引 | 基准 | P2 |

### 3.3 未开始

| 项 | 现状 | 影响 |
|----|------|------|
| F-10 集成导出 | 无 `integrations` 模块 | 结果进不了 Jira/DefectDojo/Webhook |
| F-11 调度与通知 | 无 scheduler | persistent 不能排期巡检 |
| F-13 离线模式 | 无 `--offline` | 内网/断网场景不可用 |
| F-14 插件生态 | `PluginRegistry` 只有内存注册，无 entry_points/权限/版本校验 | 第三方插件无法安装即用 |
| F-15 E2E/ESLint | 无 Playwright、无 ESLint | UI 交互没有自动回归 |
| F-17 供应链 | 无 audit/SBOM/Docker job | 发布不可信 |
| F-18 24h | 只跑 8s | 长稳未验证 |
| P2-07/08/09/10/11/13/16/17 | 未做 | 可访问性/启动/保留/供应链 |
| DNS rebinding 防护 | 未做 | 本地 Web 的 Host 校验缺失 |

---

## 4. 四类验收门

### 4.1 UI 截图验收

**当前只完成：** 首页 1440×1000 headless Chrome 截图，确认 SPA 渲染、侧栏 `v0.4.1`、表单可见。`/tmp` 截图 `.test-tmp/ui-home.png`。

**本轮已补的真实交互（CDP，非仅静态截图）：**

- 首页填入 `127.0.0.1:1` → 点击「开始」→ 任务创建、事件流、状态更新。
- 历史页 → 点击「查看运行详情」→ 修复前弹窗不存在；补渲染后弹窗正常展示事件时间线/产物/报告。
- 风险结果页 → 选择 `https://example.com` → 处置状态下拉改为「已确认」→ `/api/findings` 读回 `triage_status=confirmed`。
- 截图：`.test-tmp/ui-confirm.png`、`ui-run-detail-wide.png`、`ui-risk.png`、`ui-triage.png`。

**还没做：** 报告页真实生成/下载、设置页 MCP 启停、边界页导出、stop 409 的 UI 提示、窄屏 768/1024 全页、键盘 Tab 焦点、console error 扫描。

| 页面 | 必须验证的交互 | 通过标准 |
|------|----------------|----------|
| 首页 | 空 target 时开始按钮禁用；非法端口报错；合法端口打开确认框；取消不建任务；确认后任务进入 queued/running | 每步截图 + 网络请求 + 状态变化 |
| 首页运行态 | 任务事件流更新；停止按钮；停止后状态 stopped；已完成任务再停止显示 409 提示 | 截图 + toast + 任务状态 |
| 历史 | 任务列表、运行详情按钮、弹窗打开/关闭/Esc/焦点归还、时间线/产物/报告 | 截图 + DOM 断言 |
| 风险结果 | 目标切换、处置状态下拉、备注失焦保存、刷新后仍在、错误 toast | 截图 + 后端状态读回 |
| 报告 | 生成 md/html、筛选、预览、下载 JSON/SARIF、空态 | 截图 + 下载文件 MIME/扩展名 |
| 设置 | MCP 列表、启停（待做）、配置保存、审计导出入口（待做） | 截图 + 配置读回 |
| 安全边界 | 审计统计、事件列表、导出按钮（待做） | 截图 + 下载内容 |
| 响应式 | 1440/1024/768；窄屏 rail 是否遮挡；键盘 Tab | 截图 + 无横向滚动/无遮挡 |
| 可访问性 | `lang`、标题、焦点陷阱、reduced-motion、aria-label | DOM/截图 |

> 当前截图里右侧 rail 的文字在 1440 宽度下有拥挤/截断迹象，必须在 Stage 2 用真实交互再确认是截图缩放还是布局缺陷；不能凭一张静态图就判通过。

### 4.2 真实调用验收

**已完成：**
- 本地 401 mock → `recon` exit 1、错误脱敏。
- 本地 401 mock → Web 任务 `failed` / `task_failed`。
- codescan 真任务 → 完成、事件、soak。
- 本地 401 mock → `run --engine solve` 曾 **exit 0**，已修复为 exit 1。
- 失败矩阵（真实 SDK × 本地 provider mock）：401/403 首次请求即失败且脱敏；429/500/timeout/malformed/空 choices/连接断开重试耗尽后抛 `LLMInvocationError`；取消原样上抛；retry-then-ok 恢复并计数；solve/team/rounds/persistent 入口均上抛 fatal 错误；`run_agent_task` 记录 `failed`/exit 1；`recon`/`scan`/`exploit`/`run --engine solve` 四个 CLI 命令在真实 401 provider 下 exit 1。用例：`tests/agent/test_llm_transport_failure_matrix.py`、`tests/agent/test_engine_fatal_propagation.py`、`tests/cli/test_cli_mock_llm_failure.py`；mock：`scripts/mock_llm_server.py`。

**未完成：**
- 成功 LLM mock 的文本/工具调用/流式 chunk/usage 断言（mock server 已提供 `ok`/`tool`/`stream_ok` 场景，尚未写对应用例）。
- 真实付费 LLM：预算 0，除非你明确批准并给预算；默认继续用本地 mock。

### 4.3 真实 E2E

**已完成 5 条（Playwright + 本地 mock LLM，`frontend/e2e/`）：**
1. 首页 → 快速侦查 → 任务创建 → 完成态。
2. 历史 → 运行记录 → 运行详情 → 时间线/产物 → 关闭。
3. 风险结果 → 处置状态下拉 → 刷新后仍为 `confirmed`。
4. 报告 → 生成 → 筛选 SARIF → 下载文件扩展名 `.sarif`。
5. 已完成任务 stop → 409；终态后 SSE 不再重连。

运行：`cd frontend && npm run e2e`（5 passed，14.4 s）。截图：`frontend/e2e-artifacts/`。

**仍未覆盖：** 设置页 MCP 启停、边界页审计导出、窄屏 768/1024、键盘 Tab、console error 汇总。

### 4.4 真实代码复审

**进行中：** 已启动独立只读审查代理，按 P0/P1/P2 检查 49 个改动文件与新增文件，重点看 solve/team/rounds 吞错、EventBus 溢出、生命周期、持久化、前端新功能闭环、测试是否过弱。结果回来后必须先分级、复现、再修，不能直接接受。

**复审通过标准：**
- 每个 P0/P1 有代码证据 + 复现 + 测试。
- 不存在「接口存在但 UI 不可达」「测试只测 mock」「失败仍 completed」。
- 没有未处理的 TODO/空实现/假数据。
- 安全边界（路径、鉴权、命令执行）没有回退。

---

## 5. 深度审查发现（本轮新增）

### P0

1. **solve/team/rounds/persistent 吞 LLM 失败（已修复并复测）**
   - 修复前：`run --engine solve` 401 → exit 0，仍生成报告；Web 首页无 key → completed。
   - 修复：`structured_call` 对 401 抛 `LLMInvocationError(fatal=True)`；solver 步骤、rounds 循环、team 计划/顾问遇到 fatal 直接上抛；persistent 经 auto_pentest 透传。
   - 复测：solve/team/rounds/persistent 均 exit 1；Web 默认 `run` → failed。剩余是 429/timeout/malformed 的 mock 矩阵。

### P1

2. **流式 LLM usage 未记录**
   - `_record_response_usage` 只在 `_call_with_persistent_retries` 调用；`call_llm_stream` / `call_llm_auto_stream` 不走这里。
   - Web 任务大量走流式，`tokens_total` 很可能恒为 0。
3. **报告 JSON/SARIF 下载类型错误**
   - `ReportsPage.handleDownload` 对非 html 一律 `text/markdown` + `.md`；`kindFilter` 只支持 md/html。
   - 用户下载 SARIF 得到 `.md`，工具无法识别。
4. **F-05 没有项目闭环**
   - `grep project_id` 为空；没有 task/project 归属、CLI `--project`、Web 切换器、报告路由。
5. **F-07 没有报告中心 2.0**
   - 无 Jinja2 多模板、无脱敏、无 PDF 接入；只有旧报告生成 + JSON/SARIF 产物。
6. **F-09/F-12 前端不可达**
   - 审计导出只有 API；MCP 开关只有 API；UI 没有按钮/入口。
7. **MCP 开关只对下一个任务生效**
   - `toggle_mcp_server` 返回 `applies_to: next_task`；运行中的 server 不会热重启，和「控制台启停」的用户预期不一致。
8. **版本仍有硬编码**
   - `vulnclaw/codescan/report.py:218` 写死 `"0.4.1"`；`test_version_consistency` 没覆盖。
9. **SSE 缓冲溢出无 gap 事件**
   - 慢消费者超过 2000 事件会静默跳过；客户端无法知道缺口。
10. **shutdown 对 queued 任务状态不干净**
    - `shutdown` 只 cancel `_running`；等待信号量的任务可能保持 queued 到下次启动对账。

### 本轮 UI 实测新增发现

11. **`HistoryPage` 没有渲染 `RunDetailDialog`（已修复）**
    - 初始只加了 import 和 state，没有 JSX；按钮点击无任何反应。
    - 真实 CDP 验证：修复前 `document.querySelector('[role=dialog]')` 为 null；补渲染后正常。
12. **运行详情弹窗对比度/布局（已修复）**
    - 弹窗深色背景继承了浅色主题的深色文字 `rgb(36,63,101)`；h3 几乎不可读。
    - `.report-dialog-header` 没有 flex 规则，关闭按钮掉到标题下方。
    - 已补 `.report-dialog` 文字色、header flex、事件 payload/产物 code 的对比度。
13. **右侧固定 rail 在 1440 宽度下标签被视口裁切**（待修）
    - 截图中「历史/报告/资产/范围/发现/控制台/刷新」文字贴到右边缘并被截断，且覆盖 topbar 目标文本。
14. **处置状态无保存反馈**（待修）
    - 下拉/备注保存成功但没有 toast/行内「已保存」，用户不知道是否落盘；失败才出 error。
15. **风险卡标签与值之间缺少间距**（待修）
    - `类型SQLi`、`证据https://...` 在窄屏连在一起，可读性差。

### P2

11. **可访问性未闭环**：`index.html` 固定 `zh-CN`/`theme-color`；无 reduced-motion；`ToastHost` 硬编码 `aria-label`；`ConfirmDialog`/`RunDetailDialog` 无焦点陷阱与焦点归还。
12. **目标列表性能未达标**：500 目标 0.432 s，目标 <0.1 s；需要 `index.json` 第二阶段。
13. **启动性能未达标**：`--help` 0.848 s，目标 <0.5 s。
14. **覆盖率未达标**：77.05%，目标 82%；`web/app.py` 56%。
15. **无 gc/保留策略**：sessions/runs/targets 只增不减。
16. **供应链缺失**：无 pip-audit/npm audit/SBOM/Docker workflow。
17. **DNS rebinding 未防护**：`auth.py` 把环回客户端视为可信，未校验 Host。
18. **前端 chunk 335 KB**：未做路由级 lazy 拆分（P3）。

---

### 5.1 独立复审发现与处置

| 复审项 | 状态 | 证据 |
|--------|------|------|
| P0-01 solve/loop/team 吞失败 | **已修复** | solve/team/rounds/persistent 401 → exit 1；Web 默认 run → failed |
| P1-01 `_save_state` 非原子写 | **已修复** | 改用 `atomic_write_json`；快照读取测试 |
| P1-02 交付结论夸大 | **已修正** | 计划书/CHANGELOG 按引擎与 MCP 实际范围改写 |
| P2-01 终态 EventSource 无限重连 | **已修复** | 终态事件 `source.close()` |
| P2-02 team 子 Agent 仍打印 KB 提示 | **已修复** | team 子 Agent `console_output=False` + 测试 |
| P2-03 流式 token 恒为 0 | **已修复（估算）** | `_record_estimated_usage` + 测试；真实 usage 仍以 provider 为准 |
| P2-04 失败/中断任务无运行详情入口 | **部分修复** | History 增加「运行记录」列表，可直接打开任意 run；失败消息展示；续跑/证据抽屉仍未做 |
| P2-05 新路由零 HTTP 测试 | **已修复** | `tests/web/test_new_routes.py` 覆盖 8 个路由/状态码 |
| P2-06 prune 只在启动跑、不清 EventBus | **已修复** | `create_task` 触发 prune；`EventBus.forget` |
| P2-07 环形缓冲溢出无 gap | **已修复** | `event_gap` 事件 + 测试 |
| P2-08 DNS rebinding 未防护 | **已修复** | 环回客户端 Host 白名单；`VULNCLAW_WEB_ALLOWED_HOSTS` |
| P2-09 wheel 无 UI 断言 | **已修复** | `verify_dist_artifacts` 检查 wheel 内 `vulnclaw/web/dist/index.html` + 测试；dist 仍未纳入 git |
| P2-10 status.pending / README / 死代码 | **部分修复** | status.pending、并发 env 文档已补；`project_service.report_dir` 仍待 F-05 接线 |
| P2-07/08/09/10/11 可访问性 | **已修复** | 语言回落、lang/title、aria、焦点陷阱、reduced-motion；窄屏 rail 仍待查 |
| P3-1 终态后 set_completed 写 summary | **已修复** | 终态先返回 |
| P3-2 KeyboardInterrupt 记录 completed | **已修复** | Web `_run_task` 按 run.status 走 interrupted；CLI exit 130 |
| P3-3 import 即写盘 | **已修复** | 无变更时不 flush；读-only 测试 |
| P3-4 run_dir 绝对路径 | **已修复** | API 返回 run_name |
| P3-5 PoC 相对路径无基准说明 | **未修** | 报告文案仍待补 |
| P3-6 findings.json/sarif 全机覆盖 | **已修复** | 改为 `<report_stem>_findings/` |
| P3-7 300 事件断言过弱 | **已修复** | 收紧到 0.5 s + 保留策略用例 |
| P3-8 本地索引未 ignore | **已修复** | `.codegraph/`、`.cocoindex_code/`、`graft/`、`.mcp.json`、`.ignore` |
| P3-9 JSONL 缺失后 seq 重置 | **已修复** | TaskRecord.event_seq + EventBus.seed_sequence |

## 6. 执行编排

### Stage 0：冻结与复现（0.5–1 天）

| 任务 | 交付物 | 验收 |
|------|--------|------|
| 收独立复审报告 | 分级问题清单 | 每条有文件/行/复现 |
| 补失败用例 | `tests/agent/test_solve_llm_failure.py`、`test_team_llm_failure.py`、`test_persistent_llm_failure.py`、`tests/web/test_stream_gap.py`、`tests/web/test_shutdown_queued.py`、`tests/web/test_token_streaming.py`、`tests/web/test_report_download_types.py` | 当前代码上失败，失败原因正确 |
| 固化 mock 矩阵 | `scripts/mock_llm_server.py`（success/tool/stream/401/429/timeout/malformed） | 可重复启动，场景可切换 |

### Stage 1：正确性收口（1–2 天）

| 任务 | 交付物 | 验收 |
|------|--------|------|
| 失败传播贯穿所有引擎 | solver/loop/team/persistent 对 fatal 错误上抛 | `run --engine solve/team/rounds` 401 → exit 1；Web → failed |
| 流式 usage | 流式响应累计 usage 或按 chunk 估算；摘要字段有值 | mock 流式 usage → tokens_total > 0 |
| 报告下载类型 | JSON/SARIF 正确 MIME/扩展名；filter 支持 | 下载文件可被 jq/SARIF 工具读取 |
| 版本硬编码 | `codescan/report.py` 引用 `__version__`；测试扫描全仓 | 版本一致性测试覆盖 |
| SSE gap | 缓冲溢出发 `event_gap`；前端提示 | 慢消费者测试 |
| shutdown queued | 关机时 queued → stopped/interrupted | 测试断言 |

**Stage 1 出口：** P0 全部有真实失败复现与修复证据；P1 的 2/3/8/9/10 关闭。

### Stage 2：真实 E2E 与 UI 交互（2–3 天）

| 任务 | 交付物 | 验收 |
|------|--------|------|
| Playwright 环境 | `frontend/playwright.config.ts`、`e2e/` | `npx playwright test` 可跑 |
| 5 条主链路 | 首页任务、历史运行详情、发现处置、报告下载、stop 409/重连 | 每条截图 + 视频 + 断言 |
| UI 修复 | 焦点陷阱、`lang/title`、reduced-motion、aria、报告下载 | 截图 + axe 扫描 |
| 真实浏览器手工复核 | 1440/1024/768 截图 | 按钮可点、状态正确、无遮挡 |

**Stage 2 出口：** UI 截图验收不再只有首页；真实 E2E 5 条绿；无 console error。

### Stage 3：产品层闭环（3–4 天）

| 任务 | 交付物 | 验收 |
|------|--------|------|
| F-05 完整项目 | `project_id`、CLI `--project`、Web 切换器、项目报告目录、任务归属 | 跨项目隔离；报告落项目目录；E2E |
| F-07 报告中心 2.0 | 模板、脱敏、PDF、格式选择、SARIF 校验 | 同 run 多格式；无绝对路径/密钥 |
| F-09/F-12 UI | 边界页导出按钮、设置页 MCP 启停 | 真实点击 + 文件/配置读回 |
| P2-07～11 | 语言、lang/title、aria、焦点、reduced-motion | DOM/截图/axe |

### Stage 4：集成与自动化（3–4 天）

| 任务 | 交付物 | 验收 |
|------|--------|------|
| F-10 集成 | Jira/DefectDojo/Webhook dispatch | 本地 mock server：payload/重试/超时/幂等 |
| F-11 调度 | 进程内 scheduler + 通知 | 可控时钟：到点入队/串行/失败告警 |
| F-13 离线 | `--offline`、KB 预打包索引、doctor 离线体检 | 断网不挂起 |
| F-14 插件 | entry_points + 权限 + 版本校验 | 样例包发现/拒绝/不兼容提示 |

### Stage 5：质量与发布（2–3 天）

| 任务 | 交付物 | 验收 |
|------|--------|------|
| 覆盖率 | 补齐 `web/app.py` 分支 | ≥82%，app.py ≥90% |
| 目标索引 | `targets/index.json` | 500 目标 <0.1 s |
| CLI 启动 | 延迟导入 | `--help` <0.5 s |
| GC/保留 | `vulnclaw gc` | 幂等 + dry-run |
| 供应链 | pip-audit/npm audit/SBOM/Docker | CI job 绿 |
| 24h soak | soak 报告 | RSS 增长 <10%，无孤儿 |
| 版本 | bump 0.5.0 + changelog + wheel | 版本一致；wheel 内含 UI |

---

## 7. 功能验收矩阵

| 功能 | 正常 | 错误 | 边界 | 集成 | UI | E2E |
|------|------|------|------|------|----|-----|
| P0-01 失败语义 | 成功完成 | 401/429/超时 → failed/exit1 | 所有引擎 | CLI+Web+报告 | 错误展示 | 是 |
| SSE | 事件顺序 | 断线/重连/溢出 | Last-Event-ID/终态 | 前端订阅 | 状态更新 | 是 |
| 生命周期 | queued→running→completed | stop 409/初始化失败 | shutdown/重启 | 队列+事件 | 状态标签 | 是 |
| 持久化 | 事件/快照 | 崩溃/坏文件/迁移 | 保留策略 | 重启读取 | 历史 | 是 |
| F-04 运行详情 | 打开/时间线 | 404/空事件 | 长事件 | run.json/events | 弹窗 | 是 |
| F-06 发现处置 | 状态/备注 | 404/非法状态 | key 不一致 | target state | 下拉/备注 | 是 |
| F-05 项目 | 创建/切换/归属 | 重名/非法 slug | 跨项目隔离 | 任务/报告 | 切换器 | 是 |
| F-07 报告 | 多格式 | 生成失败/无权限 | 空报告/大报告 | findings 产物 | 预览/下载 | 是 |
| F-08 Token | 非流式+流式 | usage 缺失 | 0 token | 摘要/UI | 任务台 | 是 |
| F-09 审计 | jsonl/csv | 空事件/格式非法 | 大文件 | 边界页 | 导出 | 是 |
| F-10 集成 | mock 成功 | 超时/重试/幂等 | 大批 findings | 报告 | 配置 | 是 |
| F-11 调度 | 到点入队 | 失败告警 | 时钟边界 | 队列/通知 | 配置 | 是 |
| F-12 MCP | 启停 | 未知 server | 运行中任务 | 诊断 | 设置页 | 是 |
| F-13 离线 | 本地模型 | 断网/缺索引 | 无外网 | KB | 设置 | 是 |
| F-14 插件 | 发现/加载 | 权限/版本 | 重复 id | 执行 | 列表 | 是 |

---

## 8. 风险与停止条件

- **P0-01 已闭环**，但 429/timeout/malformed 的失败矩阵还没跑；在这些场景验证前，F-10/F-11/F-13/F-14 仍不应优先。
- **付费 API 预算 0**：真实 LLM 验收默认用本地 mock；除非你明确批准预算。
- **不 commit/push**：保守 profile，除非你明确要求。
- **不把 mock 当真实集成**：mock 只证明协议与分支；真实 provider 行为需另开预算。
- **不把「接口存在」当功能完成**：F-05/F-07/F-09/F-12 当前就是反例。
- **停止条件**：mock 矩阵无法覆盖流式工具调用、或独立复审发现 P0 设计冲突时，停下来报告，不硬改。

---

## 9. 下一步

1. 独立复审报告已收到并完成处置（见 5.1）。
2. Stage 2 13 条 E2E 已完成（新增集成配置增删改/测试、任务通知投递与投递历史、定时任务增删改、executive 模板报告、插件清单筛选、项目关联任务、历史快照）；剩余窄屏/键盘/console error 矩阵。
3. Stage 3 已完成：F-05 任务/项目/报告路由、CLI `--project`（并修复 `options.project` 422）；F-07 PDF/SARIF/JSON、报告密钥脱敏、`pentest/executive/ctf` 三模板（`vulnclaw report --template`、Web 报告中心、`session.report_template` 决定自动报告）。剩余：跨项目列表过滤。
4. Stage 4 已完成：F-10 集成 dispatch/config + 设置页「集成」分区（增删改/令牌保留/订阅事件/一键测试/投递记录与重投）、F-11 interval scheduler + 设置页「自动化」分区（定时任务增删改启停）+ 任务终态通知覆盖 webhook/Jira/DefectDojo、F-13 offline、F-14 entry_points/权限/版本 + 样例插件包 + `/api/plugins` 与 Web 插件页。
5. Stage 5 主要完成：0.5.0 版本、目标索引（0.012s）、`--help` 0.45s、全仓覆盖率 82.67%（不排除任何模块）、security/docker workflow、SBOM step；仍缺 24h 长稳与 security/docker workflow 的 CI 实跑。

**一句话：** P0-01 已从「默认 `run` 把 401 记成成功」修到「所有引擎 exit 1 / Web failed」，但 429/timeout/malformed 矩阵、真实 E2E、产品层闭环仍未完成。
