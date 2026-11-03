# 15 分钟演示脚本（V1.1 + V1.2）

> 目标：让面试官看到「真实可跑 + 产品判断 + 人机边界 + 诚实边界」四件事。
> 结构：**3 分钟主线（必演）+ 12 分钟按兴趣加演**；任何一步翻车都不能影响演示。

## 演示前 5 分钟检查清单

```bash
cd /Users/wly/剪辑辅助agent
source .venv/bin/activate
python scripts/make_demo_fixture.py            # 重新生成基础素材（约 10s）
python scripts/make_speech_fixture.py --long   # 48s 中文口播（S006 真机演示用，macOS say）
# 可选：提前跑一遍以下命令，把 Whisper 模型缓存到本地（首次下载几百 MB，之后约 2s）
# HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 \
#   python -m clip_agent run "先语音转写并校对字幕" --media output/demo/speech_long.mp4 \
#   --set asr_model=mlx-community/whisper-large-v3-turbo --yes
# 可选：装剪映草稿依赖（演示 export-jianying 用）
# pip install -e ".[jianying]"
ls output/demo/                                 # demo.mp4 / demo.srt / bgm.m4a / speech_long.mp4
```

- [ ] 终端字号 16+，窗口清理干净（不留上次输出目录）
- [ ] `ffmpeg -version` 可用；**不依赖网络、不依赖 Ollama**（规则路由兜底是刻意设计）
- [ ] 兜底：`output/` 保留一份预生成的 `run_*` 目录与 `output/jianying_drafts/`，翻车直接打开讲
- [ ] 时间不够时只演主线（3 分钟），加演段按考官问题挑

## 一、3 分钟主线（必演）

| 时间 | 动作 | 说什么（要点，不是逐字稿） |
|---|---|---|
| 0:00–0:20 | 空终端，一句话开场 | "这是我为剪映生态做的 AI 剪辑辅助 Agent——不是全自动剪辑，是**可撤销的半自动**。规则明确的重复劳动交给 AI，判断权留给人。直接演示。" |
| 0:20–1:00 | 跑 S001：<br>`python -m clip_agent run "识别静音片段并裁剪" --media output/demo/demo.mp4 --yes` | 讲四段链路：**意图解析（规则路由）→ Skill 调度 → 预览快照 → 用户确认才渲染**。打开 `report.md`（时间戳表格）和 `cut_demo.mp4`（成片 4.64s，原片 6s）。补充：音频输入时输出 `cut_demo.m4a`——容器按流选择，避免跨 ffmpeg 版本时长漂移（CI 真 bug 修出来的） |
| 1:00–1:40 | 跑链式：<br>`python -m clip_agent run "筛选高光镜头，匹配BGM卡点" --media output/demo/demo.mp4 --bgm output/demo/bgm.m4a --yes` | 讲**多 Skill 串行编排**：一句话命中两个 Skill，S003 的高光总长自动成为 S004 的对齐目标（2.5s BGM 循环 3 次精确对齐 6s）；讲**失败即终止、保留已完成结果** |
| 1:40–2:30 | 真机 ASR：<br>`python -m clip_agent run "先语音转写并校对字幕" --media output/demo/speech_long.mp4 --set asr_model=mlx-community/whisper-large-v3-turbo --yes` | 讲**可选依赖本地推理**：S006 转写→S002 校对，48s 口播 5 段字幕；large-v3-turbo 缓存后约 2.19s，CER 5.52%（small 11.04%）。诚实讲边界：同音错字（Agent→Ajit）规则修不了，**领域热词/更大模型是下一步**，小模型数字也留着不藏。未装后端时明确提示安装、核心链路零影响 |
| 2:30–3:00 | 打开最新 `output/run_*/report.html`；跑 `python -m clip_agent report --html` 打开 `output/report.html` | 讲**双形态预览**：Markdown 给版本控制/机器读，HTML 给人看；纯静态零依赖、对比图 base64 内嵌、单文件可分享。收尾主题句：所有结果先预览、可改参重跑、可放弃——原素材零风险 |

## 二、12 分钟加演（按考官兴趣挑 2–4 段）

| 段 | 加演内容 | 命令 / 打开 | 讲点 |
|---|---|---|---|
| A 效率基线（2 min） | 同一素材 Agent vs 裸工具链 | `python scripts/bench_efficiency.py --runs 3` → 打开 `docs/evidence/2026-11-03-D2-efficiency.md` | 编排开销仅 +6.1%（5.383s vs 5.073s，机器执行时间）；操作单元从 27–29 个降到 3 条命令/1 条 combo。**明确说：这是机器执行和协议计数，不是真人手剪耗时，不能声称"快 X 倍"** |
| B 资产库与流通（2 min） | 资产导出/导入 + 广场 | `assets export color001 --out /tmp/x.clipasset` → `assets import /tmp/x.clipasset`；`assets discover --html` → `output/square.html` | 分享码内容哈希、导入校验 Skill 依赖、同码幂等；质量分 = 50%×去重素材复用 + 30%×收藏 + 20%×导入，复用按独立素材去重防刷；官方精选/社区热门/待验证 + 周复用资产数。在线广场/创作者主页需平台承载 |
| C 剪映草稿导出（3 min） | 把 run 变成剪映草稿 | `export-jianying output/run_* --dry-run` → `export-jianying output/run_* --out output/jianying_drafts`；`ls output/jianying_drafts/<草稿名>` | S001 保留片段→视频轨、S002 字幕按裁剪点重映射→字幕轨、S004 `bgm_aligned.m4a`→BGM 轨；调色只写参数映射 JSON，不碰剪映私有数据。**边界要说清：Mac/Linux 只生成草稿，需 Windows 版剪映打开导出**；本次只做到结构校验 + 库回读，Windows 开箱待验证 |
| D 组合模板（1 min） | 一句话跑完整流水线 | `python -m clip_agent run --combo combo003 --media output/demo/speech_long.mp4 --yes` | combo003 = S006→S002→S001（口播粗剪）；组合是资产、参数可覆盖。对应 JD「预设、Skill 沉淀和分发」 |
| E 复盘与缺口（2 min） | 打开 `docs/RETRO.md` | 第 6 章缺口 + 6.5 真机复盘 | 主动讲：0 真实用户、素材是 TTS 合成、A/B 无真人耗时、草稿未 Windows 开箱、高光仍是启发式；每项都有验证计划。**这比被追问强** |
| F 代码结构（2 min） | `clip_agent/` 目录 + `skills/` 注册机制 | `python -m clip_agent skills --json` | 新增 Skill 不改调度核心（约 30 行注册）；依赖只有标准库 + ffmpeg，Whisper/草稿是可选 extras |

## 三、必讲的 5 个点

1. **"所有 AI 结果先预览，用户确认才算数"**——主题句，开合各说一次；
2. **规则路由兜底**——没装本地模型也能跑，"降级路径是设计出来的"；
3. **失败即终止、保留已完成结果**——错误可归因，不级联；
4. **指标口径**——采纳率/二次修改率，防虚高（客服经验同源）；
5. **边界诚实**——核心零第三方依赖、第三方能力全部可选；剪映草稿能生成不能自动导出；ASR 有 CER 数字也有错字案例。

## 四、现场可能被要求的追加操作

| 考官说 | 你跑 | 讲什么 |
|---|---|---|
| "参数改一下再来一遍" | `... --set top_n=3 --yes` 或交互模式选 2 | 参数可覆盖、可重跑，这是"修改参数重跑"决策路径；输错参数名会提示可用参数清单 |
| "能加个新 Skill 吗" | 口头讲 `clip_agent/skills/` 注册机制（30 行） | 新增 Skill 不改调度核心——可扩展性是 JD 要的"Skill 建设" |
| "剪映里怎么用" | 打开 `report.md` 时间戳表；进阶跑 `export-jianying` | 手动定位裁剪 + SRT 直接导入 + 调节面板数值对照；V1.2 可直接生成草稿（Mac 生成→Windows 导出） |
| "有可视化界面吗" | 打开 `output/run_*/report.html`；总览跑 `report --html` | 双形态输出，纯静态零依赖可分享 |
| "没有字幕的素材怎么办" | `run "先语音转写并校对字幕" --media output/demo/speech_long.mp4 --yes` | ASR 可选依赖、本地推理；同音错字边界；未装后端的提示文案现场可演示 |
| "常用流程能一键跑吗" | `run --combo combo001 --media output/demo/demo.mp4 --subtitle output/demo/demo.srt --yes` | 组合方案资产化：固定链路沉淀成可执行组合、参数可覆盖 |
| "资产怎么分享给别人" | `assets export color001 --out x.clipasset` → `assets import x.clipasset` | 分享码内容哈希、导入校验依赖、同码幂等——"资产是参数不是代码，没有可执行内容，分享链路安全" |
| "资产多了怎么发现好用的" | `assets discover --html` 打开 `output/square.html` | 质量分口径、独立素材去重防刷、官方精选/社区热门/待验证、周复用资产数（生态北极星） |
| "模型在哪用" | `python -m clip_agent skills --json` | Skill 清单即模型路由的 prompt 输入（manifest） |

## 五、应急方案

- **ffmpeg 突然不可用**：不修，直接打开预生成的 `report.md` 和成片讲——"结果一样，只是不现场重跑"。
- **Whisper/网络不可用**：跳过 ASR，用 D1 证据文件（CER 数字 + SRT）讲；明确说"模型是可选依赖"。
- **export-jianying 依赖没装**：现场展示降级提示（`pip install -e ".[jianying]"`），打开预生成草稿目录讲结构——"没装的报错也是设计好的"。
- **命令打错**：重打一遍；"CLI 对失败有明确提示，这也是产品设计的一部分"。
- **时间被压到 1 分钟**：只跑 S001，然后用 `compare.jpg` 一张图讲资产库，收尾主题句。
- **被问"这是你自己写的吗"**：直说"我用 AI 辅助编码，但 SDD、产品取舍、指标口径和演示脚本都是我的产品决策；代码能跑，随时可以现场改。"
