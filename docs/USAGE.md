# 剪辑辅助 Agent · 使用指南

> 面向第一次上手的用户。看懂这一页就知道：Agent 是什么、每个 Skill 能做什么、要准备什么素材、参数怎么传、产出怎么用。

## 1. 产品使用模型（先读这个）

**一句话：你给素材 + 一句自然语言指令 → Agent 选中 Skill 并执行 → 生成预览 → 你确认后才产出成片。**

```
素材（--media 视频 / --subtitle 字幕 / --bgm 音乐）
        +
自然语言指令（如"识别静音片段并裁剪"）
        ↓
① 意图解析 & 路由：匹配 Skill，生成执行计划（可多个 Skill 串行）
        ↓
② Skill 调度执行：素材识别 → 各 Skill 产出结构化结果
        ↓
③ 预览报告：report.md / report.html（不修改任何原素材）
        ↓
你的决策：[1] 应用 → 渲染成片 / [2] 修改参数重跑 / [3] 放弃
```

需要先澄清一个常见误解：

- **不是「导入资产 → Agent 自动批量处理」**。每次运行由**一条指令**触发，Agent 只执行这条指令命中的 Skill（可能是一条链）。
- **资产库不是导入的素材**，而是**可复用的参数预设**（调色预设、字幕模板、Skill 组合方案）。Skill 运行时可以从资产库取参数（目前 S005 调色支持 `--asset`）。
- 批量处理（一个模板套多个素材）是 V1.1 的「Skill 组合方案」方向，当前版本没有。

## 2. 快速上手（3 步）

```bash
pip install -e ".[dev]"                # 安装（仅 pytest，核心零第三方依赖）
python scripts/make_demo_fixture.py    # 生成演示素材 output/demo/

# 一次完整调用：静音裁剪
python -m clip_agent run "识别静音片段并裁剪" \
    --media output/demo/demo.mp4 --yes
```

跑完看 `output/run_*/report.html`（浏览器打开）或 `report.md`，成片在同一个目录。

不加 `--yes` 且终端可交互时，会停下来让你选 **[1] 应用 / [2] 修改参数重跑 / [3] 放弃**。

## 3. CLI 速查

```bash
python -m clip_agent run "指令" [参数]
```

| 参数 | 作用 | 示例 |
|---|---|---|
| `--media` | 视频/音频素材（多数 Skill 需要） | `--media 口播.mp4` |
| `--subtitle` | SRT 字幕文件（S002 需要） | `--subtitle demo.srt` |
| `--bgm` | BGM 音频（S004 需要） | `--bgm bgm.m4a` |
| `--asset` | 从资产库取预设（仅 S005） | `--asset color001` |
| `--set k=v` | 覆盖 Skill 参数，可重复 | `--set min_duration=1.5 --set top_n=3` |
| `--yes` | 非交互，直接采纳并渲染 | |
| `--no-render` | 采纳但不渲染成片（只要方案） | |
| `--workdir` | 自定义输出目录 | `--workdir out/test1` |

其他子命令：`skills`（清单/上下线）、`assets`（资产库）、`report`（评测报表，`--html` 生成仪表盘）。

## 4. Skill 总表

| ID | 做什么 | 需要的素材 | 产出 | 触发词示例 |
|---|---|---|---|---|
| S001 | 静音片段裁切 | 视频/音频（`--media`） | 静音时间段、保留片段、可渲染成片 | 静音、无声、去静音 |
| S002 | 字幕批量校对与样式统一 | SRT（`--subtitle`） | 修正后 SRT、问题清单、样式参数 | 字幕、错别字、校对 |
| S003 | 高光镜头识别筛选 | 视频（`--media`） | 高光片段列表（含评分） | 高光、精彩、名场面 |
| S004 | BGM 时长对齐 | BGM（`--bgm`），目标时长自动取 | 对齐方案、可渲染音频 | BGM、背景音乐、卡点 |
| S005 | 批量调色参数套用 | 视频（`--media`）+ 预设/参数 | 滤镜链、调色对比图、剪映参数映射、可渲染成片 | 调色、滤镜、预设、LUT |
| S006 | 语音转写生成字幕 | 视频/音频（`--media`） | 转写 SRT（S002 的上游） | 转写、语音识别、生成字幕 |

## 5. 每个 Skill 详解

### S001 静音片段裁切

- **输入**：`--media`（视频或音频）
- **参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `silence_threshold` | `-30` | 静音判定阈值（dB），越低越严格 |
| `min_duration` | `0.5` | 静音段最短时长（秒），短于此不处理 |
| `padding` | `0.1` | 裁切时静音段前后保留的余量（秒） |

- **示例**：

```bash
python -m clip_agent run "用-35dB阈值识别静音，超过1秒的裁掉" \
    --media 口播.mp4 --yes
# 等价于 --set silence_threshold=-35 --set min_duration=1.0
```

- **产出**：`silence_cut.json`（时间戳方案）、`cut_demo.mp4`（应用后渲染）
- **剪映里怎么用**：按报告里的「需要删除的静音段」时间戳手动裁；或直接用渲染成片。

### S002 字幕批量校对与样式统一

- **输入**：`--subtitle`（SRT）；也可以由 S006 转写结果自动接力
- **参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `max_line_chars` | `18` | 单行最大字数，超出自动折行 |
| `fix_overlap` | `true` | 修正时间轴重叠 |
| `dedupe` | `true` | 删除连续重复字幕 |
| `llm_polish` | `false` | 调用本地模型润色错别字（需 Ollama，失败自动降级） |
| `style` | 见下 | 统一样式参数 |

```json
{"font": "思源黑体 CN Medium", "font_size": 5, "color": "#FFFFFF", "stroke": 0.5, "position": "底部居中"}
```

- **示例**：

```bash
python -m clip_agent run "批量校对字幕错别字，统一样式" \
    --subtitle demo.srt --yes --set max_line_chars=16
```

- **产出**：`fixed.srt`（可直接导入剪映）
- **剪映里怎么用**：导入 SRT；样式按报告的参数在剪映「文本」面板批量设置。

### S003 高光镜头识别筛选

- **输入**：`--media`（视频）
- **参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `top_n` | `5` | 取评分最高的前 N 段 |
| `scene_threshold` | `0.3` | 镜头切变判定阈值（0~1，越大越不敏感） |
| `min_segment` | `1.0` | 过短镜头合并的最小时长（秒） |

- **示例**：

```bash
python -m clip_agent run "筛选高光镜头，取前3个" --media 素材.mp4 --yes
# 指令里的"前3个"会被解析为 top_n=3
```

- **产出**：`highlight_segments`（开始/结束/评分）
- **说明**：V1 为启发式（切变 + 响度）评分，V1.1 计划接入多模态精排。

### S004 BGM 时长对齐

- **输入**：`--bgm`；目标时长自动取上游 S003 的高光总长，没有则取 `--media` 时长
- **参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `fade_out` | `2.0` | 尾部淡出时长（秒） |
| `trim_start` | `0.0` | BGM 起始裁剪点（秒） |

- **示例**：

```bash
python -m clip_agent run "筛选高光镜头，匹配BGM卡点" \
    --media 素材.mp4 --bgm bgm.m4a --yes
```

- **产出**：`bgm_aligned.m4a`（循环/裁剪 + 淡出，可直接铺到剪映音轨）

### S005 批量调色参数套用

- **输入**：`--media`，参数二选一：`--asset 预设ID`（资产库）或 `--set brightness=0.1 ...`（内联）
- **参数**：

| 参数 | 默认 | 说明 | 安全范围 |
|---|---|---|---|
| `asset_id` | 空 | 资产库预设 ID（`assets list` 查看） | - |
| `brightness` | `0.0` | 亮度 | -1.0 ~ 1.0 |
| `contrast` | `1.0` | 对比度 | 0.5 ~ 2.0 |
| `saturation` | `1.0` | 饱和度 | 0.0 ~ 3.0 |
| `gamma` | `1.0` | 伽马 | 0.1 ~ 10.0 |
| `temperature` | `0.0` | 色温（负=冷，正=暖） | -1.0 ~ 1.0 |

- **示例**：

```bash
python -m clip_agent run "套用调色预设" --media 素材.mp4 --asset color001 --yes
python -m clip_agent run "调色，亮度-0.05对比度1.15" \
    --media 素材.mp4 --set brightness=-0.05 --set contrast=1.15 --yes
```

- **产出**：`compare.jpg`（一帧前后对比，预览阶段就生成）、`graded_demo.mp4`、剪映「调节」面板数值映射
- **剪映里怎么用**：按报告的亮度/对比度/饱和度/色温数值在「调节」面板设置。

### S006 语音转写生成字幕（可选依赖）

- **输入**：`--media`（视频/音频）
- **前置**：`pip install -e ".[asr]"`（Apple Silicon 装 mlx-whisper，其他平台装 faster-whisper；首次运行自动下载模型）
- **参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `asr_backend` | `auto` | `auto` / `mlx-whisper` / `faster-whisper` |
| `asr_model` | 空 | 空=后端默认（mlx: whisper-small-mlx；faster: small） |
| `language` | `zh` | 转写语言 |

- **示例**：

```bash
# 转写后自动接 S002 校对
python -m clip_agent run "先语音转写并校对字幕" --media 口播.mp4 --yes
```

- **产出**：`transcribed.srt`、`fixed.srt`
- **国内网络**：`export HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1`

## 6. 组合链（一句话命中多个 Skill）

规则路由按**触发词在指令中出现的位置**排序，形成串行执行链：

| 指令 | 执行链 | 中间结果如何传递 |
|---|---|---|
| `筛选高光镜头，匹配BGM卡点` | S003 → S004 | S003 的高光总长自动作为 S004 的对齐目标 |
| `先语音转写并校对字幕` | S006 → S002 | S006 的转写字幕自动作为 S002 的输入 |

单 Skill 失败即终止，已完成的结果保留在报告里。

### 组合模板（`--combo`，V1.1）

把固定链路存成资产库里的「组合方案」，一键执行，不用每次说指令：

```bash
python -m clip_agent assets list                            # 查看内置组合方案
python -m clip_agent run --combo combo003 --media 口播.mp4 --yes
```

内置组合：

| 资产 | 名称 | 链路 | 额外要求 |
|---|---|---|---|
| combo001 | 口播净化流水线 | S001 → S002 | 需要 `--subtitle` |
| combo002 | 高光卡点流水线 | S003 → S004 | 需要 `--bgm` |
| combo003 | 口播粗剪流水线 | S006 → S002 → S001 | 需要安装 `[asr]` |

自定义组合方案（`steps` 为 Skill ID 列表，每步参数放在 `step_params` 里）：

```bash
python -m clip_agent assets save 我的口播流程 --type skill_combo \
  --params '{"steps": ["S006", "S002"], "step_params": {"S006": {"language": "zh"}, "S002": {"max_line_chars": 16}}}'
```

组合方案里的参数仍可被命令行覆盖（`--set k=v`），`--asset`（调色预设）同样生效。

## 7. 创作资产库

资产 = 可复用的参数预设，不是素材文件。

```bash
python -m clip_agent assets list                          # 查看（内置 6 个）
python -m clip_agent assets save 我的夜景预设 \
    --type color_preset --params '{"brightness": -0.05, "contrast": 1.1}' --tags 夜景
python -m clip_agent assets favorite color001             # 收藏
python -m clip_agent assets rollback color001 1           # 回滚到 v1
```

- 类型：`color_preset`（调色）/ `subtitle_template`（字幕样式）/ `skill_combo`（Skill 组合方案）
- 同名保存会递增版本，可回滚
- 数据文件：`data/assets.json`（本地）

## 8. 输出目录结构

```
output/run_20261102_185807/
├── report.md / report.html   # 预览报告（同源双形态）
├── preview.json              # 机器可读的完整结果
├── compare.jpg               # 调色前后对比图（S005）
├── cut_demo.mp4              # 应用后渲染的成片
├── fixed.srt                 # 校对后字幕
├── bgm_aligned.m4a           # 对齐后的 BGM
├── transcribed.srt           # 转写字幕
└── silence_cut.json          # 静音时间戳方案
```

## 9. 常见问题

**Q：我的视频没有字幕，S002 能用吗？**
A：先跑 S006 转写（需要 `[asr]` 可选依赖），或用剪映「识别字幕」导出 SRT 后传给 `--subtitle`。

**Q：怎么知道某个 Skill 有哪些参数？**
A：`python -m clip_agent skills --json`；也可以在指令里直接说（如「用-35dB阈值」「取前3个」），规则路由会提取常用参数。

**Q：能一次处理很多条素材吗？**
A：当前版本一次指令处理一组素材。批量（模板 × 素材表）是 V1.1「Skill 组合方案」的方向。

**Q：需要联网/装模型吗？**
A：核心链路完全本地、零第三方依赖；LLM 润色（可选）和语音转写（可选）才会用到模型。

**Q：运行会不会改我的原素材？**
A：不会。所有产物写在 `output/run_*` 下，原素材只读。
