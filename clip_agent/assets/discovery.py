"""资产发现（P2 发现机制本地先行版）：质量分聚合 + 资产广场排序。

对齐 docs/ECOSYSTEM-PLAN.md 第 4、5 节：

- 质量分口径（0–100，透明可解释）：
      score = 100 × (0.5×min(去重复用素材数, 20)/20
                   + 0.3×min(收藏数, 10)/10
                   + 0.2×min(导入数, 10)/10)
- 榜单防刷：复用次数按「独立素材」去重——同一素材反复应用同一资产只算 1 次；
  旧埋点没有 material 字段时按一个未知素材计一次。
- 来源标识：内置/公开资产为「官方精选」，本地资产有复用为「社区热门」，
  其余为「待验证」（零复用，进入观察期）。

本模块只聚合本地埋点与资产库，不承诺在线广场；在线寻址需要平台承载。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .library import Asset, AssetLibrary

REUSE_WEIGHT = 0.5
FAVORITE_WEIGHT = 0.3
INSTALL_WEIGHT = 0.2
REUSE_CAP = 20
FAVORITE_CAP = 10
INSTALL_CAP = 10
WINDOW_DAYS = 7


@dataclass
class AssetInsight:
    """单个资产的发现视图：资产本体 + 质量分 + 复用信号。"""

    asset: Asset
    score: float
    reuse: int            # 去重素材后的累计复用次数
    materials: int        # 不同素材数
    weekly_reuse: int     # 近 7 天去重复用次数
    badge: str            # 官方精选 / 社区热门 / 待验证


def _parse_ts(value) -> datetime:
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def use_index(events: list, now: datetime = None) -> dict:
    """汇总 use 埋点：{asset_id: {"materials": set, "weekly_materials": set}}。"""
    now = now or datetime.now()
    start = now - timedelta(days=WINDOW_DAYS)
    index: dict = {}
    for ev in events or []:
        if ev.get("type") != "asset" or ev.get("action") != "use":
            continue
        asset_id = ev.get("asset_id")
        if not asset_id:
            continue
        rec = index.setdefault(asset_id, {"materials": set(), "weekly_materials": set()})
        # 缺 material 的旧埋点归并为同一个未知素材，避免重复计数
        material = ev.get("material") or ""
        rec["materials"].add(material)
        ts = _parse_ts(ev.get("ts"))
        if ts is not None and ts >= start:
            rec["weekly_materials"].add(material)
    return index


def quality_score(asset: Asset, reuse: int) -> float:
    """质量分 0–100；reuse 为去重素材后的复用次数。"""
    reuse_part = min(max(reuse, 0), REUSE_CAP) / REUSE_CAP
    favorite_part = min(max(asset.favorites, 0), FAVORITE_CAP) / FAVORITE_CAP
    install_part = min(max(asset.installs, 0), INSTALL_CAP) / INSTALL_CAP
    score = 100 * (
        REUSE_WEIGHT * reuse_part
        + FAVORITE_WEIGHT * favorite_part
        + INSTALL_WEIGHT * install_part
    )
    return round(score, 1)


def _badge(asset: Asset, reuse: int) -> str:
    if asset.is_public:
        return "官方精选"
    if reuse > 0:
        return "社区热门"
    return "待验证"


def rank(library: AssetLibrary, events: list = None, tag: str = "",
         asset_type: str = "", limit: int = 0, now: datetime = None) -> list:
    """按质量分排序的资产广场；limit=0 表示不截断。"""
    now = now or datetime.now()
    index = use_index(events or [], now=now)
    insights = []
    for asset in library.list(tag=tag, asset_type=asset_type):
        rec = index.get(asset.asset_id, {"materials": set(), "weekly_materials": set()})
        reuse = len(rec["materials"])
        insights.append(AssetInsight(
            asset=asset,
            score=quality_score(asset, reuse),
            reuse=reuse,
            materials=len(rec["materials"]),
            weekly_reuse=len(rec["weekly_materials"]),
            badge=_badge(asset, reuse),
        ))
    insights.sort(key=lambda i: (-i.score, -i.asset.favorites, i.asset.name))
    return insights[:limit] if limit and limit > 0 else insights


def weekly_reused_assets(events: list, now: datetime = None) -> int:
    """北极星指标「周复用资产数」：近 7 天被不同素材真实复用过的资产数。"""
    index = use_index(events or [], now=now)
    return sum(1 for rec in index.values() if rec["weekly_materials"])
