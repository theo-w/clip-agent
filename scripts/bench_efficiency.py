#!/usr/bin/env python3
"""效率基线（D2）：Agent 端到端耗时 vs 等价裸工具链耗时。

对同一条素材执行三个标准任务，各重复 N 次取中位数：
- S001 静音裁剪（检测 + 裁剪渲染）
- S006→S002 语音转写 + 字幕校对
- S005 调色预设 + 对比图（渲染 + 对比图）

Agent 侧走 CLI（含意图路由、预览报告、HTML、埋点）；
裸工具链侧直接调用同样的 ffmpeg / ASR 工具，不经过 Agent 层。
差值即 Agent 编排开销。

用法：
    .venv/bin/python scripts/bench_efficiency.py --media output/demo/speech_long.mp4 --runs 5
    # 已缓存 Whisper 模型时加 --offline，避免 HuggingFace 网络检查造成抖动
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path("/tmp/clip_agent_bench")

AGENT_TASKS = {
    "S001 静音裁剪": ["run", "识别静音片段并裁剪", "--yes"],
    "S006→S002 转写+校对": ["run", "先语音转写，再校对字幕", "--yes"],
    "S005 调色预设+对比图": ["run", "套用调色预设", "--asset", "color001", "--yes"],
}

_RAW_ASR = r'''
import sys
from pathlib import Path
from clip_agent.media import transcribe as asr
wd = Path(sys.argv[1]); wd.mkdir(parents=True, exist_ok=True)
segs, backend, model = asr.transcribe(sys.argv[2], wd)
(wd / "transcribed.srt").write_text(asr.segments_to_srt(segs), encoding="utf-8")
'''


def _median(values: list) -> float:
    return round(statistics.median(values), 3)


def _clean(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def bench_agent(media: str, runs: int, env: dict) -> dict:
    out = {}
    for name, args in AGENT_TASKS.items():
        walls, steps = [], []
        for i in range(runs):
            wd = TMP / "agent" / f"{name.split()[0]}_{i}"
            _clean(wd)
            t0 = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, "-m", "clip_agent", *args, "--media", media,
                 "--workdir", str(wd)],
                capture_output=True, text=True, env=env,
            )
            walls.append(round(time.perf_counter() - t0, 3))
            if proc.returncode != 0:
                raise SystemExit(f"Agent 任务失败：{name}\n{proc.stdout[-800:]}\n{proc.stderr[-800:]}")
            preview = json.loads((wd / "preview.json").read_text(encoding="utf-8"))
            steps.append(round(sum(r["duration"] for r in preview["results"]), 3))
        out[name] = {
            "wall": walls, "wall_median": _median(walls),
            "step_sum": steps, "step_median": _median(steps),
        }
    return out


def bench_raw(media: str, runs: int, env: dict) -> dict:
    from clip_agent.assets.library import AssetLibrary
    from clip_agent.media import analyzer
    from clip_agent.skills.s1_silence_cut import invert_to_keep
    from clip_agent.skills.s5_color_apply import build_filter_chain

    chain = build_filter_chain(AssetLibrary().get("color001").params)

    def raw_silence(i: int) -> None:
        wd = TMP / "raw" / f"silence_{i}"
        _clean(wd)
        total = analyzer.probe_duration(media)
        keep = invert_to_keep(total, analyzer.detect_silence(media, -30, 0.5), 0.1)
        expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep)
        analyzer.run_cmd([
            "ffmpeg", "-y", "-hide_banner", "-i", media,
            "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-af", f"aselect='{expr}',asetpts=N/SR/TB",
            "-c:a", "aac", "-b:a", "160k",
            "-t", f"{sum(e - s for s, e in keep):.3f}", str(wd / "cut.mp4"),
        ])

    def raw_color(i: int) -> None:
        wd = TMP / "raw" / f"color_{i}"
        _clean(wd)
        analyzer.run_cmd([
            "ffmpeg", "-y", "-hide_banner", "-i", media, "-vf", chain,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "copy", str(wd / "graded.mp4"),
        ])
        analyzer.run_cmd([
            "ffmpeg", "-y", "-hide_banner",
            "-ss", f"{analyzer.probe_duration(media) / 2:.2f}", "-i", media,
            "-frames:v", "1",
            "-vf", f"scale=640:-2,split[base][graded];[graded]{chain}[g];[base][g]hstack=inputs=2",
            "-q:v", "3", str(wd / "compare.jpg"),
        ])

    def raw_asr(i: int) -> None:
        wd = TMP / "raw" / f"asr_{i}"
        _clean(wd)
        proc = subprocess.run(
            [sys.executable, "-c", _RAW_ASR, str(wd), media],
            capture_output=True, text=True, env=env,
        )
        if proc.returncode != 0:
            raise SystemExit(f"裸 ASR 失败：{proc.stderr[-800:]}")

    out = {}
    for name, fn in [
        ("S001 裸工具链", raw_silence),
        ("S006 裸工具链", raw_asr),
        ("S005 裸工具链", raw_color),
    ]:
        vals = []
        for i in range(runs):
            t0 = time.perf_counter()
            fn(i)
            vals.append(round(time.perf_counter() - t0, 3))
        out[name] = {"wall": vals, "wall_median": _median(vals)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", default="output/demo/speech_long.mp4")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--offline", action="store_true",
                        help="设置 HF_HUB_OFFLINE=1（需已缓存模型），减少网络抖动")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    media = args.media
    if not Path(media).exists():
        print(f"素材不存在：{media}\n先运行：python scripts/make_speech_fixture.py --long")
        return 1
    if shutil.which("ffmpeg") is None:
        print("需要 ffmpeg")
        return 1

    env = dict(os.environ)
    if args.offline:
        env["HF_HUB_OFFLINE"] = "1"

    TMP.mkdir(parents=True, exist_ok=True)
    agent = bench_agent(media, args.runs, env)
    raw = bench_raw(media, args.runs, env)

    pairs = [
        ("S001 静音裁剪", "S001 裸工具链"),
        ("S006→S002 转写+校对", "S006 裸工具链"),
        ("S005 调色预设+对比图", "S005 裸工具链"),
    ]
    print(f"\n素材：{media}  重复：{args.runs} 次（中位数）\n")
    print("| 任务 | Agent 端到端 | 裸工具链 | 编排开销 |")
    print("|---|---|---|---|")
    total_agent = total_raw = 0.0
    for a, r in pairs:
        av, rv = agent[a]["wall_median"], raw[r]["wall_median"]
        total_agent += av
        total_raw += rv
        delta = av - rv
        print(f"| {a} | {av:.3f}s | {rv:.3f}s | {delta:+.3f}s（{delta / rv * 100:+.1f}%） |")
    delta = total_agent - total_raw
    print(f"| **合计** | **{total_agent:.3f}s** | **{total_raw:.3f}s** | "
          f"**{delta:+.3f}s（{delta / total_raw * 100:+.1f}%）** |")

    data = {"media": media, "runs": args.runs, "agent": agent, "raw": raw}
    if args.json:
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 已写入：{args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
