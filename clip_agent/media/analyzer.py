"""素材识别模块（SDD 模块 3）：基于 ffmpeg/ffprobe 的音视频结构化分析。

输出结构化标签与时间戳片段，供各 Skill 消费：
- 音频静音检测（silencedetect）
- 镜头切变检测（select=gt(scene,X) + showinfo）
- 响度时间线（ebur128，供高光评分）
- 字幕解析（SRT）

ffmpeg 不可用时抛 MediaToolError，Skill 层转为用户可读的失败原因。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MediaToolError(RuntimeError):
    """ffmpeg/ffprobe 不可用或执行失败。"""


def _require_tools() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise MediaToolError(
            "未检测到 ffmpeg/ffprobe，请先安装（macOS: brew install ffmpeg）"
        )


def run_cmd(cmd: list, progress_total: float = None, on_progress=None) -> subprocess.CompletedProcess:
    """执行外部命令，失败抛 MediaToolError（含 stderr 尾部信息）。

    ffmpeg 命令传入 progress_total（输出总时长，秒）与 on_progress 回调时，
    附加 -progress pipe:1 流式回报进度，on_progress 收到 0~1 的比例值。
    """
    _require_tools()
    if on_progress is not None and progress_total and progress_total > 0 \
            and "ffmpeg" in cmd:
        full_cmd = [cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]]
        proc = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for line in proc.stdout:
            if line.startswith("out_time="):
                seconds = _parse_out_time(line.split("=", 1)[1].strip())
                if seconds is not None:
                    on_progress(min(seconds / progress_total, 1.0))
            elif line.startswith("progress=end"):
                on_progress(1.0)
        proc.wait()
        if proc.returncode != 0:
            raise MediaToolError(
                f"命令执行失败：{' '.join(str(c) for c in full_cmd[:4])}…"
                f"\n{proc.stderr.read()[-1500:]}"
            )
        return subprocess.CompletedProcess(full_cmd, proc.returncode)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaToolError(
            f"命令执行失败：{' '.join(str(c) for c in cmd[:4])}…\n{proc.stderr[-1500:]}"
        )
    return proc


def _parse_out_time(token: str):
    """解析 ffmpeg -progress 的 out_time 行（如 "00:00:03.456000"）；无法解析返回 None。"""
    m = re.fullmatch(r"(\d+):(\d+):(\d+(?:\.\d+)?)", token)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def probe_duration(path: str) -> float:
    """媒体总时长（秒）。"""
    proc = run_cmd([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", path,
    ])
    return float(proc.stdout.strip())


def has_audio(path: str) -> bool:
    """是否包含音频轨。"""
    proc = run_cmd([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", path,
    ])
    return bool(proc.stdout.strip())


@dataclass
class SilenceSegment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def detect_silence(path: str, threshold_db: float = -30,
                   min_duration: float = 0.5) -> list:
    """检测音频中低于 threshold_db 且持续超过 min_duration 的静音段。"""
    proc = run_cmd([
        "ffmpeg", "-hide_banner", "-nostats", "-vn",
        "-i", path,
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-",
    ])
    starts = []
    segments = []
    for line in proc.stderr.splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            starts.append(float(m.group(1)))
            continue
        m = re.search(r"silence_end:\s*(-?[\d.]+)", line)
        if m and starts:
            segments.append(
                SilenceSegment(start=starts.pop(0), end=float(m.group(1)))
            )
    # 音频结尾处的静音可能只有 silence_start，用总时长封口
    if starts:
        total = probe_duration(path)
        for start in starts:
            if total - start >= min_duration:
                segments.append(SilenceSegment(start=start, end=total))
    return segments


def detect_scene_changes(path: str, threshold: float = 0.3) -> list:
    """镜头切变时间点（scene score 超过 threshold 的帧时间戳）。"""
    proc = run_cmd([
        "ffmpeg", "-hide_banner", "-nostats", "-an",
        "-i", path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ])
    times = []
    for line in proc.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            times.append(float(m.group(1)))
    return times


def loudness_timeline(path: str) -> list:
    """(时间点, 瞬时响度 M) 序列，约每 100ms 一个采样点；-inf 记为 -70。"""
    proc = run_cmd([
        "ffmpeg", "-hide_banner", "-nostats", "-vn",
        "-i", path,
        "-filter_complex", "ebur128",
        "-f", "null", "-",
    ])
    timeline = []
    for line in proc.stderr.splitlines():
        m_t = re.search(r"\bt:\s*(-?[\d.]+)", line)
        m_m = re.search(r"\bM:\s*(-?[\d.]+|-inf)", line)
        if m_t and m_m:
            raw = m_m.group(1)
            timeline.append((float(m_t.group(1)), -70.0 if raw == "-inf" else float(raw)))
    return timeline


# ---------------------------------------------------------------- SRT 字幕

@dataclass
class SubtitleEntry:
    index: int
    start: float
    end: float
    text: str


_SRT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def _parse_srt_time(token: str) -> float:
    m = _SRT_TIME.fullmatch(token.strip())
    if not m:
        raise MediaToolError(f"无法解析 SRT 时间：{token}")
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_srt(path: str) -> list:
    """解析 SRT 字幕文件为结构化条目。"""
    raw = Path(path).read_text(encoding="utf-8-sig")
    entries = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        start_token, end_token = lines[idx].split("-->", 1)
        entries.append(SubtitleEntry(
            index=len(entries) + 1,
            start=_parse_srt_time(start_token),
            end=_parse_srt_time(end_token),
            text="\n".join(lines[idx + 1 :]),
        ))
    return entries
