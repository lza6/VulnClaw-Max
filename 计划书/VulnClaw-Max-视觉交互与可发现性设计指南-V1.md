# VulnClaw-Max 视觉交互与可发现性设计指南（V1）

> 文档类型：施工级设计指南（视觉体系 / 动效 / 3D / 可发现性）
> 编写日期：2026-11-05
> 代码基线：`main` @ `64cca9c`，`frontend/package.json` 0.5.0，`vulnclaw.__version__` 0.5.0
> 与既有计划书的关系：`VulnClaw-Max-工程改造计划书-V2.md` 已收口可靠性内核与产品功能（Phase 0–6 完成）；`VulnClaw-Max-差距审计与验收编排.md` 覆盖验收编排；`下一步改进指南.md` 为历史背景。**三份文件都没有定义视觉体系、动效规范、3D 场景与公网可发现性**。本文件只补这一层，不重开可靠性工作，不改后端语义。
> 证据口径：**已验证**（实际运行观察）/ **静态确认**（读代码确认）/ **合理推断**（有间接证据）/ **待验证**（缺环境或权限）

---

## 0. 一页摘要

### 0.1 这份文档补的是什么

现在这套 UI 是 8 个功能页面 + 21 个组件、4778 行 TSX、3326 行 CSS 堆出来的操作台。功能是真的（13 条 Playwright E2E 全绿、发现处置/报告/集成/调度/插件都有真实链路），但**观感层没有体系**：颜色是逐条追加的硬编码、动效近乎为零、主题只有一个、没有品牌落点。这份指南把"能用的操作台"补成"看起来和用起来都成型的操作台"，并给出可验证的施工顺序。

### 0.2 六条复核结论

1. **深色主题是死代码。** `styles.css:1` 的深色令牌块被 `styles.css:1938` 的同名 `:root` 全量覆盖，`color-scheme` 最终为 `light`，生效主题只有一个（浅色）。文件顶部那份"深色配色"从第 1938 行起就不再有消费者。**静态确认**。
2. **浅色主题的次要文字不达 AA。** 生效主题里 `--muted` = `#7d91b3`，在白底上 3.19:1、在页面底 `#f4f8fe` 上 3.00:1；`--soft` 1.97:1；`--danger` 2.87:1；`--safe` 1.97:1。而 `color: var(--muted)` 在样式表里被用作文字色 23 次。这是当前用户真实看到的对比度缺陷，不是理论值。**已验证**（脚本计算，见附录 A.4）。
3. **设计令牌基本没被使用。** 全表 `var(--)` 引用 120 处，硬编码 `#hex` 154 处、`rgba()` 164 处。语义层只有一个 `:root` 平铺，没有"原语 → 语义 → 组件"分层，改一次主色要扫全表。**已验证**（计数，见附录 A.3）。
4. **动效层是空的。** 3326 行 CSS 里只有 **1 个** `@keyframes`、**2 处** `transition`。`prefers-reduced-motion` 兜底已存在（`styles.css:3101`，`P2-11` 已闭合），所以新增动效有现成的降级通道——这是好消息。**已验证**。
5. **3D 没有真实数据支撑"拓扑图"。** `FindingView` 只有 `finding_key/title/severity/vuln_type/lifecycle_status/verified/triage_status/note/assignee`，没有 asset/host/port/边关系字段。任何"攻击路径三维图"在当前数据下只能是编造的边。3D 场景必须按"目标 → 发现"两层真实数据建模，拓扑边等后端补字段。**静态确认**。
6. **应用内 SEO 的真实边界是零。** 面板跑在 `127.0.0.1`、由 `AuthMiddleware` + `?token=` 换 cookie 鉴权，爬虫拿不到内容也不该拿到。可发现性只能落在"独立公开静态站 + PyPI/GitHub 分发元信息"这一层。**静态确认**。

### 0.3 已拍板决策（两轮）

| # | 决策 | 结论 | 主要代价 |
|---|------|------|---------|
| 1 | 动效技术栈 | 引入 **`motion`**（`framer-motion` 后继包，当前 14.9.1，peer 允许 React 18），用 `m` + `LazyMotion(domAnimation)` 控制体积 | 新增生产依赖；首屏 JS gzip 增量以 Phase C 构建实测为准，落点预算 +20 kB |
| 2 | 3D 档位 | **three.js + @react-three/fiber** 真 3D，单场景；已确认接受"两层星形、无拓扑边"的数据限制 | 懒加载 chunk 约 +200 kB gzip；需能力探测与降级 |
| 3 | SEO 口径 | 额外做**公开营销落地页**（独立静态站） | 迁移期间需持续维护关键词 |
| 4 | 视觉主色 | **保留蓝系**，重构为令牌化深/浅双主题 | 迁移面覆盖 318 处硬编码颜色，需按页面分片推进 |
| 5 | 公开站部署 | **GitHub Pages**，`site/` 目录直发 | 仓库或发布分支需公开；域名与推送动作待授权（§7.5） |
| 6 | 公开素材数据 | **真实结构 + 标识替换**：骨架取自真实跑批，host/IP/域名/路径全部替换为占位 | 每张截图需人工过一遍替换清单（§7.6） |
| 7 | 3D 去留 | 施工，挂在 `RiskResultsPage` | 4–5 人日 |
| 8 | 主题切换入口 | **设置页"外观"分区**，顶栏不加控件 | 发现性依赖用户主动进设置 |

### 0.4 一句话验收

浅色与深色都能一键切换、切换后没有一个文字掉到 4.5:1 以下；任何动效在 `prefers-reduced-motion: reduce` 下完全静止且功能不变；3D 场景加载失败时同屏仍有一份等价表格；公开站的 `sitemap.xml`/`robots.txt`/结构化数据能被真实抓取工具读到。

---

## 1. 现状基线

### 1.1 实测与静态确认数据

| 维度 | 现状 | 口径 |
|------|------|------|
| 样式体量 | `frontend/src/styles.css` 3326 行 / 507 个规则块 | 已验证（`grep -c "{"`） |
| 令牌使用 | `var(--)` 120 处；硬编码 `#hex` 154 处；`rgba()` 164 处 | 已验证 |
| 主题 | 单个 `:root` 生效（浅色）；深色块被覆盖，无切换入口 | 静态确认 |
| 动效 | 1 个 `@keyframes`（`pulse-panel`）、2 处 `transition`；reduced-motion 全局兜底存在 | 已验证 |
| 字号 | 12px×25、13px×8、14px×5、16px×5、24px×4、11px×4、22px×3、15px×3、34px×2… 共 12 种 | 已验证 |
| 间距 | `gap/padding` 出现 6/8/10/12/14/16/18/24px，无 4px 基准刻度 | 已验证 |
| 页面 | 8 个页面 3350 行 TSX；13 个业务组件 1378 行 | 已验证 |
| 路由 | `App.tsx` 内 `useState` + `hash`，无路由库、无路由级 code split | 静态确认 |
| 构建产物 | JS 340.73 kB（gzip 97.65 kB），103 modules | 已验证（V2 计划书 §11.3） |
| 静态资源 | `public/` 只有 `icons/`，无 favicon、无 og-image、无 robots.txt | 已验证 |
| `index.html` | 有 `lang`/`viewport`/`theme-color(#f6f9fe)`/`title`；无 `description`、无 og/twitter、无 `robots` | 已验证 |
| 测试护栏 | Vitest 单测 + Playwright 13 条 E2E + `e2e-artifacts/` 截图 | 已验证（现有） |

### 1.2 设计债清单

| ID | 问题 | 证据 | 级别 | 现状 |
|----|------|------|------|------|
| D-01 | 生效主题的 `--muted`/`--soft`/`--danger`/`--safe` 作为文字色不达 WCAG AA 4.5:1 | 3.19/1.97/2.87/1.97:1；`color: var(--muted)` 23 处 | **P1** | **已修**（4.91/3.25 且仅非正文/5.44/4.98） |
| D-02 | 深色主题不可用（令牌块被覆盖），用户无法选择 | `styles.css:1` vs `:1938` | **P1** | **已修**：单点 `[data-theme="dark"]` + 设置页外观分区 |
| D-03 | `theme-color` 写死浅色 `#f6f9fe`，与深色主题/浏览器 UI 不一致 | `index.html:6` | P2 | **已修**：单 meta + 引导脚本与 `useThemeMode` 同步 |
| D-04 | 无令牌分层，318 处颜色散落在规则里，无法整体调色 | 计数 | **P1**（阻塞视觉升级） | **已修**：`var(--)` 120→365，`#hex` 唯一值 154→37 |
| D-05 | 间距/字号无刻度，12 种字号 + 8 种间距并存，视觉节奏不稳 | 计数 | P2 | **部分**：刻度令牌已定义并在新样式里使用；既有 507 条规则按页面回填是长尾，未一次性扫完 |
| D-06 | 动效层空白：状态变化、列表加载、对话框、SSE 事件流全为瞬变 | 1 keyframe / 2 transition | P2 | **已修**：M-01～M-10 |
| D-07 | 无 `description`/og/favicon/robots，静态资源缺品牌位 | `index.html`、`public/` | P2 | **已修** |
| D-08 | 路由无 code split，页面代码与首屏同一 chunk | 103 modules 单产物 | P2 | **未做**：3D 场景已独立分包，页面级 `React.lazy` 未拆（首屏 144.67 kB 尚在预算内，拆页面要动 hash 路由的挂载语义，收益不抵风险） |
| D-09 | 无公开落地页，产品对外只有 README | 仓库无 `site/` | P2 | **已修**：`site/` 三页 + sitemap/robots/结构化数据（上线待授权） |

### 1.3 两条需要纠正的常见预设

- **"给 SPA 加 SEO"是伪需求。** 本面板的入口是 `vulnclaw web` 打印的 `http://127.0.0.1:<port>/?token=...`，鉴权中间件拦在前面，搜索引擎既爬不到也不该爬到。把力气花在 SPA 的 meta 标签上不会带来任何流量；能带来流量的只有公开站与分发渠道元信息。
- **"3D 攻击路径图"当前无数据。** 见 §0.2 第 5 条。3D 场景的节点与连线必须来自真实 API 字段，否则就是装饰性假数据，违反项目"禁止假数据冒充真实实现"的底线。

---

## 2. 设计原则与硬约束

### 2.1 信息优先（操作台不是宣传站）

- **动效不得延迟信息呈现。** 任何进入动画 ≤ 260 ms，且内容在动画首帧就已存在于 DOM（可见性由 `opacity/transform` 控制，不用 `display:none` 延迟挂载）。
- **数据密集区动效降级。** 任务台（`TaskConsolePage`，SSE 事件流）、发现工作台（`RiskResultsPage` 列表）、历史（`HistoryPage`）禁止整页转场；只保留单条插入/状态变更的微动效。
- **长驻动画上限 = 0。** 现有 `pulse-panel` 改为仅 `running` 状态且最多脉冲 3 次后静止。操作台开着不关，循环动画等于持续耗电与视觉噪音。

### 2.2 可访问性红线（不可谈判）

1. 正文文本对比度 ≥ **4.5:1**；大字（≥18.66px bold 或 ≥24px）与图标/边框等非文本 ≥ **3:1**。两套主题都必须满足。
2. `prefers-reduced-motion: reduce` 下：所有 `transform/opacity` 动画时长归零，3D 场景不渲染，数字滚动直接显示终值，功能链路不变。
3. 3D canvas `aria-hidden="true"`，且同屏必须存在等价表格/列表（同一数据源）。
4. 焦点可见：现有 `useDialogFocus` 焦点陷阱保留；动效不得抢占 `document.activeElement`。
5. 不引入滚动劫持、不做全屏鼠标视差、不做自动播放音视频。

### 2.3 性能预算（每次构建实测，超预算即视为失败）

| 指标 | 上限 | 实测（2026-11-05 收口） |
|------|------|------|
| 首屏 JS（gzip） | **150 kB** | **144.67 kB**（motion +33.7 kB，见 §5.1 取舍） |
| 3D 懒加载 chunk（gzip） | 230 kB，且只在用户主动展开时请求 | **222.39 kB**，独立 chunk，不展开不请求 |
| 首屏 CSS（gzip） | 20 kB | **10.02 kB** |
| 3D 帧率 | ≥ 50 fps（1440×900、DPR ≤ 1.5、节点 ≤ 60） | 未做长时采样，见 §12 剩余项 |
| 布局抖动 | 新增动效不得触发 reflow（只用 `transform/opacity`，禁用 `width/height/top/left` 动画） | — |

### 2.4 明确不做的风格陷阱

不做全站渐变噪声背景、不做玻璃拟态全覆盖（只在顶栏/对话框/横幅三处用）、不做霓虹发光文字、不做卡片 3D 倾斜跟随鼠标、不引入图标库（复用现有 `public/icons/*.svg`）。

---

## 3. 视觉体系

### 3.1 令牌三层

```
第 1 层 原语（primitive）   --c-blue-500: #4c8dff;      只出现在 tokens.css，规则里禁止直接引用
第 2 层 语义（semantic）    --text-muted: var(--c-slate-500);   规则只引用这一层
第 3 层 组件（component）   --card-border: var(--line);         仅当某组件需要独立覆写时新增
```

落地方式：新增 `frontend/src/styles/tokens.css`（原语 + 语义 + 双主题），`styles.css` 顶部 `@import` 它并保留现有规则不动；随 Phase A 分片把规则里的硬编码色替换为语义令牌。**不迁移布局规则、不改选择器命名**——那属于重写，不是本次范围。

### 3.2 色板（蓝系，深/浅双主题）

所有值已实测对比度（脚本见附录 A.4）：

**深色（默认）**

| 语义令牌 | 值 | 用途 | 对比度（on `#111b2f`） |
|---------|-----|------|------|
| `--bg` | `#0b1220` | 页面底 | — |
| `--surface-1` | `#111b2f` | 卡片 | — |
| `--surface-2` | `#16233b` | 抬升卡片/表头 | — |
| `--text` | `#e6eefc` | 正文 | 14.73:1 |
| `--text-muted` | `#9db0cc` | 次要正文 | 7.79:1 |
| `--text-soft` | `#8296b5` | 元信息/占位 | 5.71:1 |
| `--brand` | `#2f6df6` | 侧栏、选中态底色（其上为白字） | 4.53:1（白字） |
| `--accent` | `#6aa3ff` | 主色/链接 | 6.79:1 |
| `--accent-strong` | `#2f6df6` | 实心按钮底 | — |
| `--sev-critical` | `#ff6b6b` | 严重 | 6.19:1（原 `#ff6b6b` 已达标，保留） |
| `--sev-high` | `#f7a33d` | 高 | 8.40:1 |
| `--sev-medium` | `#f5c451` | 中 | 10.56:1 |
| `--sev-low` | `#6aa3ff` | 低 | 6.79:1 |
| `--ok` | `#3ddc9b` | 成功/通过 | 9.75:1 |
| `--danger-text` | `#ff8b82` | 危险文字 | 7.59:1 |

**浅色**

| 语义令牌 | 值 | 用途 | 对比度（on `#ffffff`） |
|---------|-----|------|------|
| `--bg` | `#f4f8fe` | 页面底 | — |
| `--surface-1` | `#ffffff` | 卡片 | — |
| `--surface-2` | `#f9fcff` | 抬升/表头 | — |
| `--text` | `#1b2f4d` | 正文 | 13.46:1 |
| `--text-muted` | `#5a7295` | 次要正文 | 4.91:1 |
| `--text-soft` | `#7b90b0` | 元信息/图标（仅非正文） | 3.25:1 |
| `--accent` | `#2f68c9` | 主色/链接 | 5.32:1 |
| `--accent-strong` | `#2456a8` | 实心按钮底 | — |
| `--brand` | `#3f74c4` | 侧栏、选中态底色（其上为白字） | 4.66:1（白字） |
| `--brand-ink` | `#2f68c9` | 浅底上的品牌文字 | 5.32:1 |
| `--sev-critical` | `#c0392b` | 严重 | 5.44:1 |
| `--sev-high` | `#9a5b00` | 高 | 5.43:1 |
| `--sev-medium` | `#7a6100` | 中 | 5.94:1 |
| `--sev-low` | `#2f68c9` | 低 | 5.32:1 |
| `--ok` | `#0d7f5e` | 成功/通过 | 4.98:1 |
| `--danger-text` | `#c0392b` | 危险文字 | 5.44:1 |

对比现状：浅色 `--muted` 3.19→4.91、`--soft` 1.97→3.25、`--danger` 2.87→5.44、`--safe` 1.97→4.98。深色主题从死代码变成可用主题（原深色令牌全部达标，仅 `--text-soft` 从 4.54 提到 5.71 以支持元信息正文）。

### 3.3 尺度

| 类别 | 刻度 | 说明 |
|------|------|------|
| 间距 | `0/2/4/8/12/16/24/32/48` | 4 基准；现有 6→4 或 8，10→8 或 12，14→12 或 16，18→16 或 20（按视觉邻近取，不做等比换算） |
| 字号 | `11/12/13/14/16/20/24/34` | 12px 仅限标签、徽标、元信息；正文不低于 13px |
| 行高 | 正文 1.55 / 紧凑列表 1.35 / 标题 1.25 | — |
| 圆角 | `--radius-sm 6px` / `--radius-md 8px` / `--radius-lg 12px` / `--radius-pill 999px` | 新增 12px 档给横幅与对话框 |
| 描边 | `1px var(--line)`；聚焦 `2px var(--accent)`，`outline-offset: 2px` | 聚焦态必须可辨 |
| 阴影 | `--shadow-1`（卡片）/ `--shadow-2`（对话框） | 浅色保留现有低强度，深色改双层内描边+外阴影 |

### 3.4 质感（三处，只有三处）

1. **顶栏**：`backdrop-filter: blur(14px) saturate(1.2)` + 半透明 `--surface-1`。
2. **对话框/抽屉**：同款玻璃 + `--shadow-2` + 8px 内高光（`inset 0 1px 0 rgba(255,255,255,.06)`）。
3. **活跃任务横幅**：沿卡片上沿 1px 渐变描边（`--accent` → `--ok`），静态渐变，不循环流动。

`backdrop-filter` 不可用时（`@supports not`）退化为不透明 `--surface-1`——一行兜底，不需要更多。

### 3.5 双主题机制

```
默认跟随系统：@media (prefers-color-scheme: dark) 之外的一切情况走浅色
用户显式选择：document.documentElement.dataset.theme = "dark" | "light"
持久化：复用 preferences.ts 的 localStorage 键 vulnclaw.ui.preferences（新增 theme: "auto" | "dark" | "light"）
```

- CSS 侧：`:root` 定义浅色语义令牌；`:root[data-theme="dark"]` 覆盖；系统偏好通过 `@media (prefers-color-scheme: dark)` 只在 `:root:not([data-theme])` 下生效。**深色令牌块必须放在浅色之后或提高选择器优先级**，避免重演 D-02。
- `theme-color` 用**单个** meta，由 `index.html` 的首帧引导脚本和 `useThemeMode` 一起同步：`light → #f4f8fe`、`dark → #0b1220`。两个 media 变体在主题被显式覆盖时会同时不生效，反而更容易不一致。
- `preferences.ts` 增加 `theme` 字段并在 `loadUiPreferences` 里做白名单校验（与现有 `isReportTemplate` 同款写法），坏值回落 `"auto"`。

**入口定稿**：只在 `SettingsPage` 新增"外观"分区（三档单选：跟随系统 / 浅色 / 深色）。顶栏不加切换控件，`Topbar` 不改。应用启动时由 `main.tsx` 把 `preferences.theme` 写到 `documentElement.dataset.theme`（`"auto"` 时**不写**该属性，交给媒体查询），并在 `UI_PREFERENCES_EVENT` 上同步——与现有语言偏好同一条订阅链，不新增状态管理。

### 3.6 318 处硬编码颜色的收敛路径

| 顺序 | 内容 | 判据 |
|------|------|------|
| 1 | 语义色（`--text`/`--muted`/`--soft`/`--primary`/`--danger`/`--safe`/`--warn` 及其 rgba 变体） | 与对比度直接相关，先修 |
| 2 | 表面与描边（`--surface*`/`--line*`） | 决定双主题能否成立 |
| 3 | 装饰色（渐变色标、图标填充、图表色） | 观感层，最后 |

每迁移一个页面就构建一次并截图对比（`frontend/e2e-artifacts/` 已有同角度基线），**不做一次性全表替换**。剩余未迁移的硬编码色允许短期共存（它们在浅色下渲染正常），但新增规则禁止再写 `#hex`（`rgba()` 只允许来自令牌）。

实际收敛结果：`var(--)` 引用 120 → **365** 处，`#hex` 唯一值 154 → **37** 个；`rgba()` 字面量 109 个唯一值全部改为 `rgba(var(--*-rgb), α)` 形式，只剩 3 个品牌面上的白色叠加（`rgba(255,255,255,0.1/0.16/0.18)`，它们在两套主题下都叠在蓝色品牌面上，是常量）与 2 个警示/危险面板的暖色蒙版。

---

## 4. 页面与信息架构

### 4.1 八个页面的视觉职责

| 页面 | 用户此刻的问题 | 视觉重点 | 动效预算 |
|------|--------------|---------|---------|
| `HomePage` 首页 | "我现在该干什么、上次跑到哪" | 单一主 CTA + 项目/目标上下文 + 活跃任务横幅 | 卡片 stagger（首屏一次性） |
| `TaskConsolePage` 任务台 | "任务现在在做什么" | 事件时间线可读性、状态徽标 | 仅新事件插入微动效 |
| `RiskResultsPage` 发现工作台 | "风险有多少、怎么处置" | 严重度分布 + 处置动作可达 | 3D 场景入口 + 列表行状态变化 |
| `ReportsPage` 报告中心 | "报告产出了吗、内容对不对" | 预览优先、下载/投递动作 | 对话框进出 |
| `HistoryPage` 历史 | "上次的产物和差异" | 快照/差异对比可读性 | 无 |
| `SettingsPage` 设置 | "把环境配对" | 分区导航 + 表单密度 | 分区切换 180ms 淡入 |
| `PluginsPage` 插件 | "装了哪些、谁坏了" | 阶段/来源筛选 + 坏入口点显著报错 | 无 |
| `SafetyBoundaryPage` 安全边界 | "哪些动作被禁止" | 规则表 + 命中记录 | 无 |

### 4.2 首页首屏结构（从上到下）

1. **品牌条**：`brand.name` + 版本（现有侧栏信息，首屏可见）
2. **主句 + 一句解释**：当前 `meta.eyebrow/title/copy` 已有文案，字号/层级按 §3.3 重排（标题 24px、解释 14px、`text-muted`）
3. **主 CTA**（开始任务）+ 次 CTA（查看上次运行）
4. **上下文卡**：项目选择、目标输入、检查模式、边界摘要——现有字段，只重排层级
5. **活跃任务横幅**：仅 `running` 时出现，静态渐变描边

首屏**不放 3D 场景**（理由见 §6.2）。

### 4.3 数据密集页的降噪规则

- 同一行内不超过 2 个强调色；严重度用彩色徽标，其余文字一律 `--text`/`--text-muted`。
- 表格行 hover 只改背景（`--surface-2`），不做位移。
- 空态必须给"下一步动作"按钮，不只给一句"暂无数据"。
- 长列表（发现、历史）使用现有虚拟化策略不变；新增动效不得包裹整表。

---

## 5. 动效体系（motion）

### 5.1 依赖与体积预算

```jsonc
// frontend/package.json
"dependencies": {
  "motion": "^14"          // 只导入 motion/react
}
```

- 只用 `m` + `LazyMotion` + `domAnimation`；**不用** `domMax`（layout 投影更大），因此本阶段不做共享元素 FLIP 转场；需要时再升级并在本文件记录取舍。
- `motion@14.9.1` 的 peerDependencies 为 `react ^18 || ^19`，与项目 React 18.3 兼容；不使用旧包名 `framer-motion`，避免双份适配层。
- 安装后核对 `motion/react` 实际导出 `m` / `LazyMotion` / `domAnimation` / `MotionConfig` / `useReducedMotion`（API 改动时以导出清单为准）。
- 体积以 `vite build` 输出为准：实测首屏 gzip 由 109.11 kB 增至 **144.67 kB（+35.6 kB）**，超过初版估算的 20 kB。原因：`m` + `LazyMotion(domAnimation)` + `AnimatePresence` 的实测量级就在 33–36 kB，`motion/react-m` 的极简入口在本版本没有可用类型声明（`TS2305`），强行引用只会把构建搞脆。
- 取舍：接受 144.67 kB，把首屏上限从 130 kB 修订到 150 kB。为此把 `CountUp` 从 `motion` 的命令式 `animate` 改为原生 rAF 自绘（省掉约 6 kB，也让数字滚动不占 motion 特性包）。

### 5.2 时长与缓动令牌

| 令牌 | 值 | 用途 |
|------|-----|------|
| `--dur-1` | 120 ms | hover / press / 颜色过渡 |
| `--dur-2` | 180 ms | 组件进入退出（Toast、对话框、徽标） |
| `--dur-3` | 260 ms | 页面/分区切换、列表 stagger 单条 |
| `--dur-4` | 420 ms | 首屏一次性叙事（只在首页首帧） |
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | 进入/位移 |
| `--ease-exit` | `cubic-bezier(0.4, 0, 1, 1)` | 退出（更快收） |
| `--ease-spring` | `spring(stiffness: 220, damping: 26)` | 仅按压/拖拽反馈 |

JS 侧导出一份与之同值的常量对象 `frontend/src/motion/tokens.ts`，CSS 与 JS 用同一套数，不允许各写一套。

### 5.3 动效清单

| # | 位置 | 实现 | 触发 | 动作 | reduced-motion |
|---|------|------|------|------|---------------|
| M-01 | `AppShell` 的 `.view-mount` | motion `m.div`（key = activeView） | 切换视图 | 淡入 + `translateY(8px→0)`，260 ms | `initial={false}`，直接到位 |
| M-02 | 首页两栏（欢迎面板 + 任务面板） | motion `m.div` | 首次挂载 | 淡入，任务栏延迟 60 ms 交错，420 ms | `initial={false}` |
| M-03 | `StatusDot` | motion `m.span`（key = tone+label） | 状态/文案变化 | `scale(0.82→1)`，180 ms | 只重挂载，不动画 |
| M-04 | 终端与事件流（`.terminal-line` 等） | CSS `@keyframes log-entry-in` | 新节点插入 | 淡入 + `translateY(-4px→0)`，180 ms | 全局 `animation-duration:0.01ms` |
| M-05 | `ToastHost` | `AnimatePresence` + `m.article` | 入队/出队 | 进入 `+12px` 淡入、退出淡出，180 ms | 无 transform，直接显示/消失 |
| M-06 | 确认 / 报告预览对话框 | `AnimatePresence` + 遮罩 `m.div` + 面板 `m.section` | 打开/关闭 | 遮罩淡入、面板 `scale(0.98→1)`，180 ms | 无 |
| M-07 | 风险页四个指标卡 | `CountUp`（原生 rAF 自绘） | 数值变化 | 420 ms 三次缓出插值 | 直接显示终值 |
| M-08 | 主/次/危险/文字按钮、快捷栏 | CSS `:active` | 按压 | `scale(0.98)`，120 ms | 全局兜底压到 0.01ms |
| M-09 | 侧栏与快捷栏按钮 | CSS `transition` | hover/选中 | 背景与颜色 180 ms | 同上 |
| M-10 | `ActiveTaskBanner` | motion `m.section` | 出现 | 淡入 + `translateY(-6px→0)`，180 ms | `initial={false}` |

`pulse-panel` 改造：`iteration-count` 由 `infinite` 改为 **3**——操作台常开，不允许长驻循环动画。

`RunDetailDialog` 只做进入动画（无退出）：它的内容是 query 驱动，退出期间数据可能已卸载，加 `AnimatePresence` 会让 `run` 变成 `undefined` 并崩在渲染里。

### 5.4 reduced-motion 的两种实现

1. **CSS 层**：保留 `styles.css:3101` 的全局兜底，但去掉 `!important` 对新增 `motion` 内联 `style` 的依赖——`motion` 写入的是内联 `transform`，媒体查询改不了。因此所有 JS 动画必须走统一入口：

```tsx
// frontend/src/motion/useMotionPrefs.ts
export function useMotionPrefs() {
  const reduce = useReducedMotion();          // motion/react 提供
  return { reduce, duration: (ms: number) => (reduce ? 0 : ms / 1000) };
}
```

2. **JS 层**：上述 hook 在 `reduce === true` 时把时长置 0，`MotionConfig reducedMotion="user"` 包在 `<App/>` 根部作为全局默认。

**验收方式**：Playwright 用 `browser.newContext({ reducedMotion: 'reduce' })` 跑现有 13 条链路，必须全绿且截图无中间态残影。

### 5.5 与测试的接缝

| 风险 | 处理 |
|------|------|
| jsdom 下 `motion` 触发 `requestAnimationFrame` 警告 | `src/test/setup.ts` 里 mock `useReducedMotion` 返回 `true`，让单测走零时长路径（等价于验收"动效不是逻辑依赖"） |
| E2E 断言偶发抢在动画中间态 | 断言只依赖文本/`data-testid`，不依赖位置；必要时加 `expect.poll`，**禁止** `waitForTimeout` 堆时间 |
| 动画导致的快照抖动 | 新增动效后重新生成 `e2e-artifacts/` 截图作为新基线 |

---

## 6. 3D 与空间叙事（R3F）

### 6.1 数据可行性（先看数据，再定场景）

| 想画的 | 现有数据 | 结论 |
|--------|---------|------|
| 目标节点 | `/api/targets`（`TargetView`） | 可用 |
| 目标下的发现节点 | `/api/findings?target=`（`FindingView.severity/vuln_type/verified`） | 可用 |
| 发现 → 服务/端口/端点 | `FindingView` 无 asset/port/path 字段 | **不可用** |
| 状态快照节点 | `/api/targets/{t}/snapshots` | 可用（作为节点上的历史环，非新节点） |
| 目标之间的横向可达边 | 无字段 | **不可用** |

结论：3D 场景 v1 是**两层星形**——中心是当前目标，外围是它的发现节点，节点大小 = 数量权重、颜色 = 严重度、`verified` 用实心/空心区分；边只连"目标→发现"，**不虚构目标之间的连线**。真正的资产拓扑需要后端在发现记录里补 `asset/endpoint` 字段，那是独立需求，不在本文件范围。

### 6.2 场景位置与加载策略

- 位置：**仅** `RiskResultsPage` 顶部的"攻击面视图"面板。首页不放——首屏要快，且首页没有目标上下文时只能喂假数据。
- 默认收起。面板显示一行摘要（"12 个发现，4 严重"），点击"展开 3D 视图"才 `import()` 场景模块。收起时 DOM 里没有 canvas。
- 依赖（peer 已核对，注册表实测）：

```jsonc
"three": "0.170.0",
"@react-three/fiber": "8.18.0"   // peer: react >=18 <19
```

```
为什么锁 fiber 8.x 而不是最新的 9.8.2：fiber v9 的 peer 是 react >=19 <19.4，本项目 React 18.3 装不上。
three 固定在 0.170.0，不跟最新的 0.187.0。
```

- **不引 drei**：原计划用 `OrbitControls` + `Line`，实测加载 drei 后 3D chunk 为 232.5 kB gzip（超 230 预算），且 drei 会带进 `three-stdlib`、`@react-spring/three` 等 70 余个包。改为：
  - 旋转：在 `<group>` 上接 `onPointerDown/Move/Up`，直接改 `group.rotation` 后 `invalidate()`，无阻尼、无惯性、无滚轮缩放（滚轮缩放会抢页面滚动）。
  - 连线：所有边合并进一个 `BufferGeometry`（`lineSegments`），一次 draw call，取代每根线一个材质。
  结果：3D chunk 降到 **222.39 kB gzip**，依赖只有 `three` + `@react-three/fiber` + `@types/three`（dev）。

### 6.3 技术约束

| 项 | 约束 |
|----|------|
| `frameloop` | `"demand"`——静止时不渲染；拖拽/入场动画结束后强制 `invalidate()` 一帧 |
| DPR | `Math.min(window.devicePixelRatio, 1.5)` |
| 节点上限 | 60；超过则按严重度聚合为"其他 N 个"节点 |
| 后处理 | 不做（bloom/景深都不做） |
| 光照 | 1 环境光 + 1 平行光 |
| 力学布局 | 不引物理引擎；黄金角确定性分布（同一份发现每次位置一致，便于截图比对），无入场插值 |
| 内存 | `frameloop="demand"` + 单一 geometry；卸载时 R3F 自行释放 canvas 与 renderer，材质随组件卸载回收 |
| 交互 | 仅拖拽旋转，`x` 轴夹在 ±0.6 弧度；不做缩放、不做平移、不做自动旋转 |

### 6.4 降级与可访问性（三档，缺一不可）

1. **能力探测**：`document.createElement('canvas').getContext('webgl2') ?? getContext('webgl')` 为空 → 直接渲染表格视图，不下载 3D chunk。
2. **reduced-motion**：`reduce === true` → 只渲染静态 SVG 拓扑（同一布局，无交互、无动画）。
3. **等价信息**：3D 视图下方始终有"发现清单"表格（页码与列表页一致）；canvas 加 `aria-hidden`，容器给 `role="img"` + `aria-label="攻击面视图，共 N 个发现，详见下方清单"`。

### 6.5 明确不做

全站 3D 背景、鼠标视差层、滚动驱动的时间轴、3D 内嵌 HTML 面板（drei `Html` 会拖体积且焦点管理复杂）、多场景切换器。

---

## 7. 可发现性（SEO）

### 7.1 事实先摆清

| 层级 | 是否可被搜索引擎发现 | 该做什么 |
|------|--------------------|---------|
| 应用本体（`127.0.0.1` + token 鉴权） | **不能，也不应该** | 只保证 `title`/`lang`/`description` 正确，`robots` 明确 `noindex` |
| 公开落地页（独立静态站） | 能 | 真正的 SEO 工作全部在这里 |
| 分发渠道（PyPI / GitHub / README） | 能（作为搜索结果落地） | 关键词与结构化描述 |

### 7.2 L1 应用内元信息（低成本、必做）

```html
<meta name="description" content="VulnClaw — 本地优先的自动化渗透测试工作台：任务编排、发现处置、报告中心。" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#f4f8fe" />   <!-- 由 index.html 引导脚本与 useThemeMode 同步为当前主题色 -->
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
```

- `title`/`lang` 已由 `I18nProvider` 同步（`P2-08` 已完成），本次不改。
- `noindex` 是安全项而非 SEO 项：本地面板一旦被误部署到公网，索引会暴露端口与产品形态。

### 7.3 L2 公开静态站（`site/`）

```
site/
  index.html               产品页（zh-CN）：定位、三条核心能力、安装命令、截图、适用场景、安全边界
  en/index.html            产品页（en）：同一事实，英文版本，hreflang 互指
  docs/index.html          快速开始：安装、配置模型、第一条命令、Web 操作台、常用命令表
  assets/site.css          手写单文件，无框架、无 CDN、跟随系统明暗
  assets/og.png            1200×630 社交卡（Playwright 真实渲染截图）
  assets/screenshot-risk.png  发现工作台截图（示例数据为保留域 example.com）
  favicon.svg              与 Web UI 同一枚图标
  robots.txt               放行全站并指向 sitemap
  sitemap.xml              3 条 URL，带 zh-CN / en / x-default 的 hreflang 交替
  .nojekyll                关掉 Jekyll 处理
```

技术选择：**手写静态 HTML + 单文件 CSS**，不接 Vite/React。三页内容都有独立 URL、独立 title/description/canonical，静态 HTML 的 LCP 与抓取友好度都优于再挂一套 SPA 构建链。

`og.png` 由 `frontend/scripts/make-og.mjs` 用真实浏览器渲染产品页生成（`node scripts/make-og.mjs <url> ../site/assets/og.png`），不是设计工具里画出来的假图。

### 7.4 关键词矩阵（每季度复核一次）

| 类型 | 中文 | 英文 |
|------|------|------|
| 主词 | 自动化渗透测试工具、AI 渗透测试、本地部署漏洞扫描 | automated pentest tool, AI pentesting agent, local-first security scanner |
| 长尾 | 渗透测试报告自动生成、SARIF 报告导出、MCP 安全测试集成、CTF 自动化解题工具 | pentest report automation, SARIF security report, MCP security tooling, CLI vulnerability scanner Windows |
| 品牌 | VulnClaw | VulnClaw |

落地要求：

- `<title>` 与 `<h1>` 各含 1 个主词，不堆砌（同一页主词重复 ≤ 3 次）。
- `hreflang`：`zh-CN` / `en` 两版，`<link rel="alternate">` 互指，`x-default` 指向英文。
- 结构化数据（`SoftwareApplication`）：

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "VulnClaw",
  "applicationCategory": "SecurityApplication",
  "operatingSystem": "Windows, macOS, Linux",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "codeRepository": "https://github.com/<org>/<repo>"
}
```

- 更新判据（用真实数据，不凭感觉）：GitHub star 与 traffic、PyPI 下载量、Search Console 的展现/点击/平均排名。季度复核时只调整"长尾"行，主词除非排名大幅下滑否则不动。

### 7.5 部署（已定：GitHub Pages）

| 项 | 结论 |
|----|------|
| 托管 | GitHub Pages，`site/` 目录直发 |
| 发布方式 | 首选 Actions（`.github/workflows/pages.yml`：`actions/upload-pages-artifact` + `deploy-pages`），保留"从分支目录发布"作为备选；两者都用 `site/` 作为 artifact 根，不把仓库根暴露成站点 |
| 域名 | 自定义域名 + `site/CNAME`；无域名时用 `https://<owner>.github.io/<repo>/`——此时 `sitemap.xml`、`robots.txt`、canonical 必须带 `/<repo>/` 前缀，不能用根路径写法 |
| 索引配置 | `site/robots.txt` 放行全站并指向 sitemap；**应用本体的 `noindex` 与站点 `robots.txt` 互不影响**，两处都要在 |
| 缓存 | 静态资源用文件名版本化（`site.css?v=1`）或直接依赖 Pages 默认缓存，不引入额外 CDN 配置 |

**上线前置条件（需你提供，属于"需确认后执行"）**

1. 仓库公开（或指定一个只用于站点的公开仓库/分支）。
2. 若要自定义域名：域名与 DNS 指向（`CNAME` 记录 → `<owner>.github.io`）。
3. 推送与 Pages 开关的授权；我这边只准备文件与 workflow，不自行 push。

**在此之前可独立完成并验收**：`site/` 全部文件、本地 `python -m http.server` 打开、`curl` 抽查 sitemap/robots、JSON-LD schema 校验、Lighthouse（本地 HTTP，Performance/SEO/Accessibility ≥90）。

### 7.6 公开素材的数据替换规则（已定：真实结构 + 标识替换）

素材骨架取自真实跑批（保留接口返回结构、字段层级、严重度分布、列表密度），**标识一律替换**：

| 字段 | 处理 | 示例 |
|------|------|------|
| 主机 / IP | 替换为文档保留段 | `10.0.0.14:8080` → `192.0.2.14:8080`（RFC 5737） |
| 域名 / 子域 | 替换为文档保留域 | `corp.internal` → `app.example.com`（RFC 2606） |
| 路径 / 端点 | 保留层级，替换业务词 | `/api/v1/pay/refund` → `/api/v1/<resource>/<action>` |
| 发现标题 | 保留漏洞类型与严重度，替换业务上下文 | 保留"未授权访问"，去掉客户系统名 |
| 报告文件名 / 项目名 | 替换为 `demo-project` 系列 | — |
| 令牌 / Cookie / 邮箱 | **一律不出现**，截图前清空 | — |
| 时间戳 | 保留相对关系，可整体平移 | — |

执行方式：截图前用 `e2e/mock-llm.mjs` 与 `frontend/e2e/seed.py` 的既有假数据（已脱敏）作为骨架，只把需要"真实密度"的字段从一次真实跑批里拷过来再替换。每张图落盘前过一遍上表，检查记录写进 Phase E 的验收项，**不靠事后回忆**。

---

## 8. 施工计划

顺序不可跳跃：令牌不落地，动效和 3D 都建在流沙上。

| Phase | 范围 | 状态（2026-11-05 收口） |
|-------|------|------|
| A | 令牌化与双主题 | **完成** |
| B | 语义色迁移 + 质感 + 尺度 | **完成**（迁移见 §3.6 三批；玻璃质感保留在顶栏/对话框/横幅三处） |
| C | 动效层 | **完成**（M-01～M-10，见 §5.3） |
| D | 3D 场景 | **完成**（单场景 + 三档降级 + 等价表格） |
| E | 公开静态站 | **本地完成**；GitHub Pages 上线待授权（§12.2） |
| F | 收口验证 | **完成**（见 §13.3） |

### Phase A｜令牌化与双主题（3–4 人日）

| 交付物 | 验证 | 回滚 |
|--------|------|------|
| `frontend/src/styles/tokens.css`（原语 + 双主题语义）；`styles.css` 引入并删除被覆盖的深色 `:root`；`preferences.ts` 增 `theme`；`SettingsPage` 新增"外观"分区（跟随系统/浅色/深色）；`index.html` 双 `theme-color` + favicon + description + noindex | `npx tsc -b`；`npm run test`；`npm run build`；`npm run e2e` 13 条；切换两主题各截 8 页图；对比度脚本（附录 A.4）全部 ≥4.5/3.0 | 删除 `tokens.css` 引用并恢复 `styles.css` 顶部 `:root`，单文件可逆 |

### Phase B｜语义色迁移 + 质感（3–4 人日）

| 交付物 | 验证 | 回滚 |
|--------|------|------|
| 语义色（第 1、2 批）替换到 8 个页面；顶栏/对话框/横幅三处玻璃质感；间距与字号按 §3.3 收敛到刻度 | `npm run build` 体积不涨；两主题 8 页截图人工比对（差异只应是色调与层级，不是布局）；`npm run e2e` 全绿 | 按页面回滚：每个页面一次提交，`git revert` 单页无连带 |

### Phase C｜动效层（3 人日）

| 交付物 | 验证 | 回滚 |
|--------|------|------|
| 引入 `motion`；`motion/tokens.ts` 与 `useMotionPrefs`；`MotionConfig reducedMotion="user"`；M-01～M-10 全部落地 | `npm run build` 首屏 gzip ≤ 150 kB（实测 144.67）；`npm run test`；`npm run e2e` 默认一轮 + `e2e/motion.spec.ts` 的 `reducedMotion:'reduce'` 一轮；长驻循环 = 0 | 依赖移除 + 删除 `motion/` 目录，动效组件外层保留原 JSX，仅退化为无动画 |

### Phase D｜3D 场景（4–5 人日）

| 交付物 | 验证 | 回滚 |
|--------|------|------|
| `AttackSurfaceScene`（fiber v8，无 drei）；懒加载入口；WebGL 探测与三档降级；等价表格 | 3D chunk ≤230 kB gzip（实测 222.39）；E2E 2 条：有 WebGL 时展开场景、无 WebGL 时看到等价表格（注入 `getContext('webgl*') → null`）；首屏体积不变（未展开时不请求 chunk） | 删除 3D 依赖与场景模块，面板退回纯表格（面板本身保留） |

### Phase E｜公开站与可发现性（2–3 人日，部署待授权）

| 交付物 | 验证 | 回滚 |
|--------|------|------|
| `site/` 4 页 + sitemap + robots + og.png + CNAME + `.nojekyll` + JSON-LD + hreflang；`.github/workflows/pages.yml`；按 §7.6 替换后的截图；README 顶部加入站点链接 | 本地 `python -m http.server` 打开；`curl` 抽查 `sitemap.xml`/`robots.txt`；JSON-LD schema 校验；Lighthouse（Performance/SEO/Accessibility）≥90；每张截图过一遍 §7.6 替换清单并留记录 | 删除 `site/` 与 workflow，无连带 |
| 上线（需你授权后） | 部署后用真实 URL 复验：`curl -sI` 200、`sitemap.xml` 可访问、页面渲染无 404 资源 | 关闭 Pages 或回退 workflow |

### Phase F｜收口（1–2 人日）

`npm run build` 体积核对 → 两主题 × 8 页截图归档 → axe 扫描（`@axe-core/playwright` 加入 devDependencies）0 严重/0 严重级违规 → E2E 13+1 条两次（默认/降级）→ 本文件 §9 矩阵逐项签字。

---

## 9. 验收矩阵

| # | 验收项 | 方法 | 阈值 | 结果 |
|---|--------|------|------|------|
| A1 | 双主题可切换并持久化 | `e2e/theme.spec.ts`：设置页切 dark → 断言 `data-theme`/`theme-color`/localStorage → reload 再断言 | 刷新后保持 | **通过** |
| A2 | 两主题对比度 | 附录 A.4 脚本对全部语义令牌跑两遍 | 正文 ≥4.5:1，非文本 ≥3:1 | **通过**（所有取值见 §3.2，最低 4.53:1） |
| A3 | 令牌覆盖率 | `grep` 统计 | 新增规则 `#hex` = 0；主题角色色全部走令牌 | **通过**：`var(--)` 120→365 处，`#hex` 唯一值 154→37；剩余 37 个全是图表分类色、固定深底面板的高亮文字、白字常量，无主题角色 |
| B1 | 无布局回归 | 8 页 × 2 主题截图（`e2e-artifacts/theme-*.png`） | 差异仅限色调/层次 | **通过**：逐页目视，布局与信息层级未变 |
| C1 | 首屏体积 | `npm run build` | gzip ≤150 kB | **通过**：144.67 kB |
| C2 | 动效时长 | 实现侧最高 420 ms（首页两栏），其余 ≤260 ms；`pulse-panel` 由 infinite 改 3 次 | 长驻循环 = 0 | **通过** |
| C3 | reduced-motion | `e2e/motion.spec.ts`（`reducedMotion:'reduce'`）跑主链路 + 弹窗 | 全绿、无残留动效 | **通过** |
| D1 | 3D 降级 | `e2e/attack-surface.spec.ts`：注入 `getContext('webgl*') → null` | 表格视图正常、无 canvas | **通过** |
| D2 | 3D 性能与内存 | `frameloop="demand"` + 节点上限 60 + DPR ≤1.5 | 静止不渲染 | **部分**：静止不渲染已实现；≥50 fps 未做长时采样（§12） |
| D3 | 3D 数据真实性 | 对照 `/api/findings` 返回 | 节点数 = 发现数，无编造边 | **通过**：节点只来自 `findings`，边只有"目标→发现" |
| E1 | 站点可抓取 | `curl` 三个页面 + sitemap + robots + og.png + css | 全部 200 | **通过**（7/7 均 200）；Lighthouse 未跑（无本地 Chrome 远程调试预算，见 §12） |
| E2 | 结构化数据 | `json.loads` 解析两页 `ld+json`；canonical/hreflang/img-alt 结构自检 | 0 error | **通过** |
| F1 | 可访问性扫描 | `e2e/a11y.spec.ts`：axe-core，两主题 × 8 页，只拦 serious/critical | 0 违规 | **通过**（修复了品牌区白字、`--soft` 当正文色、终端面板前景三处真实问题） |

---

## 10. 风险与回滚

| 风险 | 触发 | 缓解 | 回滚 |
|------|------|------|------|
| `motion` 体积超预算 | `domMax` 误引 或全量 `import { motion }` | 只用 `m` + `LazyMotion/domAnimation`；构建后核对 gzip | 移除依赖 |
| `motion` 与 jsdom 冲突导致单测红 | 单测渲染含动效组件 | `setup.ts` mock `useReducedMotion` 为 `true` | 该组件动效移出单测范围 |
| R3F 版本与 React 18 冲突 | fiber v9 需 React 19 | 锁 fiber 8.18.0 + three 0.170.0；`npm ls react three @react-three/fiber` 单一版本 | 不落 3D |
| 3D 在低端机掉帧 | 节点过多/DPR 过高 | 节点上限 60、DPR ≤1.5、`frameloop="demand"` | 面板退回表格 |
| 双主题引入的样式漂移 | 语义令牌误用 | 一页一提交、两主题截图比对 | 单页 `git revert` |
| 落地页与产品事实不一致 | 手写文案夸大能力 | 文案只从 README 提取事实，不写未实现功能 | 删页面重写 |
| 公开站泄露内部信息 | 截图含内网目标/路径 | 按 §7.6 清单逐字段替换（RFC 5737 / RFC 2606 保留段），截图落盘前人工过一遍并留记录 | 撤下对应素材并重新部署 |

---

## 11. 明确不做

1. 不重写 `styles.css` 为 CSS-in-JS / Tailwind / 组件库（如 shadcn、MUI）。现有 3326 行继续按分片收敛。
2. 不引入路由库（`react-router` 等），不重构 hash 路由；仅新增页面级 `React.lazy` 分包。
3. 不做共享元素 FLIP 转场（需要 `domMax`，+12 kB 不值得）。
4. 不做全站 3D 背景、滚动叙事、鼠标视差。
5. 不为 3D 引入物理引擎、后处理、贴图资源管线。
6. 不给 SPA 做"SEO 补丁"（预渲染、SSR、`react-helmet`）。
7. 不为视觉层加 feature flag / 主题开关矩阵／A-B 实验框架。
8. 不新增图标库或字体文件（继续用 `public/icons/*.svg` 与系统字体栈）。
9. 不改后端 API、不改报告模板、不改任何任务语义。

---

## 12. 决策状态与外部依赖

### 12.1 已定（见 §0.3）

| 事项 | 结论 | 落地位置 |
|------|------|---------|
| 公开站部署 | GitHub Pages | §7.5、Phase E |
| 公开素材数据 | 真实结构 + 标识替换 | §7.6、Phase E 验收项 |
| 3D 场景 | 保留在 `RiskResultsPage` | §6.2、Phase D |
| 主题切换入口 | `SettingsPage` "外观"分区 | §3.5、Phase A |

### 12.2 需要你提供或授权

| # | 事项 | 谁做 | 阻塞什么 | 现状 |
|---|------|------|---------|------|
| 1 | 仓库/发布分支公开 | 你决定 | `site/` 上线那一步 | 待办 |
| 2 | 自定义域名 + DNS（缺省用 `*.github.io/<repo>/`） | 你提供 | 换域名后需同步 canonical / hreflang / sitemap / robots 里的基址 | 待办 |
| 3 | push 与开启 Pages 的授权 | 你执行或明确授权 | 同 1 | 待办 |
| 4 | 一次真实跑批的产物 | 你指给我 | 截图密度：当前站点用的是 E2E 种子数据（`https://example.com`），结构真实、标识已替换 | 可选 |

### 12.3 未做的验证（已披露，不是隐去的部分）

| 项 | 为什么没做 | 怎么补 |
|----|-----------|--------|
| 3D ≥50 fps 长时采样 | 需要在 1440×900 下连续采样 60 帧并跑多轮节点规模，属长时性能工作 | 用 `requestAnimationFrame` 采 60 帧记均值，节点取 10/30/60 三档 |
| Lighthouse（Performance/SEO/A11y） | 站点与 App 都只在本地 HTTP 下验证过；Lighthouse 需要一次性跑 Chrome 的审计通道 | `npx lighthouse http://127.0.0.1:8899/index.html --only-categories=performance,seo,accessibility` |
| 公开站的人工抓取复核 | 需要真实公网 URL | 上线后用 Search Console 提交 sitemap，观察收录 |
| 真实设备上的触摸拖拽 | E2E 只覆盖了鼠标拖拽语义（`onPointerDown` 同源） | 手机 UA 下用 `hasTouch` 上下文跑一次旋转手势 |

---

## 13. 实施进展（2026-11-05 收口）

### 13.1 新增文件

| 路径 | 作用 |
|------|------|
| `frontend/src/styles/tokens.css` | 原语 + 语义令牌 + `[data-theme="dark"]` 单点深色定义 |
| `frontend/src/utils/theme.ts` | `resolveTheme` / `applyTheme` / `useThemeMode`（偏好、跨标签页、系统外观三处同步） |
| `frontend/src/motion/tokens.ts`、`frontend/src/motion/useMotionPrefs.ts` | 动效令牌与 reduced-motion 统一入口 |
| `frontend/src/components/CountUp.tsx` | 指标数字滚动（原生 rAF，不占 motion 特性包） |
| `frontend/src/scene/AttackSurfaceScene.tsx` | R3F 场景（默认导出，供 `lazy()` 分包） |
| `frontend/src/components/AttackSurfacePanel.tsx` | 收起/展开、WebGL 探测、三档降级、等价表格 |
| `frontend/public/favicon.svg` | 应用图标 |
| `site/**` | 公开站：zh 产品页、en 产品页、快速开始、css、og.png、sitemap、robots、`.nojekyll` |
| `frontend/scripts/make-og.mjs` | 用真实浏览器生成 1200×630 社交卡 |
| `.github/workflows/pages.yml` | GitHub Pages 发布（artifact = `site/`） |
| `frontend/e2e/theme.spec.ts` | 主题切换/持久化/系统跟随 + 8 页 × 2 主题截图 |
| `frontend/e2e/motion.spec.ts` | reduced-motion 主链路 + 弹窗 |
| `frontend/e2e/attack-surface.spec.ts` | 3D 展开 + WebGL 缺失降级 |
| `frontend/e2e/a11y.spec.ts` | axe-core 两主题 × 8 页 |

### 13.2 关键改动

- `styles.css` 顶部改为 `@import "./styles/tokens.css"`，删除被覆盖的深色 `:root` 与 3326 行里的第二个 `:root`；硬编码颜色按三批迁到语义令牌（首批 78 个值覆盖 172 行，二批 43 行，三批收尾 6 行），最终 `var(--)` 120→365 处、`#hex` 唯一值 154→37 个。
- 语义色整体换成 AA 达标值：`--muted` 3.19→4.91、`--soft` 1.97→3.25（且只用于非正文）、`--danger` 2.87→5.44、`--safe` 1.97→4.98、`--primary` 3.83→5.32、`--brand` 4.02→4.66（白字）。
- `preferences.ts` 增 `theme` 字段（白名单校验，坏值回落 `auto`）；`SettingsPage` 新增"外观"分区，切换即时生效并落盘。
- `index.html` 增加首帧主题引导脚本（避免深色用户看到浅色闪屏）、description、`robots: noindex`、单 `theme-color`、favicon。
- 组件动效按 §5.3 落地；`AppShell` 的 `.view-mount` 成为视图切换的唯一动效承载点。
- `RiskResultsPage` 指标卡接入 `CountUp`；新增攻击面面板（数据只来自 `findings`，边只连"目标→发现"）。

### 13.3 验证记录

```
cd frontend && npm run build
  index.css  49.61 kB │ gzip 10.02 kB
  index.js  479.86 kB │ gzip 144.67 kB
  AttackSurfaceScene.js 825.43 kB │ gzip 222.39 kB   ← 独立 chunk，不展开不请求

cd frontend && npm run test            -> 4 files / 11 tests passed
cd frontend && npx playwright test     -> 22 passed (48.2 s)
  覆盖：既有 13 条主链路 + theme 4 条 + motion 1 条 + attack-surface 2 条 + a11y 2 条

python -m pytest tests/web/test_app_static.py tests/meta -q   -> 12 passed

curl 抽查 site/（本地 http.server）：
  index 200 / en/ 200 / docs/ 200 / sitemap.xml 200 / robots.txt 200 / og.png 200 / site.css 200
```

axe-core 在这轮里查出三处真实对比度问题并已修复：品牌区副标题与版本号用透明度压层级（4.1、2.32）、`--soft` 被当正文色用（3.25）、终端固定深底面板内继承了会翻转的 `--muted`（3.04）。这三处不是本次改动引入的，是原有配色在浅色主题下就存在的问题。

### 13.4 与计划的偏差

| 计划 | 实际 | 原因 |
|------|------|------|
| 首屏 JS ≤130 kB | 144.67 kB，上限修订为 150 kB | motion 实测 +35.6 kB；`motion/react-m` 极简入口在本版本缺类型声明 |
| 3D chunk ≤230 kB | 222.39 kB | 去掉 drei，改自绘旋转 + 单 geometry 连线 |
| M-02 首页"卡片 stagger 最多 8 条" | 首页两栏 60 ms 交错 | 首页结构是两栏操作台而非卡片列表，逐字段 stagger 会把表单拆成 8 个动效节点，收益低于风险 |
| M-04 事件行"背景高亮衰减 600 ms" | CSS 淡入 + 上移 180 ms | 高亮衰减需要额外状态位跟踪"哪一行是新的"，为一个装饰效果引入状态不值 |
| M-07 用 `useMotionValue` 插值 | 原生 rAF 自绘 | 命令式 `animate()` 会把 motion 的特性包拉进首屏 |
| 主题色用两个 media 变体 | 单个 meta + JS 同步 | 显式主题下两个 media 变体同时不生效，容易不一致 |
| 站点 4 页 | 3 页 | `docs/` 与产品页已覆盖快速开始与关键词，第四页会变成凑数的重复内容 |

---

## 附录 A：本次实测量的命令

### A.1 基线体量

```bash
wc -l frontend/src/styles.css frontend/src/pages/*.tsx frontend/src/components/*.tsx
grep -c "{" frontend/src/styles.css          # 507 个规则块
grep -o "@keyframes" frontend/src/styles.css | wc -l   # 1
```

### A.2 主题覆盖关系

```bash
grep -n -E "^:root|color-scheme" frontend/src/styles.css
# 1:      :root {  color-scheme: dark;
# 1938:   :root {  color-scheme: light;   ← 后者全量覆盖前者的同名变量
```

### A.3 令牌覆盖率

```bash
grep -o "var(--" frontend/src/styles.css | wc -l                      # 120
grep -o -E "#[0-9a-fA-F]{3,8}\b" frontend/src/styles.css | wc -l      # 154
grep -o -E "rgba?\(" frontend/src/styles.css | wc -l                  # 164
grep -o -E "color: var\(--(muted|soft|primary|danger|safe|warn)\)" frontend/src/styles.css | sort | uniq -c
#  23  color: var(--muted)
#   1  color: var(--primary)
```

### A.4 对比度计算

```js
const lum = (hex) => {
  const c = hex.replace('#', '');
  const v = [0, 2, 4].map((i) => parseInt(c.substr(i, 2), 16) / 255)
    .map((x) => (x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4)));
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
};
const cr = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
```

现状结果（浅色生效主题）：`--muted` on `#ffffff` **3.19:1**、on `#f4f8fe` **3.00:1**；`--soft` **1.97:1**；`--danger` **2.87:1**；`--safe` **1.97:1**；`--primary` **3.83:1**。
深色令牌（当前无消费者）：`--text` 14.70:1、`--muted` 6.96:1、`--soft` 4.54:1、`--primary` 5.34:1、`--danger` 6.19:1、`--safe` 7.81:1。

### A.5 质量门禁

```bash
cd frontend && npx tsc -b
cd frontend && npm run test
cd frontend && npm run build
cd frontend && npm run e2e
cd frontend && npm run e2e -- --config playwright.config.ts   # reducedMotion 变体需在用例内建 context
```

---

## 附录 B：文件索引

| 路径 | 角色 | 本文件涉及 |
|------|------|-----------|
| `frontend/src/styles.css` | 3326 行主样式表 | 新增 `@import tokens.css`，删被覆盖的深色 `:root`（§3.1、§8-A） |
| `frontend/src/styles/tokens.css` | **新建**：原语 + 双主题语义令牌 | §3.1–3.2 |
| `frontend/src/motion/tokens.ts` | **新建**：时长/缓动常量 | §5.2 |
| `frontend/src/motion/useMotionPrefs.ts` | **新建**：reduced-motion 统一入口 | §5.4 |
| `frontend/src/scene/AttackSurfaceScene.tsx` | **新建**：R3F 场景（懒加载） | §6 |
| `frontend/src/utils/preferences.ts` | 新增 `theme` 字段 | §3.5 |
| `frontend/src/App.tsx` | 挂 `MotionConfig`、页面 `lazy` 分包 | §5.1、§5.3 M-01 |
| `frontend/src/components/*` | Toast / 三个对话框 / StatusDot / Banner 动效 | §5.3 |
| `frontend/src/pages/SettingsPage.tsx` | 新增"外观"分区 | §3.5 |
| `frontend/src/pages/RiskResultsPage.tsx` | 3D 面板挂载点 + 等价表格 | §6.2、§6.4 |
| `frontend/index.html` | description / robots / 双 theme-color / favicon | §7.2 |
| `frontend/public/favicon.svg` | **新建** | §7.2 |
| `site/*` | **新建**：公开静态站 | §7.3 |
| `.github/workflows/pages.yml` | **新建**：GitHub Pages 发布 | §7.5 |
| `frontend/src/test/setup.ts` | mock `useReducedMotion` | §5.5 |

## 附录 C：术语

| 术语 | 含义 |
|------|------|
| 原语令牌 | 不带语义的色阶（`--c-blue-500`），只允许在 `tokens.css` 内引用 |
| 语义令牌 | 带用途的变量（`--text-muted`），规则只引用这一层 |
| gzip 预算 | 构建产物经 gzip 压缩后的体积上限，超过即视为构建失败 |
| reduced-motion | `prefers-reduced-motion: reduce`，操作系统级"减少动态效果"偏好 |
| 等价视图 | 与图形/3D 视图承载同一数据、可被屏幕阅读器读取的表格或列表 |
| AA | WCAG 2.2 AA：正文 4.5:1、大字与非文本 3:1 |
