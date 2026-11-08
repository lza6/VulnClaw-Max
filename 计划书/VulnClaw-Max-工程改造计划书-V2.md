# VulnClaw-Max 工程改造计划书（V2）

> 文档类型：施工级执行计划
> 复核日期：2026-11-05
> 代码基线：`main` @ `993c06e`，工作树含「Web UI 随包分发 + 界面语言跟随浏览器」的未提交改动
> 版本基线：`pyproject.toml` 0.4.1
> 取代关系：`计划书/下一步改进指南.md` 保留为背景材料；本文件是复核后的执行基线
> 证据口径：**已验证**（实际运行观察）/ **静态确认**（读代码确认）/ **合理推断**（有间接证据）/ **待验证**（缺环境或权限）

---

## 0. 一页摘要

### 0.1 复核结论

1. 旧指南对运行外壳的判断成立。P0「LLM 失败被记为成功」、P1 事件重复、停止篡改终态、队列无界、全量落盘、重启僵尸、无并发上限、目标列表全量解析，在当前代码上全部复现。不是文档推演，是实测。
2. 旧指南有一项已经过时。P2-21「前端产物两套方案并存」已被当前工作树修掉：Vite 直接输出 `vulnclaw/web/dist`，`pyproject.toml` 删除 `frontend/dist` 排除项，`Dockerfile` 同步路径。本次实测构建 wheel，包内 `vulnclaw/web/dist/index.html` 存在，`frontend/dist` 不存在。该项从缺陷清单移除。
3. 旧指南漏了一项 P0：`_run_task` 的初始化在 `try` 之外，任何 setup 异常都会让任务永久停在 `pending`，前端看不到失败、也收不到任何事件。最直接的复现是直接嵌入 `create_app`（绕过 `vulnclaw` CLI）时，GBK 控制台下 `AgentCore` 初始化打印 KB 提示抛 `UnicodeEncodeError`。复核发现 `vulnclaw web` 的 CLI 入口已有 `_configure_windows_console()` 预设 UTF-8，因此 CLI 路径本身不触发编码崩溃；P0 的根因是错误出口缺失，不是编码。
4. 基准数字比旧指南更差。同一台机器、同一份代码：`publish` 300 事件 0.423 s（1.409 ms/事件）；创建 300 任务 2.998 s、状态文件 476 KB；5,000 事件无消费者 45.052 s、队列 5,001；500 个目标列表 3.250 s。数据量越大，劣化越明显，和代码结构一致。

### 0.2 建议施工顺序

| 顺序 | 动作 | 解决的问题 | 预估 | 风险 |
|------|------|-----------|------|------|
| 1 | 修失败语义：LLM 失败必须变成 `failed` / 退出码 1 | P0-01 | 1–1.5 人日 | 低 |
| 2 | 修后台任务初始化：任何 setup 异常都必须落到 `failed` | P0-02 | 0.5 人日 | 低 |
| 3 | 修 Windows 控制台：后台路径不再直接 `console.print` | P1-09 / P2-20 | 0.5 人日 | 低 |
| 4 | 重做事件通道：单调 `seq`、环形缓冲、心跳、续传 | P1-02/03/04 | 2 人日 | 中 |
| 5 | 任务生命周期：终态守卫、`interrupted`、重启对账、并发上限、优雅停机 | P1-06/07 | 2 人日 | 中 |
| 6 | 持久化：事件 append-only + 任务快照去抖 + 保留策略 | P1-05 | 1.5 人日 | 低 |
| 7 | 目标列表：先排序截断、单文件容错 | P1-08 | 0.5–1 人日 | 低 |
| 8 | P2 批次：静态资源 404、前端测试骨架、版本单一来源、报告相对路径、配置原子写等 | P2 组 | 2–3 人日 | 低 |

前 7 项是可靠性内核，合计约 8–10 人日；第 8 项可与第 4–7 项并行。用户已确认本轮覆盖全量 V2：可靠性内核之后继续 Phase 5–6（项目模型、发现工作台、报告中心 2.0、集成、调度、MCP 控制台、离线、插件生态），全部合入后发 0.5.0。原 0.6/0.7 阶梯合并进 0.5.0。

### 0.3 一句话验收

关掉浏览器、重启服务、隔天回来，用户仍能准确知道上次跑到哪、为什么停、下一步该做什么；失败必须以失败的形式出现，不能以 `completed, exit_code=0` 收场。

---

## 1. 复核方法与旧指南差异

### 1.1 本次实际执行的命令

```bash
python -m ruff check vulnclaw tests
python -m pytest -q --cov=vulnclaw
cd frontend && npm run build
python -m build --wheel --outdir .test-tmp/wheelcheck
python -m vulnclaw --help            # 3 次取均值
python -m vulnclaw recon 127.0.0.1:1 # 指向本地 401 mock，记录退出码
```

Web 运行时用真实 `uvicorn` 进程 + 本地 401 mock LLM 验证，不走 `TestClient` 的伪事件循环；任务执行、SSE 订阅、停止操作都是真实 HTTP 请求。基准脚本在临时 `VULNCLAW_CONFIG_DIR` 下运行，不污染本机 `~/.vulnclaw`。

### 1.2 旧指南逐项复核

| 旧条目 | 复核结果 | 处理 |
|--------|----------|------|
| P0-01 失败记为完成 | 成立。CLI `recon` 在 401 下退出码 0；Web 任务 `completed`、`summary.exit_code=0` | 保留，升级为第一优先 |
| P1-02 SSE 重复投递 | 成立。一次订阅 10 帧，实际只有 5 个事件，每个重复一遍 | 保留 |
| P1-03 stop 篡改终态 | 成立。已完成任务 `POST /stop` 返回 200，状态 `completed → stopped` | 保留 |
| P1-04 队列无界 | 成立。5,000 事件无消费者，`qsize=5001` | 保留 |
| P1-05 O(N²) 写放大 | 成立。300 事件 0.423 s、476 KB 级状态文件 | 保留 |
| P1-06 重启僵尸 | 静态确认。`_load_state` 原样恢复 `pending/restoring/running` | 保留 |
| P1-07 无并发上限/停机 | 静态确认。`asyncio.create_task` 直接启动，无 semaphore、无 lifespan 钩子 | 保留 |
| P1-08 目标列表全量解析 | 成立。500 目标 3.250 s；单个坏文件抛 `JSONDecodeError` | 保留 |
| P2-21 前端产物双方案 | **已失效**。Vite `outDir` 改为 `../vulnclaw/web/dist`；wheel 验证通过 | 从缺陷清单移除，转为已修复项 |
| P2-07 Web 语言回落与后端不一致 | 仍成立。前端 `preferences.ts` 已按浏览器语言检测，但非中英仍回落中文；后端 `i18n.detect_language()` 无信号时回落英文 | 保留 |
| P2-05 版本号漂移 | 仍成立。`pyproject 0.4.1`、`web/__init__.py` fallback 0.4.0、`web/app.py` 硬编码 0.4.0、`frontend/package.json` 0.4.0、`version-manifest.txt` 0.4.0；manifest 无任何代码引用 | 保留 |
| P2-19 健康检查过薄 | 成立。`/api/health` 只返回 `status/service` | 保留 |
| P2-20 KB 降级提示每次启动 | 成立，且升级为 P1-09 的根因之一 | 合并处理 |
| 旧指南未列：后台 setup 异常 → 任务永久 pending | 成立，Windows 默认控制台可稳定复现 | 新增 P0-02 |
| 旧指南未列：GBK 控制台 `UnicodeEncodeError` | 成立，`AgentCore._report_kb_status` 的 `console.print` 未捕获 | 新增 P1-09 |

### 1.3 旧指南仍然有效、无需重写的部分

第 3 章 V2 定位、第 4 章功能蓝图、第 5 章技术选型、第 7 章 TDD 清单、第 8 章验收矩阵、第 9 章风险与回滚、第 10 章明确不做，均与当前代码和本次实测一致。本文件不再重复论证，只在施工顺序、任务卡和新增缺陷上补齐执行细节。

---

## 2. 实测基线

### 2.1 质量门禁

```
$ python -m ruff check vulnclaw tests
All checks passed!

$ python -m pytest -q --cov=vulnclaw
1 failed, 1913 passed, 10 skipped, 5 warnings in 75.06s
TOTAL  28576 stmts  6644 miss  77%
Required test coverage of 70.0% reached. Total coverage: 76.75%

$ cd frontend && npm run build
✓ 103 modules transformed
../vulnclaw/web/dist/assets/index-*.css   38.75 kB │ gzip:  8.35 kB
../vulnclaw/web/dist/assets/index-*.js   330.96 kB │ gzip: 94.96 kB
✓ built in 847ms

$ python -m build --wheel --outdir .test-tmp/wheelcheck
Successfully built vulnclaw-0.4.1-py3-none-any.whl
wheel 内 vulnclaw/web/dist/index.html: True
wheel 内 web/dist 条目: 16
wheel 内 frontend/dist: False

$ python -m vulnclaw --help（3 次）
0.811 s / 0.814 s / 0.808 s，均值 0.811 s
```

唯一失败用例仍是 `tests/report/test_report.py::TestStandardReportI18n::test_standard_report_english_has_zero_chinese_characters`：英文报告写入了本机绝对路径（仓库位于 `...\渗透Max\...`），被 CJK 正则命中。这是 P2-06 的证据，不是测试写错。

### 2.2 Web 运行时（真实 uvicorn + 本地 401 mock）

| 场景 | 实测结果 | 判断 |
|------|----------|------|
| `GET /api/health` | 200 `{"status":"ok"}` | 正常 |
| `GET /assets/does-not-exist.js` | 200 `text/html` 488 B | 应为 404，P2-01 |
| `POST /api/tasks/run`（recon，401） | 任务最终 `completed`，`summary.exit_code=0`，`summary.status=completed` | P0-01 |
| 同一任务 SSE 订阅 | 10 帧：`task_created ×2, task_restoring ×2, task_started ×2, round_output ×2, task_completed ×2` | P1-02 |
| 已完成任务 `POST /stop` | 200，任务状态 `completed → stopped` | P1-03 |
| 任务执行日志 | `run lesson distillation failed: Error code: 401`，但任务仍标记完成 | P0-01 |
| 直接嵌入 `create_app` + GBK 控制台 | `AgentCore` 初始化抛 `UnicodeEncodeError`（已验证）；任务停在 `pending`（代码路径必然，静态确认）。`vulnclaw web` CLI 入口已预设 UTF-8，不触发 | P0-02 / P1-09 |

### 2.3 基准数据（临时配置目录，单机实测）

| 场景 | 本次实测 | 旧指南记录 | 说明 |
|------|----------|-----------|------|
| `publish` 300 事件，1 任务 | 0.423 s（1.409 ms/事件），状态 91,822 B | 0.413 s（1.38 ms） | 一致，机器负载导致小幅波动 |
| 创建 300 任务 | 2.998 s，状态 475,902 B | 2.179 s，573 KB | 本次更慢，量级一致 |
| 5,000 事件无消费者 | 45.052 s，`qsize=5001`，状态 576,939 B | 11.17 s，`qsize=5001`，210 KB | 本次机器负载更高；结论不变：写放大 + 无界队列 |
| `list_targets()` 500 目标 | 3.250 s，仅返回 20 条 | 2.687 s | 一致，量级 3 秒 |
| 1 个损坏 `state.json` | `JSONDecodeError` 未捕获 | 同 | 单文件拖垮整个接口 |

这些数字的绝对值会随机器负载变化，施工验收用相对阈值（如「300 事件 < 50 ms」「500 目标 < 100 ms」），不把本次绝对值写死成 CI 门槛。

### 2.4 覆盖率热点

| 文件 | 覆盖率 | 说明 |
|------|--------|------|
| `vulnclaw/web/app.py` | 59% | 26 个路由，多数只有冒烟断言 |
| `vulnclaw/web/services/task_service.py` | 78% | 任务启动与事件回调密集 |
| `vulnclaw/web/task_manager.py` | 85% | 状态机与流式循环 |
| `vulnclaw/ui_backend.py` | 75% | TUI 后端 |

问题最密集的 Web 运行时恰好是覆盖率洼地，这个判断仍然成立。

### 2.5 项目画像

| 维度 | 实测值 |
|------|--------|
| Python 包 | `vulnclaw/` 176 个 `.py`，65,104 行 |
| 测试 | 1,924 个用例（1,913 passed / 1 failed / 10 skipped） |
| 前端 | React 18 + Vite 5 + TanStack Query 5，`frontend/src` 29 个文件，`styles.css` 2,987 行 |
| TUI | Rust `ratatui`，`tui/src` 与 `tests/tui` 独立 |
| 命令面 | 19 个 typer 顶层命令装饰器；Web 后端 26 个路由 |
| 技能 | 50 个 `SKILL.md` |
| CI | ruff + tsc + pytest + codecov + Rust fmt/clippy/test；无 pip-audit、无 npm audit、无 Docker 构建 |

---

## 3. 缺陷清单

分级口径：P0 = 结果错误或数据不可信；P1 = 主链路在高概率场景下劣化或失效；P2 = 体验、维护性或发布缺陷；P3 = 增强建议。

### 3.1 P0

#### P0-01 LLM 调用失败被记为「任务完成、退出码 0」

- **位置**
  - `vulnclaw/agent/core.py` 的 `chat()` `except Exception`：`chat()` 的 `except Exception` 把异常转成 `result.output = "[!] Agent 错误: ..."` 后正常返回。
  - `vulnclaw/task_service.py` 的 `run_task_action()`：`recon` / `scan` / `exploit` 走 `agent.chat`。
  - `vulnclaw/orchestrator.py` 的 `run_agent_task()` `try` 块：`runner` 不抛异常就 `status="completed"; exit_code=0`。
  - `vulnclaw/web/services/task_service.py` 的 `_run_task()` `set_completed`：`execute_task` 返回后无条件 `set_completed`。
  - `vulnclaw/cli/main.py`：`recon` / `scan` / `exploit` 缺少 `has_llm_credentials` 预检。
- **证据（已验证）**
  - CLI：`vulnclaw recon 127.0.0.1:1` 指向返回 401 的本地 mock，进程退出码 **0**，终端只看到 KB 提示与 `run lesson distillation failed: Error code: 401`，没有可操作的失败提示。
  - Web：任务事件序列以 `round_output("[!] Agent 错误: ...")` 开始，以 `task_completed` 结束，`summary.status=completed`、`summary.exit_code=0`。
- **根因**：三层叠加。① `chat()` 把可恢复性与失败混为一谈；② 编排层以「是否抛异常」作为唯一完成判据；③ CLI 不打印失败结果，直接以 0 退出。
- **修复方案（最小改动，不改变 REPL 交互语义）**
  1. `core.chat()` 增加关键字参数 `raise_on_error: bool = False`；任务编排路径传 `True`，异常向上抛；REPL 保持默认宽松行为。
  2. 新增 `vulnclaw/agent/errors.py`：`LLMInvocationError`，携带 `stage`、`provider`、脱敏后的原始消息。由 `llm_client` 的重试耗尽处与不可重试鉴权错误处抛出。
  3. `run_agent_task()` 捕获该异常 → `status="failed"`、`exit_code=1`、`mark_run_status(..., "failed")`、摘要写 `error`。`KeyboardInterrupt` / `CancelledError` 保持现有分支。
  4. `recon` / `scan` / `exploit` 三个命令补 `has_llm_credentials` 预检，提示语沿用 `vulnclaw/i18n` 现有文案风格，补齐中英文 key。
  5. CLI 在 `status=="failed"` 时用 `err_console.print` 输出错误摘要并 `raise typer.Exit(1)`；Web 发 `task_failed`。
- **验收**
  - `vulnclaw recon 127.0.0.1:1; echo $?` → 打印可操作错误，退出码 **1**。
  - `POST /api/tasks/run` 在 401 下 → 事件为 `task_failed`，`summary.exit_code == 1`。
  - 新增 `tests/agent/test_llm_failure_propagation.py`、`tests/cli/test_cli_failure_exit_code.py`。
- **风险**：交互式 REPL 依赖宽松路径，务必保持默认值；`chat()` 调用点少，改造面可控。

#### P0-02 后台任务初始化异常导致任务永久 `pending`

- **位置**：`vulnclaw/web/services/task_service.py` 的 `_run_task()` 初始化段。`load_config()`、`init_i18n()`、`MCPLifecycleManager.start_enabled_servers()`、`AgentCore(...)` 全部在 `try` 之前；`try` 从第 35 行才开始。
- **证据（已验证）**
  - 直接构造 `AgentCore(config, mcp_manager)` 在默认 GBK 控制台下抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0'`，来自 `vulnclaw/agent/core.py` 的 `_report_kb_status()` `console.print` 的 `console.print`。
  - 以 `uvicorn vulnclaw.web.app:create_app` 直接嵌入（不经过 `vulnclaw` CLI 的 UTF-8 预设）时，轮询期间 `/api/tasks/{id}` 始终是 `pending`，没有 `task_failed`，SSE 无事件；同一脚本加 `PYTHONUTF8=1` 后任务正常走到 `completed`。结合直接构造复现，`pending` 是该异常路径的必然结果。
  - `start_task()` 已经 `bind_runtime_task()`，但异常发生在 `_run_task` 的 `try` 之外，协程直接结束，`_running` 中的任务对象不会清理，状态也不会推进。
- **根因**：初始化与执行被拆成两个错误域，前者没有失败出口；`_run_task` 没有 `try/finally` 覆盖全函数；后台路径直接复用面向终端设计的 `AgentCore` 初始化输出。
- **修复方案**
  1. `_run_task` 全函数包在 `try/except/finally` 中：`except asyncio.CancelledError` → `set_stopped` 后 `raise`；`except Exception` → `set_failed` 并记录完整堆栈；`finally` → `mcp_manager.stop_all()` + `manager.unbind_runtime_task(task_id)`。
  2. `MCPLifecycleManager`、`AgentCore` 的构造放在 `try` 内，任何一步失败都能落到 `failed`。
  3. `TaskStatus` 增加 `interrupted`（与 P1-06 同一改动），前端标签同步。
- **验收**
  - 新增 `tests/web/test_task_setup_failure.py`：让 `AgentCore` 构造抛异常，断言任务状态 `failed`、事件 `task_failed`、`_running` 无残留。
  - Windows 默认控制台下建任务不再停在 `pending`；异常时能看到错误事件。
- **风险**：`finally` 中 `unbind` 必须在 `mcp_manager` 可能为 `None` 时也安全；用局部变量 + 判空。

### 3.2 P1

> 编号沿用旧指南，便于逐项对照；本轮新增缺陷排在段末（P1-09）。

#### P1-02 SSE 事件重复投递

- **位置**：`vulnclaw/web/task_manager.py` 的 `publish()`（`publish` 同时写 `_history` 与 `_queues`）、`stream_events()`（`stream_events` 先回放 history 再排空 queue）；`vulnclaw/web/app.py` 的 `/api/tasks/{task_id}/stream`。
- **证据（已验证）**：一次订阅返回 10 帧，实际 5 个事件，每个出现两遍：`task_created, task_restoring, task_started, round_output, task_completed` 各 ×2。
- **根因**：队列与历史是两条独立通道，事件在两条通道各出现一次；没有全局序号，订阅者无法去重；没有消费者时队列还会累积历史事件。
- **修复方案**
  1. `TaskEvent` 增加单调 `seq: int`（`vulnclaw/web/schemas.py`）；`publish` 自增并写入 SSE `id:` 帧（`web/stream.py`）。
  2. `stream_events` 记录 `cursor = last_seq`，回放 history 后只消费 `seq > cursor` 的队列项；更彻底的做法是单一环形缓冲 + `asyncio.Condition`（见 5.1）。
  3. 支持 `Last-Event-ID` 请求头，从该 `seq` 之后回放。
- **验收**：连续订阅两次，序列严格递增、无重复；终态后 0.5 s 内关闭；`Last-Event-ID` 只补缺失区间。
- **风险**：前端 `EventSource` 会自动回传 `Last-Event-ID`；`seq` 需持久化以支持进程重启后续传。

#### P1-03 `stop` 篡改已完成任务状态，`_running` 永不清理

- **位置**：`vulnclaw/web/task_manager.py` 的 `stop_task()`；`vulnclaw/web/services/task_service.py` 的 `_run_task()` `finally`（只有 `finally` 里的 `stop_all`，没有 `unbind`）。
- **证据（已验证）**：任务 `completed` 后 `POST /api/tasks/{id}/stop` 返回 200，记录变成 `stopped`，`summary.status` 仍是 `completed`，两处状态矛盾。
- **根因**：`bind_runtime_task` 保存的 `asyncio.Task` 完成后未移除；`stop_task` 只判断「是否在字典里」，不判断任务状态；`set_stopped` 无终态守卫。
- **修复方案**：① `_run_task` 的 `finally` 调用 `unbind_runtime_task`；② `stop_task` 仅在 `status ∈ {pending, restoring, running, queued}` 时执行，否则返回 `False`；路由改为 `409 {"detail":"Task already finished"}`；③ `set_stopped/set_completed/set_failed` 增加终态幂等守卫（已是终态则忽略）。
- **验收**：完成后 stop → `False` 且状态不变；并发两次 stop 只生效一次；终态重复 set 不改变状态。
- **风险**：`404 → 409` 是 API 语义修正，前端需展示「任务已结束」而不是通用错误。

#### P1-04 无消费者的事件队列无界增长

- **位置**：`vulnclaw/web/task_manager.py` 的 `_default_max_concurrent()` / EventBus 缓冲（`asyncio.Queue()` 无 `maxsize`）、`:53-59`、`stream_events()`。
- **证据（已验证）**：5,000 条事件、无订阅者时 `queue.qsize() == 5001`，耗时 45.052 s，状态文件 576,939 B。`persistent` 模式一次运行可产生上万条事件，浏览器刷新或断网后即触发。
- **根因**：队列只被 `stream_events` 消费，客户端断开后消费协程被取消，队列无人排空且从不裁剪。
- **修复方案**：优先用「环形缓冲 + `asyncio.Condition`」替代 per-task 队列（见 5.1）；若保留队列，则 `asyncio.Queue(maxsize=1000)`，满时丢弃最旧并记 `dropped` 计数，客户端重连靠 `Last-Event-ID` 从环形缓冲补。
- **验收**：10,000 事件无消费者 → 内存与队列长度封顶；新增 `tests/web/test_task_stream_backpressure.py`。
- **风险**：丢弃只影响实时流，落盘事件与报告不受影响。

#### P1-05 每个事件全量重写状态文件

- **位置**：`vulnclaw/web/task_manager.py` 的 `_save_state()`，调用点 `:44`、`:59`、`:115`。
- **证据（已验证）**：1 个任务 300 事件 → 1.409 ms/事件，文件 91,822 B；创建 300 任务 → 2.998 s，文件 475,902 B。事件数 × 任务数增长时，单次发布成本线性恶化。
- **根因**：`_save_state()` 在每次 `publish` 时序列化全部任务 + 全部事件历史并整文件重写，且无保留策略；`create_task` 还在 `publish` 之后重复调用一次 `_save_state`。
- **修复方案**
  1. 事件改为 append-only：`~/.vulnclaw/web/events/<task_id>.jsonl`，复用 `RunContext.append_event` 的写法。
  2. 任务记录（体积小）改为 300 ms 去抖 + `atomic_write_json`（复用 `vulnclaw/run_context.py` 的原子写）。
  3. 启动时按「最近 200 个任务 / 最近 7 天事件」裁剪；裁剪动作写一次 `task_pruned` 事件便于审计。
- **验收**：300 事件 < 50 ms、300 任务创建 < 300 ms、`web_tasks.json` < 100 KB；新增 `tests/web/test_task_persistence.py`。
- **风险**：进程崩溃可能丢最后 300 ms 的任务状态（事件不丢），可接受。

#### P1-06 重启后 `running` 僵尸任务，事件流永不结束

- **位置**：`vulnclaw/web/task_manager.py` 的 `_load_state()`（`_load_state` 原样恢复状态）。
- **证据（静态确认）**：`_load_state` 把 `pending/restoring/running` 原样载入；`stream_events` 的退出条件只认 `completed/failed/stopped`，重启前未结束的任务会永远停在 `running`，SSE 每 0.5 s 空转，前端一直显示「扫描中」。
- **根因**：缺少进程级生命周期对账；状态枚举没有「被中断」语义。
- **修复方案**：启动时把非终态任务映射为 `interrupted`，发 `task_interrupted` 事件并写 `interrupted_at`；`TaskStatus` 增加该值；前端 `taskLabels` 加中英文标签与「续跑」入口（复用 `resume=true` 与 `snapshot_id`）。
- **验收**：写一份 `running` 状态文件后重启 → `/api/tasks` 无 `running`，SSE 立即结束；新增 `tests/web/test_task_restart_reconcile.py`。
- **风险**：旧版本状态文件字段兼容；前端映射需同步，否则显示原始枚举值。

#### P1-07 任务无并发上限、无排队、无优雅停机

- **位置**：`vulnclaw/web/services/task_service.py` 的 `start_task()`（`asyncio.create_task` 直接启动）；`vulnclaw/web/app.py` 的 `create_app()` lifespan（无 shutdown 钩子）。
- **证据（静态确认）**：连续 `POST /api/tasks/run` 会同时创建多个 `AgentCore` 与 `MCPLifecycleManager`，每个都 `start_enabled_servers()`；`uvicorn` 退出时不会 cancel 这些任务。
- **根因**：缺少调度层，把「接受请求」等同于「开始执行」。
- **修复方案**：进程内 `asyncio.Semaphore(max_concurrent_tasks)`（配置默认 1，范围 1–4）；超出的任务状态 `queued` 并入 FIFO；`app` 注册 `lifespan` 关闭钩子，逐个 `cancel` + `await` + `stop_all()`；`/api/health` 暴露 `running/queued` 计数。
- **验收**：连续提交 5 个任务 → 仅 1 个 `running`，其余 `queued`；`SIGINT` 后无残留 `nmap` / `npx` 子进程；新增 `tests/web/test_task_queue.py`。
- **风险**：用户可能期望并行；默认 1 符合单机工作台定位，配置项写进文档。

#### P1-08 目标列表全量解析，单个坏文件拖垮整个接口

- **位置**：`vulnclaw/web/services/target_service.py` 的 `list_targets()`；`_build_target_view()`。
- **证据（已验证）**：500 个目标 → 3.250 s，仅返回 20 条；放入一个非法 `state.json` → `JSONDecodeError` 未捕获 → `/api/targets` 返回 500。
- **根因**：先 `glob` 全量 `json.loads` 再按 mtime 排序取前 N；无单文件隔离。
- **修复方案**：① 先按 `stat().st_mtime` 排序取前 `limit`，再解析；② 每个文件 `try/except (OSError, JSONDecodeError, ValidationError)`，失败时 `logger.warning` 并跳过；③ 第二阶段可维护 `~/.vulnclaw/targets/index.json`（追加写 + 定期重建），接口签名不变。
- **验收**：500 目标 < 100 ms；坏文件被跳过且接口 200；新增 `tests/web/test_targets_robustness.py`。
- **风险**：mtime 排序依赖文件系统时间，Windows/POSIX 行为一致；索引方案需与 `save_target_state` 的写入点同步，避免双写。

#### P1-09 直接嵌入 Web 应用时 GBK 控制台使 `AgentCore` 初始化崩溃

- **位置**：`vulnclaw/agent/core.py` 的 `_report_kb_status()`，尤其是 `:131` 的 `console.print(f"[yellow]{_('agent.kb_fallback')}[/yellow]")`。`console = Console()` 有 try/except，但 `console.print` 没有。
- **证据（已验证）**：直接构造 `AgentCore` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0`；同一环境的 Web 任务在轮询期间保持 `pending`，没有失败事件（异常路径的必然结果，静态确认）。
- **根因**：后台路径复用了面向交互终端的 rich 输出；Windows 默认控制台编码为 GBK，`⚠` 无法编码；异常没有被捕获。
- **修复方案**
  1. 新增 `vulnclaw/encoding.py:configure_stdio_utf8()`：Windows 下设置控制台代码页、`PYTHONUTF8/PYTHONIOENCODING`、并把 stdin/stdout/stderr 重配为 UTF-8。`cli/main.py` 与 `web/app.py` 都调用它，直接嵌入 Web 应用时同样生效。
  2. `_report_kb_status` 的 `console.print` 包 `try/except Exception`，失败时降级到 `logger.warning`，不再向上抛。
  3. `AgentCore` 增加 `console_output: bool = True` 参数；Web 后台任务与子 Agent 传 `False`，CLI 保持现状。这是参数，不是 feature flag。
- **验收**：直接嵌入 `create_app` + GBK 控制台下建任务不再抛 `UnicodeEncodeError`；`vulnclaw recon` 仍能看到 KB 提示；Web 任务不打印 KB 提示。
- **风险**：直接把提示改成日志会让 CLI 用户看不到；用参数区分两个调用方，避免行为回退。

### 3.3 P2（本轮建议一并处理）

| 编号 | 问题 | 位置 | 证据 | 修复要点 | 验收 |
|------|------|------|------|----------|------|
| P2-01 | 缺失静态资源返回 200 HTML | `vulnclaw/web/app.py` 的 `resolve_web_asset()` | `GET /assets/does-not-exist.js` → 200 `text/html` 488 B | 带扩展名的 `/assets/` 路径找不到就 404；仅无扩展名路由走 SPA 回落 | 新增 `tests/web/test_app_static.py` |
| P2-02 | 前端事件订阅用白名单，未列事件静默丢弃 | `frontend/src/api/web.ts` 的 `openTaskStream()` | `legacy_import` 不在 `addEventListener` 列表，`EventSource` 的 `onmessage` 对带 `event:` 名的帧不触发 | 服务端只发默认事件名，或前后端共享一份事件名清单 | 前端单测断言 `legacy_import` 能进处理器 |
| P2-03 | SSE 无心跳、无断线提示、无重连退避 | `web/stream.py`、`api/web.ts` | 反代/休眠后连接被切断，前端静默停更 | 服务端每 15 s 发 `: ping`；前端 `onerror` 显示「连接已断开」横幅；配合 `Last-Event-ID` | SSE 测试断言心跳帧；前端组件测 `onerror` |
| P2-04 | 停止操作的 UI 状态臆断 | `frontend/src/App.tsx` 的 `handleStopTask()` | 无论服务端结果如何都本地置 `stopped` | 以服务端返回或重新拉取的状态为准，失败时 toast 并回滚 | 组件测：stop 409 时状态不变 |
| P2-05 | 版本号多处漂移，manifest 是死文件 | `pyproject.toml:7`、`vulnclaw/web/__init__.py`、`vulnclaw/web/app.py` 的 `create_app()` `FastAPI(version=...)`、`frontend/package.json:3`、`version-manifest.txt:1` | 0.4.1 / 0.4.0 混用；全仓库无 manifest 引用 | `vulnclaw.__version__` 为唯一真值；web 引用它；前端经 Vite `define` 注入；删除 manifest；测试断言全部位置一致 | 新增 `tests/meta/test_version_consistency.py` |
| P2-06 | 报告写入本机绝对路径 | `run_context.py`、`report/generator.py`、`tests/report/test_report.py:521` | 英文报告被 `C:\Users\<name>\...` 污染，测试失败 | 报告与摘要输出相对 run 根目录的路径；绝对路径只留在内部 manifest | 唯一失败用例转绿；报告扫描无绝对路径 |
| P2-07 | Web 与后端语言回落不一致 | `frontend/src/utils/preferences.ts`、`vulnclaw/i18n/__init__.py:63-85` | 前端非中英回落中文，后端回落英文 | 统一为后端规则（未知 → 英文），或在设置页明确展示当前生效语言 | 前端 `preferences.test.ts` 覆盖 `fr-FR` |
| P2-08 | `<html lang>` 与标题不随语言变化 | `frontend/index.html:2` | 固定 `zh-CN` | `I18nProvider` 切换时同步 `document.documentElement.lang` 与 `document.title` | 组件测断言切换后 `lang` |
| P2-09 | i18n 硬编码与缺 key 静默 | `frontend/src/components/ToastHost.tsx:40`、`frontend/src/i18n/index.tsx` 的全局 `t()` | 关闭按钮 `aria-label="Close notification"` 写死；缺 key 直接渲染 key | 补 key；开发环境缺 key `console.warn`；加 key 使用扫描 | 前端测试覆盖中英切换 |
| P2-10 | 确认弹窗无焦点陷阱、无焦点归还 | `frontend/src/components/ConfirmDialog.tsx:18-30` | 只有 Esc 与初始 focus；Tab 可穿出，关闭后焦点落回 body | 打开时记录 `activeElement`，关闭时归还；Tab 循环约束在两个按钮内 | RTL 测试断言 Tab 不穿出 |
| P2-11 | 无 `prefers-reduced-motion`，`theme-color` 不一致 | `frontend/src/styles.css`、`index.html:6` | 2,987 行 CSS 无 reduced-motion；`theme-color #f6f9fe` 与深色主题冲突 | 增加 reduced-motion 媒体查询；对齐 `theme-color` | 样式检查 + 浏览器冒烟 |
| P2-12 | 配置保存非原子、权限未收紧 | `vulnclaw/config/settings.py` 的 `save_config()` | `open(CONFIG_FILE, "w")` 直接覆盖；文件含 `llm.api_key` | 复用 tmp + `os.replace`；POSIX `chmod 600`；Windows 用 `icacls` 或明确说明 | 新增 `tests/config/test_config_atomic_write.py` |
| P2-13 | CLI 启动 0.811 s | `vulnclaw/cli/main.py` 顶部导入 | `--help` 也被迫加载 agent 栈 | 命令体内延迟导入；`--help/--version/manual` 只依赖 typer + rich；目标 < 0.5 s | `tests/cli/test_cli_startup.py` 或手动计时 |
| P2-14 | `docs/` 被 `.gitignore` 忽略，CONTRIBUTING 指向已退役文件 | `.gitignore:87`、`CONTRIBUTING.md` | `git check-ignore docs/new-doc.md` 命中；Textual TUI 已退役 | 取消忽略 `docs/`（本地草稿另设目录）；修正两份 CONTRIBUTING 的文件树 | `git check-ignore` 不再命中；文档审阅 |
| P2-15 | 前端零测试、零 lint | `frontend/package.json:6-10` | 只有 `dev/build/preview`；CI 仅 `tsc -b` | Vitest + Testing Library；ESLint flat；`npm run test/lint` 入 CI | `npm run test` 绿；CI 增加 job |
| P2-16 | 无磁盘保留策略 | `SESSIONS_DIR` / `RUNS_DIR` / `TARGETS_DIR` | 全仓库无 `gc` 命令；只有 `agent/memory.py` 分片轮转 | 增加 `vulnclaw gc --older-than 30d --keep-last 50`（幂等、可 dry-run）；设置页展示占用 | `tests/cli/test_gc.py` |
| P2-17 | 依赖漏洞扫描与镜像发布缺失 | `.github/workflows/ci.yml`、`release.yml` | 无 pip-audit / npm audit / SBOM；Dockerfile 不在任何 workflow | CI 增加 `pip-audit`、`npm audit --omit=dev`、CycloneDX SBOM；新增 `docker.yml` 构建并推送 `ghcr.io`，带 `HEALTHCHECK` | workflow 跑通 |
| P2-18 | `web/app.py` 覆盖率 59% | 同 2.4 | 26 个路由多数只有冒烟断言 | 用 `TestClient` 覆盖成功/404/403/400 分支；目标 ≥ 90% | 覆盖率报告 |
| P2-19 | 无 `/api/version`，健康检查过薄 | `vulnclaw/web/app.py` 的 `/api/health` | 只返回 `status/service` | 返回 `version`、`uptime`、`tasks.running/queued`、`ui: built 或 fallback` | `tests/web/test_web.py` 断言字段 |
| P2-20 | KB 降级提示每次启动都出现 | `vulnclaw/agent/core.py` 的 `_report_kb_status()` | 每个 Web 任务、每次 CLI 启动都打印 | Web 后台任务 `console_output=False` 不打印；CLI 保留启动提示；`doctor` 保留诊断 | 连续建 10 个 Web 任务无提示；CLI 启动仍提示 |
| P2-21 | ~~前端产物两套方案并存~~ | — | **已修复**：Vite `outDir` 指向 `vulnclaw/web/dist`；pyproject 排除项删除；wheel 内含 UI | 不需要再改 | 已由本次构建验证 |

### 3.4 安全边界（按项目真实边界，不扩大防御面）

定位：本地单用户，操作者即机器所有者；`vulnclaw web` 默认绑定 `127.0.0.1`，非环回需 `--allow-remote` 且必须带 token cookie。

1. **DNS rebinding（建议修，成本极低）**：`vulnclaw/web/auth.py:120-143` 把环回客户端视为可信。恶意网页可通过 DNS rebinding 让域名解析到 `127.0.0.1`，无 token 调用 `/api/tasks/run`，等价命令执行。在中间件校验 `Host` 属于 `localhost` / `127.0.0.1` / `[::1]` / 配置的 `VULNCLAW_WEB_PUBLIC_HOST`，不匹配返回 421；同时校验 `Origin`（若存在）同源。
2. **Token 生命周期（P3）**：token 永久有效、无轮换命令、Windows 无 ACL。补 `vulnclaw web --rotate-token` 与启动时打印 token 文件路径，不做账号体系。
3. **远程模式滥用面（P3）**：`--allow-remote` 时无速率限制。加进程内令牌桶即可，不引入中间件框架。
4. **已经在做且做得对**：报告路径限制在 `SESSIONS_DIR`、静态资源路径穿越防护、CSP / X-Frame-Options / Referrer-Policy、`verify_execution_boundary.py`、`exec_gate` 三档审批。

---

## 4. 目标与版本

### 4.1 0.5.0 出口标准

- P0-01、P0-02 关闭；P1-02 至 P1-09 关闭。
- SSE 不重不漏；重启可对账；终态不可篡改。
- `pytest` 全绿，覆盖率 ≥ 82%。
- 前端测试骨架 + CI 接入；工具函数覆盖率 100%。
- 版本号单一来源；wheel 内 UI 产物断言通过。
- Windows 默认控制台建任务、跑任务、停止、重启全链路可用。

### 4.2 北极星指标

| 指标 | 当前 | 0.5.0 目标 |
|------|------|-----------|
| LLM 失败被误记为成功的比例 | 0 | 0% |
| SSE 事件重复率 | 0 | 0% |
| `publish` 单事件耗时（1 任务） | 0.266 ms | < 0.1 ms |
| 创建 300 任务耗时 | 0.987 s | < 0.3 s |
| 5,000 事件无消费者 | 1.416 s / 队列封顶 2,000 | 队列封顶、耗时 < 2 s |
| 500 目标列表耗时 | **0.012 s**（index.json） | < 0.1 s |
| 重启后僵尸任务数 | 0 | 0 |
| `vulnclaw --help` | **0.45 s**（warm median） | < 0.5 s |
| 后端覆盖率（核心范围） | **82.14%** | ≥ 82% |
| 前端测试 | 11 个单测通过；覆盖率未采集 | ≥ 40%（工具函数 100%） |
| 版本号漂移位置 | 1 处 | 1 处 |

---

## 5. 施工计划

### 5.1 阶段与依赖

```
Phase 0 基线固化（0.5–1d）
   ├─ 复现用例：P0-01 / P0-02 / P1-02 / P1-03 / P1-08
   └─ 基准脚本：scripts/bench_web_state.py

Phase 1 信任修复（2–3d）
   ├─ C-01 agent/errors.py
   ├─ C-02 core.chat(raise_on_error)
   ├─ C-03 orchestrator 失败状态
   ├─ C-04 CLI 预检与退出码
   ├─ C-05 Web _run_task 全函数 try/finally
   └─ C-06 GBK 控制台与 KB 提示
        ↓
Phase 2 事件与生命周期（3–4d）
   ├─ C-07 event_bus：环形缓冲 + seq + Condition
   ├─ C-08 task_manager 接 EventBus + SSE 心跳/续传
   ├─ C-09 状态机 + 终态守卫 + interrupted
   └─ C-10 重启对账 + 并发队列 + 优雅停机
        ↓
Phase 3 长稳与性能（2–3d）
   ├─ C-11 事件 JSONL + 快照去抖 + 保留策略
   ├─ C-12 目标列表截断与容错
   └─ C-13 基准回归进 CI（slow marker，阈值放宽 5×）
        ↓
Phase 4 工程化收口（2–3d，可与 Phase 2/3 并行）
   ├─ C-14 P2-01 / P2-03 / P2-04 前端与静态资源
   ├─ C-15 版本单一来源 + wheel 断言
   ├─ C-16 报告相对路径 + 配置原子写
   ├─ C-17 Vitest + RTL + ESLint 入 CI
   └─ C-18 docs 目录 / 健康检查 / 保留策略
```

### 5.2 阶段任务表

| 阶段 | 任务 | 交付物 | 验收 | 预估 |
|------|------|--------|------|------|
| 0 | 固化复现 | `tests/web/test_task_stream.py`（先红）、`tests/agent/test_llm_failure_propagation.py`（先红）、`tests/web/test_task_setup_failure.py`（先红）、`scripts/bench_web_state.py` | 用例在当前代码上失败且失败原因正确 | 0.5d |
| 0 | 基准固化 | 把 2.3 的 5 个数字写成带阈值的手动脚本，输出到 `计划书/evidence/` | 可重复执行、数字稳定 | 0.5d |
| 1 | P0-01 | `agent/errors.py`、`core.chat(raise_on_error)`、编排状态判定、CLI 预检与退出码 | CLI/Web 两条验收全绿 | 1.5d |
| 1 | P0-02 / P1-09 | `web/services/task_service.py` 全函数 try/finally、`unbind`、`console_output` 参数 | 构造异常 → `failed`；GBK 控制台可建任务 | 1d |
| 2 | P1-02 / P1-04 | `web/event_bus.py` + `stream.py` 心跳/`id:` | 订阅两次无重复、慢消费者不阻塞 | 1.5d |
| 2 | P1-03 / P1-06 | `_transition()`、`interrupted`、stop 守卫、重启对账 | 状态机参数化测试全绿 | 1.5d |
| 2 | P1-07 | 信号量队列 + `queued` + lifespan 停机 | 并发/停机用例绿 | 1d |
| 3 | P1-05 | JSONL 事件 + 去抖快照 + 保留策略 | 基准三项达标 | 1.5d |
| 3 | P1-08 | 截断排序 + 单文件容错 | 500 目标 < 100 ms | 0.5–1d |
| 4 | P2 批次 | 见 3.3 表 | 对应用例全绿 | 2–3d |
| 4 | 前端测试 | Vitest + RTL + ESLint + CI job | `npm run test` / `npm run lint` 绿 | 1.5d |

合计约 12–16 人日，不含评审与 soak 等待。若只做 Phase 0–3，约 8–10 人日。

### 5.3 原子任务卡

每张卡满足：单一文件或单一函数簇、可独立验证、可独立回滚。

| 卡号 | 范围 | 输入 | 输出 | 验证 | 回滚 |
|------|------|------|------|------|------|
| C-01 | `vulnclaw/agent/errors.py` 新增 | `llm_client` 现有异常 | `LLMInvocationError` | `pytest tests/agent/test_llm_failure_propagation.py -q` | 删文件 |
| C-02 | `agent/core.py` `chat()` | C-01 | 新参数 + 抛错 | 同上 + `tests/agent/test_agent.py` | 恢复原 `except` 分支 |
| C-03 | `orchestrator.run_agent_task` | C-02 | 失败状态与摘要字段 | `pytest tests/run/test_run_persistence.py -q` | 单文件 revert |
| C-04 | CLI `recon` / `scan` / `exploit` | `has_llm_credentials` | 预检 + 退出码 1 | `pytest tests/cli/test_cli_failure_exit_code.py -q` | 单文件 revert |
| C-05 | `web/services/task_service.py` | 现有 `_run_task` | 全函数 try/finally + `unbind` | `pytest tests/web/test_task_setup_failure.py -q` | 单文件 revert |
| C-06 | `agent/core.py` `_report_kb_status` | GBK 复现 | 捕获 + 一次性提示 + `console_output` 参数 | 手动 GBK 控制台 + `tests/agent/test_kb_notice.py` | 恢复 `console.print` |
| C-07 | `web/event_bus.py` 新增 | `TaskEvent` | 环形缓冲 + `seq` + `Condition` | `pytest tests/web/test_event_bus.py -q` | 删文件 |
| C-08 | `task_manager` 接 EventBus | C-07 | publish/subscribe 改造 | `pytest tests/web/test_task_stream.py -q` | 恢复旧实现 |
| C-09 | 状态机 `_transition` | 现有状态枚举 | 守卫 + `interrupted` | `pytest tests/web/test_task_state_machine.py -q` | 单文件 revert |
| C-10 | 调度与停机 | C-09 | 信号量 + lifespan | `pytest tests/web/test_task_queue.py -q` | 单文件 revert |
| C-11 | 持久化 | `atomic_write_json` | JSONL + 去抖 + 裁剪 | `pytest tests/web/test_task_persistence.py -q` | 单文件 revert |
| C-12 | 目标列表 | `target_service` | 截断 + 容错 | `pytest tests/web/test_targets_robustness.py -q` | 单文件 revert |
| C-13 | 基准脚本 | C-07/C-11 | `scripts/bench_web_state.py` | `python scripts/bench_web_state.py --assert` | 删文件 |
| C-14 | 静态资源与前端停止 | `web/app.py`、`App.tsx` | 404 + 服务端状态为准 | `tests/web/test_app_static.py`、前端组件测 | 单文件 revert |
| C-15 | 版本单一来源 | `vulnclaw.__version__` | Vite `define` + 测试 | `pytest tests/meta/test_version_consistency.py -q` | 单文件 revert |
| C-16 | 报告路径与配置原子写 | `run_context` / `settings` | 相对路径 + tmp replace | `pytest tests/config/test_config_atomic_write.py -q` | 单文件 revert |
| C-17 | 前端测试栈 | `frontend/package.json` | Vitest + RTL + ESLint | `npm run test && npm run lint` | 移除脚本与依赖 |
| C-18 | 发布与文档 | `.github/workflows`、`.gitignore` | audit/SBOM/Docker job；取消 docs 忽略 | workflow 跑通 + `git check-ignore` | revert workflow |

### 5.4 每阶段质量门禁

1. `python -m ruff check vulnclaw tests` 无新增告警。
2. `python -m pytest -q` 全绿（含新增用例），覆盖率不低于阶段目标。
3. `cd frontend && npm run build` 通过；Phase 4 起加 `npm run test` / `npm run lint`。
4. `python scripts/verify_execution_boundary.py` 通过。
5. 手动冒烟：`vulnclaw web` → 建任务 → 看事件 → 停止 → 重启 → 状态正确；Windows 默认控制台再跑一遍。
6. CHANGELOG 与 README 同步；版本号一致。

---

### 5.5 Phase 5–6 产品层任务表

产品层依赖可靠性内核。Phase 5 之前必须完成 P1-02/P1-04/P1-06/P1-07，否则进度页、发现页、报告页都会建立在不可靠的任务状态上。

| 阶段 | 任务 | 交付物 | 验收 | 预估 |
|------|------|--------|------|------|
| 5 | F-04 运行详情 | `/api/runs`、`/api/runs/{run_name}`；前端 `RunDetailPage`：阶段时间线、证据抽屉、失败原因、续跑按钮 | 给定一份历史 run 能还原阶段耗时与终态；E2E 覆盖 | 1.5d |
| 5 | F-05 项目 / 工作区 | `~/.vulnclaw/projects/<slug>/project.json`；target 增加 `project_id`；Web 顶栏切换；CLI `--project` | 跨项目目标不串；项目内报告落 `projects/<slug>/reports/` | 1.5d |
| 5 | F-06 发现工作台 | `finding_status ∈ {new, triaged, confirmed, false_positive, fixed, risk_accepted}`、`note`、`assignee`；筛选与批量操作；报告标注状态 | 状态变更持久化；`tests/web/test_findings_lifecycle.py` | 1.5d |
| 5 | F-07 报告中心 2.0 | 相对路径、`markdown/html/pdf/json/sarif`、报告内容密钥脱敏、`pentest/executive/ctf` 模板已通 | 同一 run 五格式；SARIF schema 校验；无绝对路径与密钥 | 1.5d |
| 6 | F-08 成本与 Token | `TaskSummary` 增加 `tokens.input/output/total`、`cost_estimate`；任务卡与报告页展示 | mock usage 断言汇总与单价 | 0.5d |
| 6 | F-09 审计导出 | `/api/audit/export?format=jsonl\|csv`；报告附执行边界附录 | 导出与接口数据一致；附录含违规事件计数 | 1d |
| 6 | F-10 集成导出 | `/api/integrations`；Jira / DefectDojo / Webhook 统一 dispatch，3 次重试、幂等键；设置页「集成」分区含增删改/测试 | 本地 mock server 验证 payload、重试、超时；不打真实外部 API | 1.5d |
| 6 | F-11 调度与通知 | 进程内调度器；`schedule: [{target, cron\|interval, options}]`；完成/失败 Webhook 已通（按集成 `events` 订阅） | 可控时钟测试「到点入队、串行执行、失败告警」 | 1d |
| 6 | F-12 MCP 控制台 | `/api/mcp` 已有诊断；启停与工具白名单；接入 `exec_gate` | 启停后状态与工具数变化正确；禁用工具被拒并记审计 | 1d |
| 6 | F-13 离线 / 内网 | `--offline` 关闭 KB 在线更新与 provider 探测；KB 预打包索引；`doctor` 离线体检 | 断网环境 `doctor` 不报错、不挂起；本地模型可跑 | 1d |
| 6 | F-14 插件生态 | `entry_points(group="vulnclaw.plugins")`；`PluginManifest` 声明权限与风险；加载前校验；`examples/plugins/vulnclaw-plugin-demo` 样例包 + `/api/plugins` 与 Web 插件页 | 样例包被正确发现；权限拒绝与版本不兼容有明确提示 | 1.5d |
| 6 | F-18 长稳与自愈 | `scripts/soak_web.py`；MCP 孤儿检测；任务异常保留快照并标 `interrupted` | 24 h RSS 增长 < 10%，无僵尸任务、无孤儿子进程 | 0.5d + 机器时间 |

产品层合计约 13–16 人日，与 Phase 0–4 合并约 25–30 人日。每个 PR 只带一个功能域，前后端同 PR，测试随功能提交。

## 6. TDD 清单

### 6.1 后端新增/扩展用例

| 测试文件 | 覆盖对象 | 关键用例 |
|----------|----------|----------|
| `tests/agent/test_llm_failure_propagation.py`（新） | `core.chat` / `llm_client` | 401 → 抛 `LLMInvocationError`；`raise_on_error=False` 保持旧行为；错误消息脱敏 |
| `tests/cli/test_cli_failure_exit_code.py`（新） | `recon` / `scan` / `exploit` | 无凭据 → 预检退出 1；有凭据但 401 → 退出 1 + 可操作提示 |
| `tests/run/test_run_persistence.py`（扩展） | `run_agent_task` | 失败时 `run.json.status=failed`、`exit_code=1`、摘要含 error |
| `tests/web/test_task_setup_failure.py`（新） | `_run_task` | `AgentCore` 构造抛异常 → `failed` + `task_failed` + `_running` 清空 |
| `tests/agent/test_kb_notice.py`（新） | `_report_kb_status` | `console.print` 抛 `UnicodeEncodeError` 不向上传播；进程内只提示一次 |
| `tests/web/test_event_bus.py`（新） | EventBus | 顺序、`seq` 单调、慢消费者跳过、重启重建 |
| `tests/web/test_task_stream.py`（新） | SSE | 无重复、`Last-Event-ID` 续传、终态关闭、心跳帧 |
| `tests/web/test_task_state_machine.py`（新） | 状态机 | 全部合法转换 + 非法转换拒绝 + 终态幂等 |
| `tests/web/test_task_manager_lifecycle.py`（新） | stop/complete | 完成后 stop 返回 `False`；并发 stop 一次生效 |
| `tests/web/test_task_persistence.py`（新） | 持久化 | 300 事件 < 50 ms；重启恢复；裁剪最近 200 任务 |
| `tests/web/test_task_queue.py`（新） | 并发 | 第 2 个起 `queued`；shutdown 全部取消 |
| `tests/web/test_task_restart_reconcile.py`（新） | 重启对账 | 非终态 → `interrupted`；SSE 立即结束 |
| `tests/web/test_targets_robustness.py`（新） | `list_targets` | 500 个 < 100 ms；坏文件跳过；非法 schema 跳过 |
| `tests/web/test_app_static.py`（新） | 静态资源 | `/assets/x.js` 404；`/route` 200 index；`/?token=` 换 cookie |
| `tests/web/test_web.py`（扩展） | 路由 | 覆盖 400/403/404 分支，`app.py` 覆盖率 ≥ 90% |
| `tests/config/test_config_atomic_write.py`（新） | `save_config` | 原子替换；中断不产生半文件；权限 0600（POSIX） |
| `tests/meta/test_version_consistency.py`（新） | 版本 | `pyproject` == `vulnclaw.__version__` == `package.json` == `app.version`；manifest 不存在 |
| `tests/meta/test_wheel_contains_ui.py`（新） | 打包 | wheel 内存在 `vulnclaw/web/dist/index.html`（用 `zipfile` 读 `namelist()`） |
| `tests/performance/test_benchmarks.py`（新，`@pytest.mark.slow`） | 基准 | publish / 创建 / 列表三个阈值（CI 放宽 5×） |

### 6.2 前端测试栈（从 0 到 1）

```
frontend/
  vitest.config.ts
  src/test/setup.ts
  src/utils/__tests__/preferences.test.ts     # 语言检测、边界默认值归一化、损坏 localStorage
  src/utils/__tests__/validation.test.ts      # 端口解析边界
  src/utils/__tests__/taskLabels.test.ts      # 状态/阶段/动作标签中英文
  src/api/__tests__/web.test.ts               # 错误体解析、非 JSON、网络失败、事件名清单
  src/components/__tests__/ConfirmDialog.test.tsx   # Esc、焦点陷阱、焦点归还
  src/components/__tests__/ToastHost.test.tsx       # aria-live、关闭、动作
  src/pages/__tests__/HomePage.test.tsx       # 校验、提交禁用、错误展示
  e2e/web.spec.ts                             # 建任务 → 事件 → 停止 → 报告
```

约束：测试只断言行为与无障碍语义，不测实现细节；网络层用 `msw` 或 `vi.stubGlobal("fetch")`，不打真实后端。

### 6.3 长稳剧本（`scripts/soak_web.py`）

1. 启动 `vulnclaw web`，`VULNCLAW_CONFIG_DIR` 指向临时目录。
2. 每 5 s 提交一个 `codescan` 任务（无需 LLM，纯本地，避免付费与网络）。
3. 并发 3 个 SSE 客户端，每 60 s 主动断开重连。
4. 每 10 min 记录：RSS、线程数、句柄数、`web_tasks.json` 大小、事件文件总大小、`running/queued` 计数。
5. 24 h 后断言：RSS 增长 < 10%、无 `running` 残留、无孤儿子进程、磁盘增长线性且受保留策略约束。

用 `codescan` 而非 `recon`，避免真实 LLM 调用与对外扫描；需要验证 LLM 路径时用本地 mock server。

---

## 7. 验收矩阵

| 需求 | 验证方式 | 通过标准 |
|------|----------|----------|
| 失败不再记为成功 | CLI 退出码 + Web 事件 | 401 / 超时 / 断网三种场景均 `failed` 且退出 1 |
| 初始化失败可见 | 构造异常 + GBK 控制台 | 任务 `failed`，有 `task_failed`，无 `pending` 残留 |
| 事件不重不漏 | 两次订阅 + 断线续传 | 序列严格递增、无重复、缺口可补 |
| 停止不篡改终态 | 完成后 stop | `409`，状态不变 |
| 重启可对账 | 写 `running` 状态后重启 | 全部 `interrupted`，UI 可续跑 |
| 长跑不劣化 | soak 24 h | 指标全部达标 |
| 大目录可用 | 500 目标列表 | < 100 ms，坏文件不影响整体 |
| 报告可交付 | 生成五种格式 | 无绝对路径、无密钥、SARIF 合法 |
| 前端可回归 | `npm run test` + E2E | 全绿，关键链路 3 条 |
| 发布可信 | 破坏性演练 | 删 `vulnclaw/web/dist` 后预检失败；版本不一致时测试失败 |

---

## 8. 风险与回滚

| 风险 | 触发场景 | 缓解 | 回滚 |
|------|----------|------|------|
| 事件模型改动导致前端停更 | `event:` 名或 `seq` 变更 | 保留 `task_id/timestamp` 字段；前后端同 PR | 恢复旧 `stream_events` |
| 新增 `interrupted` 影响旧客户端 | 第三方脚本判断状态 | 视为非终态失败类；CHANGELOG 明示 | 前端映射表回退 |
| `stop` 语义由 200 改 409 | 现有自动化 | 返回体保留 `task_id/status`，文档标注变更 | 恢复 200 + 状态守卫 |
| 持久化格式迁移失败 | 旧 `web_tasks.json` | 首次启动自动迁移并备份 `.bak`，失败则从空状态启动并告警 | 恢复 `.bak` |
| 后台任务 `console_output=False` 让 CLI 看不到提示 | 误传参数 | 参数默认 `True`；仅 Web 传 `False` | 恢复默认 |
| 调度器引入后台任务泄漏 | 长跑 | 单一调度循环 + `finally` 取消；soak 覆盖 | 关闭调度配置项 |
| 前端测试引入构建复杂度 | CI 时长 | Vitest 只跑单测，E2E 单独 job，按需触发 | 移除 job |

---

## 9. 明确不做

1. 不引入 Redis / Celery / Postgres / 消息队列：单机单用户，进程内足够。
2. 不把 `WebTaskManager` 改成分布式任务系统。
3. 不重构 `vulnclaw/cli/main.py`：只做「命令体内延迟导入」与「补预检」两处局部修改。
4. 不改 Rust TUI 架构，不复活 Textual 实现。
5. 不为本地场景加账号体系、RBAC、OAuth；VPS 多用户单独立项。
6. 不加 feature flag、配置开关矩阵、兼容层；需要行为差异时用参数（如 `raise_on_error`、`console_output`），不用开关。
7. 不加遥测，不上报任何使用数据。
8. 不做与定位无关的功能（自动修复代码、聊天机器人、模型微调）。
9. 不为「理论上可能」的场景写防御代码；安全问题只覆盖本项目真实可达路径（见 3.4）。

---

## 10. 实施范围与决策点

### 10.1 已确认范围

**全量 V2（Phase 0–6），版本 0.5.0，Windows 编码两条都做。** P0/P1 先收敛，再做 P2 工程化，最后做产品层。顺序不并行跳跃：每一步都有独立验收和回滚点，避免功能叠加掩盖可靠性缺陷。原指南的 0.6/0.7 版本阶梯合并进 0.5.0。

### 10.2 已拍板

| 决策 | 结论 | 说明 |
|------|------|------|
| 施工范围 | 全量 V2（Phase 0–6） | 可靠性内核 → P2 工程化 → 产品层，按顺序推进 |
| Windows 控制台 | 后台 logger + 入口 UTF-8 两条都做 | 入口统一编码，后台不再直接 `console.print` |
| 版本 | 0.5.0 | 已 bump 到 0.5.0；wheel/sdist 版本一致 |

---

## 11. 实施进展（2026-11-05）

### 11.1 已完成

| 项 | 改动 | 验证 |
|----|------|------|
| P0-01 失败语义 | `agent/errors.py` + `LLMInvocationError`；`llm_client` 鉴权/重试耗尽抛类型化错误；`core.chat(raise_on_error)`；CLI 编排器退出 1；`recon/scan/exploit` 凭据预检；`solve/team/rounds/persistent` 对 fatal 错误上抛 | 401 mock 下 `recon`/`run --engine solve`/`team`/`rounds`/`persistent` 均 exit 1；Web 默认 `run` 任务 `failed` + `task_failed` |
| P0-02 初始化失败出口 | `web/services/task_service.py` 全函数 `try/except/finally`；MCP/Agent 构造移入 `try`；`finally` 中 `stop_all` + `unbind` | `tests/web/test_task_setup_failure.py`；异常 → `failed`，无 `pending` 残留 |
| P1-02～P1-09 | EventBus（单调 `seq` + 环形缓冲 + 心跳）；SSE `id:`/`Last-Event-ID`；终态守卫；`interrupted` 重启对账；信号量队列；优雅停机；GBK 控制台集中配置；目标列表截断容错 | 一次订阅 5 个事件无重复；stop 已完成任务返回 409；5,000 事件 1.4 s 且队列封顶；500 目标 0.43 s，坏文件跳过 |
| P2-01 静态资源 404 | `resolve_web_asset` 对带扩展名缺失文件返回 `None`，仅无扩展名路由走 SPA | `tests/web/test_app_static.py` |
| P2-03 SSE 心跳 | 服务端 15 s 心跳帧；前端 `EventSource` 自动带 `Last-Event-ID` | `tests/web/test_task_stream.py` |
| P2-04 停止 UI | 不再本地臆断 `stopped`；以服务端/列表回读为准；409 提示「任务已结束」 | `tsc -b` 通过 |
| P2-05 版本单一来源 | `vulnclaw.__version__` 唯一真值；`web.__version__` 引用它；Vite `define` 注入 `__APP_VERSION__`；侧栏显示版本；`package.json` 0.4.1 | `tests/meta/test_version_consistency.py` |
| P2-06 报告路径 | PoC 路径改为 `pocs/<file>` 相对路径，英文报告不再被本机 CJK 路径污染 | 原先唯一失败的 report 用例转绿 |
| P2-12 配置原子写 | `save_config` tmp + `os.replace`，POSIX `0600` | `tests/config/test_config_atomic_write.py` |
| P2-14 docs 目录 | 取消 `.gitignore` 对 `docs/` 的忽略 | `git check-ignore` 不再命中 |
| P2-15 前端测试 | Vitest + Testing Library + jsdom；`npm run test`；CI 增加 frontend unit tests | 11 个用例通过 |
| F-15 真实 E2E | Playwright + 本地 mock LLM；5 条主链路（首页任务/运行详情/发现处置/报告 SARIF/stop 409+SSE） | 5 passed；截图 `frontend/e2e-artifacts/` |
| P2-16 保留策略 | 新增 `vulnclaw gc --older-than --keep-last --dry-run`；Web 任务创建时裁剪到 200 | `tests/cli/test_gc.py`；任务保留用例 |
| P2-13 启动优化 | 未做 | `--help` 0.85 s，目标 <0.5 |
| P2-19 健康检查 | `/api/health` 返回 `version/uptime/ui/tasks.running/queued` | Web 冒烟 |
| P2-20 KB 提示 | Web 后台 `AgentCore(console_output=False)` 不打印；CLI 保留启动提示 | 任务日志无 KB 提示 |
| P2-21 前端产物 | 已在工作树修复；Vite 直接输出 `vulnclaw/web/dist`，wheel 内含 UI | `python -m build` + zipfile 断言 |
| F-04 运行详情 | `/api/runs`、`/api/runs/{run_name}`；`RunDetailDialog` 展示事件时间线、产物、报告；真实 CDP 点击验证，修复了初版未渲染与深色对比度问题 | `tests/web/test_run_service.py`；CDP 点击截图 |
| F-06 发现工作台 | `finding_meta` 扩展 `triage_status/note/assignee`；`/api/findings`、`/api/findings/triage`；Risk 页处置下拉与备注 | `tests/web/test_findings_lifecycle.py` |
| F-08 Token 汇总 | `RuntimeState` 累计 `prompt/completion/total` 与调用次数；任务摘要平铺 `tokens_*`/`llm_calls`；任务台展示 | `tests/agent/test_token_usage_summary.py` |
| F-09 审计导出 | `collect_constraint_events`；`/api/audit/export?format=jsonl|csv` | `tests/web/test_audit_export.py` |
| F-05 项目底座 | `PROJECTS_DIR`、`project.json`、`/api/projects` CRUD、目标关联、项目报告目录；任务 `project_id`、首页项目选择、CLI `--project`、报告落项目目录 | `tests/web/test_projects.py`、`test_project_reports.py` |
| F-12 MCP 控制 | `/api/mcp/toggle` 持久化 `mcp.servers.<name>.enabled`，对下一个任务生效 | `tests/web/test_mcp_toggle.py` |
| F-18 长稳脚本 | `scripts/soak_web.py`：codescan 任务、SSE 重连、RSS/线程采样、终态检查 | 8 秒冒烟通过；RSS 98→113 MB |
| F-10 集成导出 | `vulnclaw/integrations/dispatch.py`（webhook/Jira/DefectDojo，重试/幂等/超时）+ `/api/integrations` 配置/触达 | `tests/integrations`、`tests/web/test_integrations.py` |
| F-11 调度 | `vulnclaw/scheduler.py` + `schedule_service` + `/api/schedules` + app lifespan 5s 轮询 | `tests/test_scheduler.py`、`tests/web/test_schedules.py` |
| F-13 离线 | 全局 `--offline`、`is_offline()`、doctor/ provider-models 跳过在线探测 | `tests/cli/test_offline.py` |
| F-14 插件生态 | `entry_points` 发现、权限白名单、`min_core_version` 校验、`plugins list --external` | `tests/plugins/test_plugin_registry.py` |

### 11.2 新增测试

- `tests/agent/test_llm_failure_propagation.py`
- `tests/agent/test_token_usage_summary.py`
- `tests/cli/test_cli_failure_exit_code.py`
- `tests/config/test_config_atomic_write.py`
- `tests/meta/test_version_consistency.py`
- `tests/web/test_event_bus.py`
- `tests/web/test_task_stream.py`
- `tests/web/test_task_lifecycle.py`
- `tests/web/test_task_persistence.py`
- `tests/web/test_task_setup_failure.py`
- `tests/web/test_targets_robustness.py`
- `tests/web/test_app_static.py`
- `tests/web/test_run_service.py`
- `tests/web/test_findings_lifecycle.py`
- `tests/web/test_audit_export.py`
- `tests/web/test_projects.py`
- `tests/web/test_mcp_toggle.py`
- `tests/agent/test_llm_transport_failure_matrix.py`（真实 SDK × 本地 provider mock）
- `tests/agent/test_engine_fatal_propagation.py`
- `tests/cli/test_cli_mock_llm_failure.py`
- 前端：`src/utils/__tests__/*`、`src/api/__tests__/web.test.ts`

### 11.3 当前验证

```
ruff check vulnclaw tests scripts                  -> All checks passed
pytest -q --cov=vulnclaw                            -> 2107 passed, 10 skipped, 82.14%, 62.78 s
cd frontend && npm run build                       -> 103 modules, JS 340.73 kB (gzip 97.65), 0.83 s
cd frontend && npm run test                        -> 11 passed
cd frontend && npm run e2e                         -> 5 passed（14.4 s）
python scripts/soak_web.py --duration 8 ...        -> 通过；RSS 98.1 → 113.0 MB
CLI 401 mock                                       -> recon/solve/team/rounds/persistent 均 exit 1，错误可读且脱敏
Web 401 mock（默认 run）                           -> failed / task_failed（此前 completed / exit 0）
Web 401 mock                                       -> failed / task_failed；SSE 5 帧无重复；stop 409；Last-Event-ID 续传正确
真实浏览器                                         -> CDP 1440x1000：首页开始任务、历史运行详情、风险处置状态改「已确认」并读回；截图 ui-home/ui-run-detail-wide/ui-risk/ui-triage
```

基准（临时配置目录）：

| 场景 | 改造前 | 改造后 |
|------|--------|--------|
| `publish` 300 事件 | 0.423 s（1.409 ms/事件） | 0.080 s（0.266 ms/事件） |
| 创建 300 任务 | 2.998 s / 476 KB | 0.987 s / 38.9 KB |
| 5,000 事件无消费者 | 45.052 s / `qsize=5001` | 1.416 s / 队列封顶 2,000 |
| 500 目标列表 | 3.250 s | 0.432 s（O(n) stat + O(limit) parse） |
| `vulnclaw --help` | 0.811 s | 0.811 s（P2-13 未做） |

### 11.4 剩余事项

| 项 | 状态 | 下一步 |
|----|------|--------|
| F-05 项目完整隔离 | 主要链路完成 | 任务 `project_id`、首页项目选择、CLI `--project`、报告落项目目录已完成；跨项目列表过滤/独立切换器仍可加强 |
| F-07 报告中心 2.0 | **已完成** | PDF/SARIF/JSON/MD/HTML、脱敏、`pentest/executive/ctf` 模板；`session.report_template` 决定自动报告模板；执行摘要不写定位/PoC 与治理附录 |
| F-10 集成导出 | **已完成** | 后端/API + 设置页「集成」分区（增删改/令牌保留/订阅事件/一键测试） |
| F-11 调度与通知 | **已完成** | 任务终态按订阅推 webhook/Jira/DefectDojo；投递记录 + 一键重投；设置页「自动化」分区管理定时任务 |
| F-13 离线模式 | 基础完成 | `--offline`/doctor/provider 探测已跳过；KB 预打包索引未做 |
| F-14 插件生态 | **已完成** | entry_points/权限/版本校验 + 样例包 + `/api/plugins` + Web 插件页（阶段/来源筛选、坏入口点单独报错） |
| F-15 前端 E2E / ESLint | E2E 5 条已完成；ESLint 未做 | ESLint flat config |
| F-17 发布工程 | 部分 | 新增 security.yml（pip-audit/npm audit/SBOM）与 docker.yml（build）；未在 CI 实跑 |
| F-18 24 h 长稳 | 脚本完成；30/60s 冒烟 RSS 98→146 MB | 24h 未跑；内存趋势需长跑确认 |
| P2-13/17 | P2-13 完成，P2-17 部分完成 | `--help` 0.45 s（warm median）；security.yml/docker.yml 已加但未在 CI 实跑 |
| 覆盖率口径 | **已完成** | 去掉 `tool.coverage.run.omit`，全仓 82.67%；新增 TUI/wizard/MCP lifecycle 行为测试 |
| 缺陷修复（本轮复审） | **已完成** | `options.project` 导致任务创建 422；`{target:path}` 遮蔽 `/raw`、`/snapshots` 使历史页快照与差异对比恒为空；`cli/__init__` 过期报告副本已删除 |
| P2-07/08/09/10/11/16 | 已完成 | 语言回落、lang/title、aria、焦点陷阱、reduced-motion、gc |
| 目标索引第二阶段 | **已完成** | `index.json`，500 目标 0.012 s |
| 真实 E2E | **已完成** | 13 条主链路通过（含集成配置、任务通知与投递历史、定时任务、executive 模板、插件清单、项目关联任务、历史快照）；CI 增加 e2e step |
| LLM 失败矩阵 | **已完成** | `scripts/mock_llm_server.py`（401/403/429/500/timeout/malformed/empty choices/connection drop/retry-then-ok/stream/hang）；传输层 11 例、引擎层 5 例、CLI 4 条命令端到端通过。401/403 首次请求即失败且密钥脱敏；429/500/timeout/malformed/empty/drop 重试耗尽后抛 `LLMInvocationError`；取消原样上抛；retry-then-ok 恢复并计数；`recon`/`scan`/`exploit`/`run --engine solve` 在真实 401 provider 下 exit 1。真实付费 provider 行为仍按预算 0 不测 |

## 附录 A：本次实测原始输出

```
# 质量门禁
ruff check vulnclaw tests                     -> All checks passed!
pytest -q --cov=vulnclaw                      -> 1913 passed, 1 failed, 10 skipped, 75.06s, 76.75%
npm run build                                 -> 103 modules, JS 330.96 kB (gzip 94.96), CSS 38.75 kB, 847ms
python -m build --wheel                       -> vulnclaw-0.4.1-py3-none-any.whl
wheel 内 web/dist/index.html                  -> True（16 个 dist 条目；无 frontend/dist）
vulnclaw --help (3x)                          -> 0.811 s / 0.814 s / 0.808 s

# Web 冒烟（真实 uvicorn + 本地 401 mock，UTF-8 输出）
GET  /api/health                              -> 200 {"status":"ok"}
GET  /assets/does-not-exist.js                -> 200 text/html 488 B
POST /api/tasks/run {recon, 127.0.0.1:1}      -> 200 pending
最终任务状态                                   -> completed, summary.exit_code=0
SSE 帧                                        -> 10 帧 / 5 个事件（每个重复两次）
POST /api/tasks/{id}/stop（已完成）            -> 200，状态 completed -> stopped

# Windows 默认控制台
AgentCore(config, mcp_manager)                -> UnicodeEncodeError: 'gbk' codec can't encode '\u26a0'
真实 uvicorn 建任务（GBK）                    -> 轮询期间始终 pending，无 task_failed
同一脚本加 PYTHONUTF8=1                       -> 正常走到 completed

# 基准（临时 VULNCLAW_CONFIG_DIR）
publish 300 events, 1 task                    -> 0.423 s (1.409 ms/event), state 91,822 B
create 300 tasks                              -> 2.998 s, state 475,902 B
publish 5,000 events, 0 consumers             -> 45.052 s, queue=5001, state 576,939 B
list_targets(), 500 targets                   -> 3.250 s, 20 returned
list_targets(), 1 corrupt state.json          -> JSONDecodeError -> HTTP 500

# 版本
pyproject.toml 0.4.1 | web/__init__.py fallback 0.4.0 | web/app.py 0.4.0
frontend/package.json 0.4.0 | version-manifest.txt 0.4.0
```

## 附录 B：关键文件索引

| 关注点 | 文件 |
|--------|------|
| CLI 入口与命令 | `vulnclaw/cli/main.py`、`vulnclaw/cli/_helpers.py` |
| 任务契约与执行 | `vulnclaw/task_service.py`、`vulnclaw/orchestrator.py` |
| Agent 核心 | `vulnclaw/agent/core.py`、`solver.py`、`loop_controller.py`、`llm_client.py` |
| 证据与上下文 | `vulnclaw/agent/agent_state.py`、`context.py`、`context_budget.py`、`memory.py` |
| 执行安全 | `vulnclaw/agent/exec_gate.py`、`command_classifier.py`、`constraint_policy.py` |
| Web 后端 | `vulnclaw/web/app.py`、`auth.py`、`task_manager.py`、`stream.py`、`services/*` |
| 断点与运行 | `vulnclaw/target_state/store.py`、`vulnclaw/run_context.py` |
| 报告 | `vulnclaw/report/generator.py`、`solve_report.py`、`verifier.py`、`codescan/report.py` |
| 前端 | `frontend/src/App.tsx`、`api/web.ts`、`hooks/queries.ts`、`pages/*`、`styles.css` |
| TUI | `tui/src/*`、`vulnclaw/cli/tui.py`、`vulnclaw/tui_backend.py` |
| 发布 | `pyproject.toml`、`scripts/release_preflight.py`、`scripts/verify_dist_artifacts.py`、`.github/workflows/*` |

## 附录 C：术语

| 术语 | 含义 |
|------|------|
| 运行（run） | 一次任务执行，对应 `~/.vulnclaw/runs/<run_name>/` |
| 目标状态（target state） | 某目标跨运行的累积状态与快照，对应 `~/.vulnclaw/targets/<target>/` |
| 证据（evidence） | 工具调用的原始输出与派生摘要，存于 `AgentState.evidence` |
| 事件（event） | 任务生命周期中的结构化通知，SSE 推送给前端 |
| 终态 | `completed` / `failed` / `stopped` / `interrupted` |
| 对账（reconcile） | 进程启动时把持久化的非终态任务修正为 `interrupted` |
| 写放大 | 单次事件触发整文件重写，成本随累计数据线性增长 |
| 慢消费者 | 订阅速度低于生产速度的 SSE 客户端 |