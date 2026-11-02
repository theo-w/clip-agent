# GitHub 竞品与可借鉴开源项目调研

> 调研日期：2026-11-02。star 数为当日 `gh api` 实测值，会随时间变化。
>
> 目的：① 为 V1.1 / V1.2 迭代找可直接借鉴的工程方案；② 为面试准备竞品事实依据——「这和 XX 开源项目有什么区别」必须答得上来。

## 1. 调研范围与结论速览

| 仓库 | star | 一句话 | 与我们的关系 |
|---|---|---|---|
| [GuanYixuan/pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft) | ~4.8k | Python 生成/导出剪映草稿，全能力覆盖 | **V1.2 对接剪映的核心候选适配器** |
| [FireRedTeam/FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline) | ~3.6k | 小红书开源的对话式 AI 剪辑 Agent，human-in-the-loop + Skill 归档 | **定位最接近的大厂项目，方向验证 + 差异化对照** |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | ~5.7k | CLI 按「第一遍粗剪」自动剪掉静音/无运动片段 | S001 的对标与参数设计参考 |
| [renezander030/capcut-cli](https://github.com/renezander030/capcut-cli) | ~1.1k | 零依赖 CLI 直读写剪映/CapCut 草稿，「任何 LLM Agent 可驱动」 | 草稿读写基础设施工具，**与我们是分层互补关系** |
| [YeJe-cpu/easy-jianying](https://github.com/YeJe-cpu/easy-jianying) | ~0.1k | 「AI 出剪映草稿，你在剪映里接着改」，记录了剪映 11.7 加密分水岭 | **人机边界叙事的最佳参照 + 11.7 事实来源** |
| [mrbuslov/capcut-ai-editor](https://github.com/mrbuslov/capcut-ai-editor) | ~0.1k | SmartCut MCP：读剪映自动字幕→剪静音/重复口播→直接改 CapCut 工程 | 复用剪映产物做分析 + MCP 形态参考 |
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | ~137k | 一键从主题生成高清短视频（全自动成片） | **对比定位**：我们刻意不做全自动 |
| [mli/autocut](https://github.com/mli/autocut) | ~7.8k | 用文本编辑器剪视频（whisper 字幕选句→裁剪），2024-10 后停更 | 「字幕即时间轴」范式鼻祖，代际参照 |
| [lagmoellertim/unsilence](https://github.com/lagmoellertim/unsilence) | ~0.6k | 移除媒体文件静音段 | S001 早期对标，一笔带过 |
| [Hommy-master/capcut-mate](https://github.com/Hommy-master/capcut-mate) | ~2.1k | FastAPI 版剪映草稿自动化 API + Coze 插件 + Skill | 生态 MCP 化/服务化趋势样本 |
| [fancyboi999/capcut-mcp](https://github.com/fancyboi999/capcut-mcp) 等 | <0.1k | 剪映/CapCut 的 MCP server 若干 | 同上，趋势佐证 |
| [RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT) | ~8.1k | AI 短视频自动化框架 | 同 MoneyPrinterTurbo，对比定位 |

**三条速览结论：**

1. **剪映草稿生态已经成型且活跃**：pyJianYingDraft（4.8k）、capcut-mate（2.1k）、capcut-cli（1.1k）等验证了「绕过官方 API、直读写草稿」这条路有真实需求；但 **剪映 11.7 收紧了草稿加密**，读取/修改已有草稿被限制，逆向路线存在系统性风险。
2. **「Agent + Skill 化剪辑」已被大厂开源验证**：小红书 OpenStoryline（3.6k，human-in-the-loop、可复用 Style Skill、对话式改稿）与我们 SDD 的核心设计（预览确认、Skill 归档、人机边界）同构——我们的方向判断有背书，差异化要靠「剪映生态 + 规则透明 + 本地零依赖」。
3. **「全自动成片」赛道极其拥挤**（MoneyPrinterTurbo 137k star），证明我们不做全自动、只做「已有素材工作流的标准化辅助」的定位是对的，且必须讲清楚为什么。

## 2. 重点产品分析

### 2.1 pyJianYingDraft — V1.2 对接剪映的核心候选

**[GuanYixuan/pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)** · ~4.8k star / 718 fork · Python · 活跃（更新到 2026-11）· pip 可装 · CapCut 版本（pyCapCut）在开发中

用 Python 直接生成剪映草稿文件（`draft_content.json`）并驱动剪映导出，定位「构建全自动视频剪辑/混剪流水线」。能力覆盖面（README 功能矩阵）：

- **视频/图片**：素材时间控制、整体调节（调色）、关键帧、蒙版、色度抠图、背景填充、混合模式；**贴纸**：含关键帧
- **音频**：淡入淡出、音量、片段特效、场景音/音色
- **轨道**：多轨道、顺序控制
- **特效/滤镜/转场/片段动画**：全支持
- **文本**：样式/字体/描边/背景/阴影/气泡/花字/关键帧/自动换行、**导入 .srt 字幕**（与我们的 S002 输出天然衔接）
- **模板模式**：加载已有草稿为模板 → 按名称替换音视频素材 / 替换文本内容 / 整轨导入 → **批量出片**（这正是我们 V1.1「Skill 组合方案」落地成草稿的现成路径）
- **批量导出**：控制剪映打开指定草稿并导出——但依赖旧版可见控件，**剪映 7+ 自动导出失效**

**关键工程事实（V1.2 必须纳入风险设计）**：

1. 新版剪映的 `draft_content.json` **往往不是可直接读取的明文 JSON**，模板加载需要 `fallback_loader` 接入额外读取器；
2. 自动导出依赖 UI 自动化，**仅剪映 6.8 及以下可用**，新版不支持；
3. 跨平台限制：草稿生成/模板模式全平台可用，**生成的草稿仍需 Windows 版剪映导出**（Mac/Linux 不能自动导出）。

**对我们的意义**：它把「剪映草稿格式」这一层封装好了。我们 V1.2 完全不必自己逆向草稿格式——把 Skill 的输出（时间戳方案、SRT、调色参数）翻译成草稿对象即可，pyJianYingDraft/capcut-cli 是现成的「输出适配器」。

### 2.2 FireRed-OpenStoryline — 定位最接近的大厂项目

**[FireRedTeam/FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline)** · ~3.6k star / 421 fork · Python ≥3.11 · Apache-2.0 · **小红书 Super Intelligence 部门基础算法实验室**出品 · 2026-02 开源，迭代快（2026-03/04 连发新功能）

「把复杂视频创作变成自然对话」：自然语言交互 + LLM 任务规划 + 工具编排，主打 **intention-driven directing（意图驱动）**、**transparent human-in-the-loop**、**可复用 Style Skill**。功能栈：联网素材检索与下载、脚本生成（few-shot 风格迁移：用参考文本复刻文风）、BGM/配音/字体智能推荐（**含智能卡点**）、对话式精修（剪/换/重排、改色/字/描边/位置）、**Editing Skill Archiving：把整套剪辑工作流存成自定义 Skill，换素材套用即可复刻风格批量创作**。

值得记录的细节：

- **2026-03-22 新增「ASR 粗剪 Skill」**：自动去口癖、气声、结巴、重复语句，带时间戳对齐——和我们 S001+S002 组合的场景完全一致，说明「口播粗剪」是高频刚需；
- **2026-04-02 AI 转场生成**：README 明确标注依赖第三方 AIGC 服务、**成本高、结果不可控，建议按需开启**——大厂也在给「AI 全自动生成」做预期管理，与我们第 6 节「预期管理」原则互证；
- **Agent 原生**：内置 Claude Code Skills（`/openstoryline-install`、`/openstoryline-use`）+ OpenClaw Skills——「剪辑工具打包成 Agent Skill」已经是行业标准动作；
- 演示素材库关联小红书 App「AI 剪辑」资产库，说明它服务的是站内生态。

**与我们的区别**：OpenStoryline 覆盖「从主题到成片」的**创作生成**端（联网找素材、写脚本、生成成片）；我们做的是创作者**已有素材工作流的中段标准化操作**（静音/字幕/高光/BGM/调色），且规则透明、本地零依赖、每一步可解释。它验证了 human-in-the-loop + Skill 归档的产品方向，我们与它是工作流位置不同、能力侧重不同。

### 2.3 auto-editor — S001 的对标与设计参考

**[WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor)** · ~5.7k star · Nim · 持续活跃 · 自称「first pass（第一遍粗剪）」工具

CLI 按 loudness 等方法自动剪掉「dead space」。设计上有四点值得抄：

1. **可组合的编辑条件 DSL**：`--edit "(or audio:0.03 motion:0.06)"`——布尔组合多信号（音频/运动），threshold 永远是第一个参数，支持 `dB` 单位（对视频编辑者友好）；
2. **label/action 分离**：每个时间片段打标签（0=静音默认剪、1=活动默认留），`--edit:2`+`--when:2 speed:1.5` 可以「不是删掉静音，而是把大声段加速」——**「剪/留/变速」是三种动作而不只是二选一**；
3. **`--margin 0.2s` 呼吸感参数**：裁剪前后留 0.2s 缓冲，让剪辑不「喘不过气」——S001 应补的默认参数；
4. **导出到剪辑软件而非渲染成片**：`--export premiere` 生成可导入 Premiere 的 XML 时间轴，也支持 Final Cut 等格式——**把裁剪决策输出为「编辑器可导入的时间轴交换格式」**，这与我们「不覆盖原工程、用户可继续编辑」的理念完全一致，比渲染成片更符合人机边界。反向模式（`--when-active cut`）可导出「被剪掉的部分」供审核。

另有 `npx skills add WyattBlue/auto-editor` 的 Agent Skill 打包。

### 2.4 capcut-cli — 草稿读写的基础设施层

**[renezander030/capcut-cli](https://github.com/renezander030/capcut-cli)** · ~1.1k star · JavaScript/Node ≥18（零原生依赖）· 更新到 2026-11 · npm/pip 双发布

「任何 LLM Agent 可驱动的剪映/CapCut CLI」：JSON-in/JSON-out 直读写本地草稿库，无 MCP server、无 HTTP daemon；新版 CapCut 上会探测并同步所有可读的时间轴目标，不假设 `draft_content.json` 是唯一真源。产品哲学与我们的预览-确认理念同源：**输出「打开后每条轨道仍可编辑的真草稿，不是压平的成片」，publish 那一下永远留给人**。

值得记录的做法：

- **确定性边界**：给 LLM 的不是模糊的自然语言 API，而是确定性的 JSON 命令——agent 生态里「确定性工具 + LLM 规划」的分层思路；
- **四种交付形态**：CLI / 库（`loadDraft/lintDraft/saveDraft`）/ 队列执行器（stdin 读 JSONL，接 n8n/Make/Coze）/ 只读 Wasm sandbox（给 AI「看而不动」的审查模式，无文件系统/网络/环境变量访问）；
- **Agent Skill 打包**：`npx skills add renezander030/capcut-cli` 一条命令把 `capcut-edit` skill 装进 Claude Code/Codex/Cursor，skill 里教 agent「先 inspect、绝不整体 dump 草稿」的渐进披露习惯；也上了 Claude Code plugin marketplace；
- **隐私姿态**：全本地，唯一上云是 opt-in 的 `caption --cloud`（把音频传给字节做转写）；
- **安全自律**：老版本有命令注入等漏洞，公开披露 + 修复 + changelog——CLI 工具处理用户素材的安全底线；
- 命令含 `doctor`（环境自检）、`quickstart`、`info`；能力：静音感知裁剪、样式化字幕、长视频切 shorts、translate（接 Anthropic API）、render（ffmpeg）。

**与我们的关系**：它做「草稿读写基础设施」，我们做其上的「意图路由 + Skill 编排 + 资产沉淀 + 评测」产品层。V1.2 对接剪映时它是适配器候选之一；面试时这是「分层互补、不重复造轮子」的现成论据。

### 2.5 easy-jianying — 人机边界叙事的最佳参照 + 11.7 分水岭

**[YeJe-cpu/easy-jianying](https://github.com/YeJe-cpu/easy-jianying)** · ~91 star（star 少但叙事质量极高，更新到 2026-11）

「让 AI 把剪辑做成剪映草稿，你在剪映里接着改」：AI 写剪辑计划（JSON）→ 生成剪映草稿 → 人在剪映里微调导出。README 开篇的对比表直接回答了「为什么是草稿不是成片」：

| 想改一个错别字 | 拿到成片 | 拿到剪映草稿 |
|---|---|---|
| 怎么改 | 让 AI 重新生成、重新渲染 | 在剪映里双击字幕改掉 |
| 要等多久 | 再渲染一遍 | 几秒钟 |
| 算力 | 再花一次 | 不用 |

这张表就是我们「预览-确认-可改」人机边界的最佳表述，可直接化用到我们的 DEMO 脚本和面试话术里。

**关键事实「剪映 11.7 分水岭」**：剪映草稿是加密的，社区旧做法不是破解，而是调用剪映程序自带的加解密功能；**11.7 起密钥只在剪映运行时提供，外部调用只拿到空结果——剪映有意收紧**。该项目的应对：**写一份不加密的草稿交给剪映，剪映打开后自己加密保存**（实测 11.7 可正常打开/播放/导出）。版本兼容表：5.x 及以前读写皆可（大量老开源项目停在这一代）；6.0–11.6 双向自动加解密；**11.7+ 只能生成新草稿，读改已有草稿受限**。

其他可抄细节：口播粗剪（剪气口/口癖/结巴/重来的半句 + 语义去重）、字幕本地识别不上传、卡点（识别节拍 + 打上**剪映原生踩点标记**）、批量（一个模板 × 一张表格 = N 个草稿）、以及**「剪映升级自适配」**——把版本适配当独立子问题维护，一条命令重新学习新版草稿格式。

### 2.6 capcut-ai-editor（SmartCut MCP）— 复用剪映产物做分析

**[mrbuslov/capcut-ai-editor](https://github.com/mrbuslov/capcut-ai-editor)** · ~123 star · Python · MCP server

面向 talking-head 视频的工作流：录视频 → 导入 CapCut → 用 CapCut 自动生成字幕 → 关闭 CapCut → 对 Claude 说「Smart cut 我的工程」→ 重开 CapCut 审查裁剪。分析逻辑：**直接读剪映自己生成的字幕**来定位语音，字幕间隔 >1s 判静音剪掉；检测到重复口播（重录的那句）保留最后一个版本。启发式本地运行、无需 API key，OpenAI key 可选用于重复检测增强。

两个可抄思路：① **把宿主软件已生成的产物（自动字幕）当作分析数据源**，避免重复跑 ASR——我们对接剪映后同样可以用「识别字幕」的输出来做静音/重复检测；② 「关闭宿主→改文件→重开审查」的并发安全工作流约定。

### 2.7 MoneyPrinterTurbo / ShortGPT — 对比定位：全自动成片赛道

- **[harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)** · **~137k star**（本轮调研 star 最高）：AI 大模型 + 自动化工作流，从主题/关键词**一键生成**高清短视频（文案→素材→TTS→字幕→合成，全自动）。
- **[RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT)** · ~8.1k star：YouTube shorts/TikTok 频道自动化的实验性 AI 框架。

**对我们的意义**：这类项目解决的是「从 0 到 1、没有素材的营销号批量生产」场景，star 数证明需求巨大，但也意味着该赛道已经红海。我们 SDD 第 6 节的取舍（主观创意不做全自动、AI 结果必预览）对应的正是另一个场景：**创作者已有素材、要的是精修迭代效率**。两者不冲突，但面试必须能主动讲清这个分野，否则会被归类为「又一个自动成片工具」。

### 2.8 代际参照：autocut 与 unsilence

- **[mli/autocut](https://github.com/mli/autocut)** · ~7.8k star · 2024-10 后停更：whisper 生成字幕 → 在文本文件里选保留句子 → 对应片段裁剪，「用文本编辑器剪视频」。开创了「字幕即时间轴」范式，但停更说明单点工具生命周期有限，需向工作流/生态演进。
- **[lagmoellertim/unsilence](https://github.com/lagmoellertim/unsilence)** · ~0.6k star：移除静音段的早期工具，被 auto-editor 的多信号+label 体系全面超越。

### 2.9 剪映生态的 Agent 化/MCP 化趋势（一笔带过）

| 项目 | star | 形态 |
|---|---|---|
| [Hommy-master/capcut-mate](https://github.com/Hommy-master/capcut-mate) | ~2.1k | FastAPI 草稿自动化 API，配 Coze 插件 + 配套 Skill 仓库（capcut-mate-skill） |
| [fancyboi999/capcut-mcp](https://github.com/fancyboi999/capcut-mcp) | ~96 | 剪映 MCP server，供 LLM 调用 |
| [Atx-Guy/capcut-mcp-server](https://github.com/Atx-Guy/capcut-mcp-server) | ~87 | Claude 读写 CapCut 桌面草稿的 MCP server |
| [JianYing-Automation/JianYingApi](https://github.com/JianYing-Automation/JianYingApi) | ~0.26k | 第三方剪映 API |
| [notinmood/JianyingDraft.PY](https://github.com/notinmood/JianyingDraft.PY) | ~0.21k | C# 剪映草稿库 |
| [MeiGen-AI/X-Cut](https://github.com/MeiGen-AI/X-Cut) | ~34 | 对话驱动 + 实时渲染的剪辑 agent（早期） |

**趋势结论**：官方 2026-04 上线 Skill 化 AI 助手、2026-09 专业版支持自定义 Skills 之后，第三方工具在半年内密集跟进 MCP/server 化和 Agent Skill 打包。**「剪辑能力以 Skill/MCP 形态对 LLM 开放」已是剪映生态的既成事实**——我们项目的 Skill 架构方向与生态演进一致。

### 2.10 补充线索：LeMontage 与 ai-video-editing-skill（2026-11-02 实测）

- **[FleoThing/LeMontage](https://github.com/FleoThing/LeMontage)** · **~3 star**（体量很小，仅作理念参照）：pipeline-first——AI Agent 只负责写 YAML 管线，LeMontage 本地渲染、自身从不调用模型。思路与我们的「确定性 CLI + 规则兜底」同源：**把生成交给模型、把执行交给确定性工具**。但其 star 量级说明它还不是工程化标杆，不宜作为「对标」对象引用。
- **[znyupup/ai-video-editing-skill](https://github.com/znyupup/ai-video-editing-skill)** · **~169 star**：面向 Claude Code 等 Agent 的自动 vlog 剪辑 Skill，feed 原始素材直接出片，技术栈 **ffmpeg + Whisper + Vision API**。可作为「ASR 转写 + 画面理解」组合能力的产品形态参考；但它走全自动出片路线，与我们的预览确认定位相反，借鉴点只在能力组合，不在交互哲学。

## 3. 对我们项目的具体借鉴建议

### 3.1 可直接借鉴的工程方案

| # | 借鉴点 | 来源 | 落到哪 |
|---|---|---|---|
| E1 | **时间轴交换格式输出**：静音/高光裁剪不只输出时间戳报告，增加「剪映可导入格式」的输出选项（pyJianYingDraft 草稿，或 Premiere XML 思路） | auto-editor `--export` / pyJianYingDraft | **V1.2 首位**：S001/S003 的输出适配器，用户「导入即得可继续编辑的轨道」，渲染成片只是可选项 |
| E2 | **基于 pyJianYingDraft/capcut-cli 做草稿适配层，不自研草稿格式**；采用「写不加密草稿→剪映自己加密保存」策略（11.7 实测可行），并像 easy-jianying 那样把「剪映版本适配」独立成子问题维护 | pyJianYingDraft / capcut-cli / easy-jianying | V1.2 架构设计：Skill 输出 → 草稿翻译层 → pyJianYingDraft 适配器 |
| E3 | **模板模式批量出片**：读模板草稿按名称替换素材/文本 = 我们「Skill 组合方案资产」的最短落地路径（方案 JSON → 草稿） | pyJianYingDraft 模板模式 | V1.1：组合方案资产支持一键生成剪映草稿 |
| E4 | **label/action 剪辑动作模型**：静音段动作支持「删/留/变速」三态（非删即留二态）；加 `margin` 呼吸感参数；dB 单位 | auto-editor | V1.1：S001 参数升级（`--margin` 应成为默认 0.2s 左右的经验值） |
| E5 | **复用剪映已生成产物做分析**：对接后直接读剪映「识别字幕」输出定位静音/重复，省一次 ASR | capcut-ai-editor | V1.2：S001/S002 的数据源策略 |
| E6 | **确定性 CLI + Agent Skill 打包**：`npx skills add` 式一键分发、`doctor` 自检命令、渐进披露的使用习惯写入 skill 说明 | capcut-cli / auto-editor | V1.1：把 `clip-agent` 打包成 Claude Code/Codex 可安装的 Skill，README 加安装一条命令 |
| E7 | **「口播粗剪」组合 Skill**：ASR 转写 + 去口癖/气口/重复/结巴 + 时间戳对齐——两个竞品（OpenStoryline、easy-jianying）都独立做了它，说明是高频刚需；znyupup 的 ffmpeg+Whisper+Vision 组合印证了「ASR + 画面理解」是标准能力栈 | OpenStoryline ASR 粗剪 / easy-jianying 口播粗剪 / znyupup | **V1.1 新增组合模板**（现 S001+S002 的场景化封装），Whisper 作为可选依赖、缺失时降级 |

### 3.2 可借鉴的交互设计

1. **「改一个错别字」对比表**（easy-jianying）：成片 vs 草稿的修改成本对比，直接化用进我们的 README/DEMO/面试话术——这是「预览-确认」价值的最强表述；
2. **`doctor` 自检命令**（capcut-cli）：ffmpeg/ffprobe/模型可用性一次检查，降低首跑失败率——适合加进我们 CLI；
3. **反向导出被剪内容**（auto-editor）：预览报告里附「被剪掉片段」清单，让用户能审计 AI 的裁剪决策，强化信任；
4. **预期管理的措辞**（OpenStoryline）：对高成本/不可控功能标注「成本较高、结果有随机性，建议按需开启」——大厂开源项目的预期管理范本，值得写进我们的 README。

### 3.3 必须差异化的定位点

1. **工作流位置**：全自动成片（MoneyPrinterTurbo/ShortGPT）解决「无素材、从 0 到 1」；OpenStoryline 覆盖「主题→素材→脚本→成片」的创作生成端。我们固定在「**创作者已有素材、剪辑中段的标准化操作**」——静音、字幕、高光、BGM、调色这五件事，不做叙事、不做创意转场。
2. **规则透明 + 零依赖**：生态里所有项目都绑模型/API（OpenStoryline 要 LLM+素材库，capcut-mate 要 FastAPI 部署）；我们规则路由兜底、纯本地可跑、每一步可解释——对接面（本地模型可选）保持但产品默认零门槛。
3. **资产沉淀 + 评测指标**：没有一家把「Skill 调用链路埋点、采纳/修改/放弃率、资产复用率」做进产品（OpenStoryline 的 Skill 归档最接近但没有评测体系）——这是我们从工具走向「生态设计」的差异点，也是 JD 职责③（创作知识沉淀与分发）的直接对应。
4. **与基础设施层的关系**：pyJianYingDraft/capcut-cli 是能力层，我们是产品层——**不重复造轮子，而是做它们的编排者**。面试讲成「我调研了生态，把草稿读写委托给成熟库，自己聚焦意图路由/Skill 设计/资产/评测」。

## 4. 面试叙事弹药

**Q1：「pyJianYingDraft / capcut-cli 已经能操作剪映草稿了，你的项目还有什么价值？」**

> 它们是**能力层基础设施**：解决「Python/CLI 怎么读写草稿」。我的项目是**产品层**：用户说一句「筛选高光镜头，匹配 BGM 卡点」，我来做意图解析、多 Skill 编排、失败策略、预览确认、行为埋点和资产沉淀——这层它们都没有。关系上我恰恰依赖它们：V1.2 对接剪映时，pyJianYingDraft 就是我的输出适配器候选，我的调研（可展开讲 11.7 加密分水岭、自动导出对剪映 7+ 失效等事实）决定了「不自研草稿格式、委托成熟库」的架构决策。分层而不重复造轮子，本身就是这个岗位要的生态设计判断。

**Q2：「剪映 11.7 把草稿加密收紧了，你的对接路线还成立吗？」**

> 成立，而且是刻意留了三条腿：① 当前 V1.0 的输出全是**标准格式**（SRT、时间戳报告、参数映射），不依赖剪映任何私有格式，官方怎么改都不受影响；② 草稿生成路线技术上仍可行——easy-jianying 实测「写不加密草稿、剪映打开后自己加密保存」在 11.7 上工作，只是「读改已有草稿」受限，所以 V1.2 设计成「生成新草稿」而非「改用户工程」，还把版本适配独立成子问题；③ 官方 2026-04 上线 Skill 化 AI 助手、2026-09 专业版开放自定义 Skills——**官方开放是趋势，我的 Skill 设计（原子化、参数化、可编排）本来就是按能接进官方 Skill 生态的规格做的**。逆向路线被收紧这件事，反而是我做「输出格式标准化」这个取舍的依据。

**Q3：「MoneyPrinterTurbo 十几万 star，全自动成片才是方向吧？」**

> star 数说明的是「营销号批量生产」这个场景的需求规模，不是方向唯一性。真实创作者的工作流是**已有素材、精修迭代**——改一个错别字，全自动工具要重新生成重新渲染，草稿方案双击就改完了（easy-jianying 的对比表）。而且大厂自己的判断也站在辅助一侧：小红书开源的 OpenStoryline 明确做 human-in-the-loop，连 AI 转场这种全自动功能都标注「成本高、结果不可控、建议按需开启」。我的 SDD 第 6 节把「主观创意不做全自动、AI 结果必预览」写成硬边界，调研下来这是与行业头部产品一致的设计判断，不是保守。

---

*本文件为调研草稿，star 数为 2026-11-02 实测值；引用仓库功能以其当日 README 为准。*
