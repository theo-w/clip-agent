"""CLI 入口：clip-agent / python -m clip_agent。

用法示例：
  python -m clip_agent run "识别静音片段并裁剪" --media demo.mp4 --yes
  python -m clip_agent run "筛选高光镜头，匹配BGM卡点" --media v.mp4 --bgm b.m4a
  python -m clip_agent skills                # Skill 清单（--disable/--enable 上下线）
  python -m clip_agent assets list           # 资产库
  python -m clip_agent report               # 评测报表
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from . import skills as skills_pkg  # noqa: F401  导入即注册内置 Skill
from .assets.library import AssetLibrary, AssetNotFoundError
from .assets.sharing import AssetImportError, export_asset, import_asset
from .core.intent import IntentRouter
from .core.models import ExecContext
from .core.registry import REGISTRY
from .core.scheduler import Scheduler
from .metrics.tracker import MetricsTracker
from .preview.snapshot import PreviewSnapshot

SOURCE_LABEL = {"rule": "规则路由", "llm": "本地模型路由"}


# ---------------------------------------------------------------- 参数工具

def _coerce(v: str):
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return v


def _fmt_params(params: dict) -> str:
    return json.dumps(params, ensure_ascii=False)


def _apply_cli_overrides(plan, args) -> None:
    """--asset 与 --set 的参数覆盖（只写进对应 Skill 认识的参数）。"""
    if args.asset:
        for step in plan.steps:
            if step.skill_id == "S005":
                step.params["asset_id"] = args.asset
    for kv in args.set or []:
        k, _, v = kv.partition("=")
        for step in plan.steps:
            skill = REGISTRY.get(step.skill_id)
            if skill and k in skill.meta.params:
                step.params[k] = _coerce(v)


def _merge_overrides(plan, overrides: dict) -> list:
    """把覆盖参数写进认识它的步骤；返回没有任何步骤认识的参数名。"""
    known = set()
    for step in plan.steps:
        skill = REGISTRY.get(step.skill_id)
        if not skill:
            continue
        for k, v in overrides.items():
            if k in skill.meta.params:
                step.params[k] = v
                known.add(k)
    return [k for k in overrides if k not in known]


# ---------------------------------------------------------------- run 子命令

def _execute(plan, ctx, scheduler):
    print()

    def _start(sid, name):
        print(f"▶ 执行 {sid} {name} ...")

    def _end(r):
        if r.ok:
            print(f"  ✓ 完成（{r.duration:.2f}s）")
        else:
            print(f"  ✗ 失败：{r.error}")

    return scheduler.run(plan, ctx, on_step_start=_start, on_step_end=_end)


def _decide(args) -> str:
    """用户决策：应用 / 修改参数重跑 / 放弃 / 仅预览（非交互且未指定 --yes）。"""
    if args.yes:
        return "adopted"
    if not sys.stdin.isatty():
        return "previewed"
    print("\n请选择：[1] 应用  [2] 修改参数重跑  [3] 放弃")
    mapping = {"1": "adopted", "2": "modified", "3": "discarded"}
    while True:
        try:
            choice = input("> ").strip()
        except EOFError:
            return "discarded"
        if choice in mapping:
            return mapping[choice]
        print("请输入 1 / 2 / 3")


def _read_overrides() -> dict:
    print("参数覆盖（格式 k=v，多个用空格分隔，直接回车取消）：")
    try:
        raw = input("> ").strip()
    except EOFError:
        return {}
    if not raw:
        return {}
    overrides = {}
    for token in raw.split():
        k, _, v = token.partition("=")
        if k:
            overrides[k] = _coerce(v)
    return overrides


def _render_all(plan, report, ctx) -> list:
    """用户确认应用后，物化每个 Skill 的成片输出。"""
    produced = []
    for step, result in zip(plan.steps, report.results):
        if not result.ok:
            continue
        skill = REGISTRY.get(step.skill_id)
        if skill is None:
            continue
        try:
            merged = {**skill.meta.params, **step.params}
            produced += skill.render(ctx, merged, result.outputs)
        except Exception as exc:
            print(f"  ⚠ {step.skill_id} 渲染失败：{exc}")
    return produced


def _cmd_run(args) -> int:
    for label, p in (("素材", args.media), ("字幕", args.subtitle), ("BGM", args.bgm)):
        if p and not Path(p).exists():
            print(f"✗ {label}文件不存在：{p}")
            return 1

    tracker = MetricsTracker()
    router = IntentRouter()
    scheduler = Scheduler(tracker=tracker)

    workdir = Path(args.workdir or f"output/run_{datetime.now():%Y%m%d_%H%M%S}")
    ctx = ExecContext(
        media_path=str(Path(args.media).resolve()) if args.media else None,
        subtitle_path=str(Path(args.subtitle).resolve()) if args.subtitle else None,
        bgm_path=str(Path(args.bgm).resolve()) if args.bgm else None,
        workdir=workdir,
    )

    # ① 意图解析 → 执行计划
    summary = "、".join(
        f"{label} {Path(p).name}"
        for label, p in (("视频", args.media), ("字幕", args.subtitle), ("BGM", args.bgm))
        if p
    )
    plan = router.route(args.instruction, media_summary=summary or None)
    print(f"◆ 意图解析（{SOURCE_LABEL.get(plan.source, plan.source)}）：{plan.intent or '未识别'}")
    if plan.explanation:
        print(f"  {plan.explanation}")
    if not plan.steps:
        return 1
    _apply_cli_overrides(plan, args)
    for step in plan.steps:
        skill = REGISTRY.get(step.skill_id)
        extra = f"（参数：{_fmt_params(step.params)}）" if step.params else ""
        print(f"  ▶ {step.skill_id} {skill.meta.name} {extra}")

    # ②③ 执行 → 预览快照 → 决策（修改参数可重跑）
    snapshot = PreviewSnapshot(workdir)
    report = _execute(plan, ctx, scheduler)
    report_path = snapshot.write(plan, report)
    print(f"\n◆ 预览报告：{report_path}")
    print(f"  预览数据：{workdir / 'preview.json'}")

    if not report.ok:
        print(f"\n⚠ 执行中断：{report.error}")
        print("  已保留前面完成的结果；可调整参数后重试。")
        tracker.track_decision(
            [s.skill_id for s in plan.steps], "discarded", note="execution_failed"
        )
        return 2

    while True:
        decision = _decide(args)
        if decision != "modified":
            break
        overrides = _read_overrides()
        if not overrides:
            continue
        unknown = _merge_overrides(plan, overrides)
        if unknown:
            avail = set()
            for s in plan.steps:
                skill = REGISTRY.get(s.skill_id)
                if skill:
                    avail.update(skill.meta.params)
            print(f"  ⚠ 未识别的参数：{', '.join(unknown)}（已忽略）")
            print(f"  可用参数：{', '.join(sorted(avail)) or '无'}")
        print("\n◆ 参数已更新，重新执行...")
        report = _execute(plan, ctx, scheduler)
        report_path = snapshot.write(plan, report)
        print(f"\n◆ 预览报告：{report_path}")
        if not report.ok:
            print(f"\n⚠ 执行中断：{report.error}")
            tracker.track_decision(
                [s.skill_id for s in plan.steps], "discarded", note="execution_failed"
            )
            return 2

    # 资产复用埋点：仅在 S005 真正成功使用预设时计入
    if args.asset and any(r.ok and r.skill_id == "S005" for r in report.results):
        tracker.track_asset("use", args.asset)

    # ④ 应用（渲染成片）或放弃（原素材不变）
    if decision == "adopted":
        if args.no_render:
            print("\n◆ 已采纳方案（--no-render：未渲染成片，方案见预览报告）")
        else:
            produced = _render_all(plan, report, ctx)
            if produced:
                print("\n◆ 已生成成片文件：")
                for p in produced:
                    print(f"  {p}")
            else:
                print("\n◆ 已采纳方案（该 Skill 输出为方案数据，见预览报告）")
    elif decision == "previewed":
        print("\n◆ 已生成预览（非交互模式，未记录采纳/放弃；可用 --yes 直接采纳）")
    else:
        print("\n◆ 已放弃本次 AI 结果，原始素材未做任何修改。")
    tracker.track_decision([s.skill_id for s in plan.steps], decision)
    return 0


# ---------------------------------------------------------------- 其他子命令

def _cmd_skills(args) -> int:
    if args.enable or args.disable:
        skill_id = args.enable or args.disable
        enabled = bool(args.enable)
        try:
            skills_pkg.set_skill_enabled(skill_id, enabled)
        except KeyError:
            print(f"✗ 未注册的 Skill：{skill_id}")
            return 1
        print(f"✓ {skill_id} 已{'启用' if enabled else '停用'}")
        return 0
    rows = REGISTRY.manifest()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(f"{'ID':<7}{'状态':<6}{'名称':<26}说明")
    for r in rows:
        status = "启用" if r["is_enable"] else "停用"
        print(f"{r['skill_id']:<7}{status:<6}{r['name']:<24}{r['desc'][:46]}")
    return 0


def _cmd_assets(args) -> int:
    lib = AssetLibrary()
    tracker = MetricsTracker()
    action = getattr(args, "action", None) or "list"

    if action == "list":
        rows = lib.list(tag=args.tag or "", asset_type=args.type or "")
        if not rows:
            print("（资产库为空）")
            return 0
        print(f"{'ID':<11}{'类型':<17}{'名称':<14}版本  收藏  标签")
        for a in rows:
            print(f"{a.asset_id:<11}{a.asset_type:<17}{a.name:<12}v{a.version:<4}"
                  f"{a.favorites:<5}{','.join(a.tags)}")
        return 0

    if action == "save":
        params = json.loads(args.params)
        asset = lib.save(
            args.name, args.type,
            params,
            tags=[t for t in args.tags.split(",") if t],
        )
        tracker.track_asset("save", asset.asset_id)
        print(f"✓ 已保存资产：{asset.asset_id} {asset.name}（v{asset.version}）")
        return 0

    if action == "favorite":
        try:
            asset = lib.favorite(args.asset_id, on=not args.off)
        except AssetNotFoundError:
            print(f"✗ 资产不存在：{args.asset_id}")
            return 1
        tracker.track_asset("favorite", args.asset_id)
        print(f"✓ {asset.name} 收藏数 {asset.favorites}")
        return 0

    if action == "rollback":
        try:
            asset = lib.rollback(args.asset_id, args.version)
        except (AssetNotFoundError, ValueError) as exc:
            print(f"✗ {exc}")
            return 1
        print(f"✓ 已回滚到 v{args.version} 的参数（当前版本 v{asset.version}）")
        return 0

    if action == "show":
        try:
            a = lib.get(args.asset_id)
        except AssetNotFoundError:
            print(f"✗ 资产不存在：{args.asset_id}")
            return 1
        print(f"ID：{a.asset_id}　名称：{a.name}　类型：{a.asset_type}　版本：v{a.version}")
        print(f"标签：{','.join(a.tags) or '无'}　许可：{a.license}　"
              f"分享码：{a.share_code or '（未分享，导出后生成）'}")
        if a.dependencies:
            deps = "、".join(
                f"{d.get('skill_id')} ≥ v{d.get('min_version', '1.0')}" for d in a.dependencies
            )
            print(f"依赖：{deps}")
        print(f"参数：{json.dumps(a.params, ensure_ascii=False)}")
        return 0

    if action == "export":
        try:
            out, code = export_asset(lib, args.asset_id, out=args.out)
        except AssetNotFoundError:
            print(f"✗ 资产不存在：{args.asset_id}")
            return 1
        tracker.track_asset("export", args.asset_id)
        print(f"✓ 已导出分享文件：{out}")
        print(f"  分享码：{code}（文件发到创作者社群，对方用 assets import 导入即用）")
        return 0

    if action == "import":
        try:
            asset = import_asset(lib, args.file)
        except AssetImportError as exc:
            print(f"✗ 导入失败：{exc}")
            return 1
        tracker.track_asset("import", asset.asset_id)
        print(f"✓ 已导入资产：{asset.asset_id} {asset.name}（v{asset.version}）")
        print(f"  参数：{json.dumps(asset.params, ensure_ascii=False)}")
        print(f"  分享码：{asset.share_code}")
        return 0

    print(f"未知操作：{action}")
    return 1


def _cmd_report(args) -> int:
    print(MetricsTracker().render_report_md())
    return 0


# ---------------------------------------------------------------- 入口

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="clip-agent", description="剪辑辅助 Agent（剪映 PC 生态辅助工具）"
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    run = sub.add_parser("run", help="执行一条自然语言剪辑指令")
    run.add_argument("instruction", help='自然语言指令，如 "识别静音片段并裁剪"')
    run.add_argument("--media", help="视频/音频素材路径")
    run.add_argument("--subtitle", help="SRT 字幕文件路径")
    run.add_argument("--bgm", help="BGM 音频路径")
    run.add_argument("--asset", help="资产库预设 ID（调色等）")
    run.add_argument("--set", action="append", default=[],
                     help="参数覆盖，如 --set top_n=3，可多次")
    run.add_argument("--yes", action="store_true", help="非交互：直接采纳结果")
    run.add_argument("--no-render", action="store_true",
                     help="采纳时不渲染成片，仅保留方案数据")
    run.add_argument("--workdir", help="输出目录（默认 output/run_时间戳）")

    skills_cmd = sub.add_parser("skills", help="查看/管理 Skill 清单")
    skills_cmd.add_argument("--json", action="store_true")
    skills_cmd.add_argument("--disable", metavar="SKILL_ID", help="下线 Skill")
    skills_cmd.add_argument("--enable", metavar="SKILL_ID", help="上线 Skill")

    assets = sub.add_parser("assets", help="创作资产库管理")
    a_sub = assets.add_subparsers(dest="action")
    a_list = a_sub.add_parser("list", help="列出资产")
    a_list.add_argument("--tag", default="")
    a_list.add_argument("--type", dest="type", default="")
    a_save = a_sub.add_parser("save", help="保存资产")
    a_save.add_argument("name")
    a_save.add_argument("--type", dest="type", default="color_preset",
                        choices=["color_preset", "subtitle_template", "skill_combo"])
    a_save.add_argument("--params", required=True, help='参数 JSON，如 \'{"brightness": 0.1}\'')
    a_save.add_argument("--tags", default="")
    a_fav = a_sub.add_parser("favorite", help="收藏/取消收藏")
    a_fav.add_argument("asset_id")
    a_fav.add_argument("--off", action="store_true")
    a_rb = a_sub.add_parser("rollback", help="回滚到历史版本")
    a_rb.add_argument("asset_id")
    a_rb.add_argument("version", type=int)
    a_show = a_sub.add_parser("show", help="查看资产详情（参数/分享码/依赖）")
    a_show.add_argument("asset_id")
    a_exp = a_sub.add_parser("export", help="导出 .clipasset 分享文件（V1.1 流通）")
    a_exp.add_argument("asset_id")
    a_exp.add_argument("--out", default=None, help="输出文件路径（默认当前目录/<ID>.clipasset）")
    a_imp = a_sub.add_parser("import", help="导入 .clipasset 文件（校验依赖后入库）")
    a_imp.add_argument("file")

    sub.add_parser("report", help="输出评测报表")
    return p


def main(argv: list = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "run": _cmd_run,
        "skills": _cmd_skills,
        "assets": _cmd_assets,
        "report": _cmd_report,
    }
    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
