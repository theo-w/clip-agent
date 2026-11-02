#!/usr/bin/env bash
# 一键 MVP 演示：生成素材 → 4 条核心链路 → 评测报表
# 用法：bash scripts/run_demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY="python3"
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
fi

line() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }

line "0/5 生成演示素材"
"$PY" scripts/make_demo_fixture.py

line "1/5 S001 静音裁剪（预览 → 确认 → 渲染成片）"
"$PY" -m clip_agent run "识别静音片段并裁剪" --media output/demo/demo.mp4 --yes

line "2/5 S002 字幕批量校对（标点/折行/重叠/重复）"
"$PY" -m clip_agent run "批量校对字幕错别字，统一样式" --subtitle output/demo/demo.srt --yes

line "3/5 S003→S004 高光筛选 + BGM 卡点（多 Skill 串行编排）"
"$PY" -m clip_agent run "筛选高光镜头，匹配BGM卡点" --media output/demo/demo.mp4 --bgm output/demo/bgm.m4a --yes

line "4/5 S005 调色预设（资产库 + 一帧预览对比图）"
"$PY" -m clip_agent run "套用调色预设" --media output/demo/demo.mp4 --asset color001 --yes

line "5/5 评测报表（效率/质量/生态指标 + HTML 仪表盘）"
"$PY" -m clip_agent report --html

LATEST=$(ls -td output/run_* 2>/dev/null | head -1)
printf '\n\033[32m✓ 演示完成\033[0m\n'
printf '  最新预览报告：%s/report.md\n' "$LATEST"
printf '  HTML 预览：   %s/report.html\n' "$LATEST"
printf '  HTML 仪表盘： output/report.html\n'
printf '  调色对比图：  %s/compare.jpg（左：原片 ｜ 右：调色后）\n' "$LATEST"
printf '  其它成片：    output/run_*/cut_demo.mp4 / fixed.srt / bgm_aligned.m4a / graded_demo.mp4\n'
