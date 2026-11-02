# 3 分钟现场演示脚本

> 目标：让面试官在 3 分钟内看到「真实可跑 + 产品判断 + 人机边界」三件事。
> 原则：**每条命令都有备用路径；任何一步翻车都不能影响演示。**

## 演示前 5 分钟检查清单

```bash
cd /Users/wly/剪辑辅助agent
source .venv/bin/activate
python scripts/make_demo_fixture.py          # 重新生成素材（约 10s）
python scripts/make_speech_fixture.py         # 可选：生成中文口播素材（演示 S006 用，macOS）
# 若可能演示语音转写：提前跑一次下面命令，把 Whisper 模型缓存到本地（首次约 2 分钟）
# HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 python -m clip_agent run "先语音转写并校对字幕" --media output/demo/speech.mp4 --yes
ls output/demo/                              # 确认 demo.mp4 / demo.srt / bgm.m4a 存在
```

- [ ] 终端字号调到 16+，窗口清理干净（不留上次的输出目录）
- [ ] 确认 `ffmpeg -version` 可用（brew 已装）
- [ ] **不依赖网络、不依赖 Ollama**（规则路由兜底是刻意设计，这本身是讲点）
- [ ] 兜底：`output/` 里保留一份预生成的 `run_*` 报告，翻车时直接打开讲

## 脚本分镜

| 时间 | 动作 | 说什么（要点，不是逐字稿） |
|---|---|---|
| 0:00–0:20 | 空终端，一句话开场 | "这是我为剪映生态做的 AI 剪辑辅助 Agent——不是全自动剪辑，是**可撤销的半自动**。规则明确的重复劳动交给 AI，判断权留给人。直接演示。" |
| 0:20–1:05 | 跑 S001：<br>`python -m clip_agent run "识别静音片段并裁剪" --media output/demo/demo.mp4 --yes` | 讲四段链路：**意图解析（规则路由）→ Skill 调度 → 预览快照 → 用户确认才渲染**。指出输出目录里的 `report.md`（时间戳表格，可手动导入剪映）和 `cut_demo.mp4`（成片 4.64s，原片 6s）。 |
| 1:05–1:45 | 跑链式：<br>`python -m clip_agent run "筛选高光镜头，匹配BGM卡点" --media output/demo/demo.mp4 --bgm output/demo/bgm.m4a --yes` | 讲**多 Skill 串行编排**：一句话命中两个 Skill，S003 的高光总长自动成为 S004 的对齐目标（2.5s BGM 循环 3 次精确对齐 6s）；讲**失败即终止、保留已完成结果**。 |
| 1:45–2:15 | 跑调色：<br>`python -m clip_agent run "套用调色预设" --media output/demo/demo.mp4 --asset color001 --yes`<br>打开 `output/run_*/compare.jpg`（最新一次 run 目录） | 讲**创作资产库**：预设来自资产库（版本化）。讲**预览成本设计**：预览阶段只抽一帧生成左右对比图（成本 O(1) 帧，确认应用才渲染整片 O(n) 帧）。左原片帧/右调色后，输出剪映「调节」面板参数映射（亮度/对比度/色温数值）。呼应 JD"预设沉淀"。 |
| 2:15–2:45 | 字幕：<br>`python -m clip_agent run "批量校对字幕错别字，统一样式" --subtitle output/demo/demo.srt --yes`<br>打开 `output/run_*/fixed.srt` 对比 `demo.srt` | 讲 4 类问题自动修正：半角标点全角化、超长行折行、时间轴重叠修正、连续重复删除（4 条→3 条）。 |
| 2:45–3:00 | 收尾，指向 `docs/RETRO.md` | "所有结果先预览、可修改参数重跑、可放弃——原素材零风险。复盘文档里我写了已知缺口和验证计划，欢迎追问。" |

时间超了怎么办：**只演示 S001 + 调色对比**（最直观的两个），其余用 `report` 报表一页带过。

## 无论怎么压缩都不能丢的 4 个必讲点

1. **"所有 AI 结果先预览，用户确认才算数"**——主题句，开合各说一次；
2. **规则路由兜底**——没装本地模型也能跑，"降级路径是设计出来的"；
3. **失败即终止、保留已完成结果**——错误可归因，不级联；
4. **指标口径**——采纳率/二次修改率，防虚高（客服经验同源）。

## 现场可能被要求的追加操作

| 考官说 | 你跑 | 讲什么 |
|---|---|---|
| "参数改一下再来一遍" | `... --set top_n=3 --yes` 或交互模式选 2 | 参数可覆盖、可重跑，这是"修改参数重跑"决策路径；输错参数名会提示可用参数清单 |
| "能加个新 Skill 吗" | 口头讲 `clip_agent/skills/` 注册机制（30 行） | 新增 Skill 不改调度核心——可扩展性是 JD 要的"Skill 建设" |
| "剪映里怎么用" | 打开 `report.md` 时间戳表 | 手动定位裁剪 + SRT 直接导入 + 调节面板数值对照 |
| "有可视化界面吗" | 打开 `output/run_*/report.html`；需要总览时跑 `python -m clip_agent report --html` 打开 `output/report.html` | 讲输出双形态：Markdown 给版本控制/机器读，HTML 给人看；纯静态零依赖、对比图 base64 内嵌、单文件可分享 |
| "常用流程能一键跑吗" | `python -m clip_agent run --combo combo001 --media output/demo/demo.mp4 --subtitle output/demo/demo.srt --yes` | 讲组合方案资产化：把固定链路沉淀成可执行组合、参数可覆盖——直接对应 JD「预设、Skill 沉淀和分发」 |
| "没有字幕的素材怎么办" | `python -m clip_agent run "先语音转写并校对字幕" --media output/demo/speech.mp4 --yes` | 讲 ASR 是**可选依赖**、本地推理；未安装时明确提示安装方式、核心链路零影响。彩蛋：small 模型把"教"听成"叫"——规则校对修不了同音错字，这正是可选 LLM 润色的边界，也是"规则可解释、模型做增强"的分工 |
| "模型在哪用" | `python -m clip_agent skills --json` | Skill 清单即模型路由的 prompt 输入（manifest） |
| "资产怎么分享给别人" | `assets export color001 --out x.clipasset` → `assets import x.clipasset` | V1.1 流通：分享码内容哈希生成、导入校验 Skill 依赖、同码幂等判重——"资产是参数不是代码，没有可执行内容，分享链路安全"（呼应 JD"沉淀与分发"） |
| "资产多了怎么发现好用的" | `python -m clip_agent assets discover --html` 打开 `output/square.html` | P2 发现机制本地版：质量分 = 50%×去重素材复用 + 30%×收藏 + 20%×导入；复用按独立素材去重防刷；页面上有官方精选/社区热门/待验证三种来源标识与周复用资产数（生态北极星指标）。在线广场/创作者主页需平台承载，诚实标注为下一步 |

## 应急方案

- **ffmpeg 突然不可用**：不修，直接打开 `output/` 里预生成的 `report.md` 和成片讲——"结果一样，只是不现场重跑"。
- **命令打错**：不慌，重打一遍；"CLI 对失败有明确提示，这也是产品设计的一部分"。
- **时间被压到 1 分钟**：只跑 S001，然后用 compare.jpg 一张图讲完资产库，收尾点主题句。
- **被问"这是你自己写的吗"**：直说"我用 AI 辅助编码，但 SDD、产品取舍、指标口径和演示脚本都是我的产品决策；代码能跑，随时可以现场改。"（配合 Q&A 预演第 12 题）
