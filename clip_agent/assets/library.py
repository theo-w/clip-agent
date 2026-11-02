"""创作资产库（SDD 模块 4）：调色预设 / 字幕模板 / Skill 组合的存取与版本管理。

存储：data/assets.json（JSON 文件）；首次加载自动播种示例预设。
能力：检索、标签筛选、另存为、收藏、版本回滚、导出。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..paths import data_dir


class AssetNotFoundError(KeyError):
    pass


@dataclass
class Asset:
    asset_id: str
    asset_type: str        # color_preset | subtitle_template | skill_combo
    name: str
    params: dict
    tags: list = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    favorites: int = 0
    is_favorite: bool = False
    is_public: bool = False  # 公共优质资产（推荐），默认个人私有
    history: list = field(default_factory=list)  # 历史版本参数快照

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def default_store_path() -> Path:
    return data_dir() / "assets.json"


SEED_PRESETS = [
    {
        "asset_id": "color001",
        "asset_type": "color_preset",
        "name": "清冷胶片感",
        "params": {"brightness": -0.05, "contrast": 1.15, "saturation": 0.85, "temperature": -0.3},
        "tags": ["冷色", "胶片", "vlog"],
        "created_at": "", "updated_at": "", "version": 1, "favorites": 0,
        "is_favorite": False, "is_public": True, "history": [],
    },
    {
        "asset_id": "color002",
        "asset_type": "color_preset",
        "name": "暖阳日系",
        "params": {"brightness": 0.06, "contrast": 1.05, "saturation": 1.1, "temperature": 0.35},
        "tags": ["暖色", "日系", "人像"],
        "created_at": "", "updated_at": "", "version": 1, "favorites": 0,
        "is_favorite": False, "is_public": True, "history": [],
    },
    {
        "asset_id": "color003",
        "asset_type": "color_preset",
        "name": "夜感增强",
        "params": {"brightness": -0.1, "contrast": 1.25, "saturation": 1.05, "gamma": 0.95},
        "tags": ["夜景", "城市"],
        "created_at": "", "updated_at": "", "version": 1, "favorites": 0,
        "is_favorite": False, "is_public": True, "history": [],
    },
    {
        "asset_id": "combo001",
        "asset_type": "skill_combo",
        "name": "口播净化流水线",
        "params": {"steps": ["S001", "S002"]},
        "tags": ["口播", "流水线"],
        "created_at": "", "updated_at": "", "version": 1, "favorites": 0,
        "is_favorite": False, "is_public": True, "history": [],
    },
]


class AssetLibrary:
    def __init__(self, path: Path = None) -> None:
        self.path = Path(path) if path else default_store_path()

    # ---------------------------------------------------------------- 存取

    def _load(self) -> list:
        if not self.path.exists():
            self._dump([dict(p) for p in SEED_PRESETS])  # 首次运行播种示例预设
            return [dict(p) for p in SEED_PRESETS]
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _dump(self, rows: list) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------------------------------------------------------------- 查询

    def list(self, keyword: str = "", tag: str = "", asset_type: str = "") -> list:
        result = []
        for row in self._load():
            if keyword and keyword not in row["name"] \
                    and keyword not in " ".join(row.get("tags", [])):
                continue
            if tag and tag not in row.get("tags", []):
                continue
            if asset_type and row["asset_type"] != asset_type:
                continue
            result.append(Asset(**row))
        result.sort(key=lambda a: (-a.favorites, a.name))
        return result

    def get(self, asset_id: str) -> Asset:
        for row in self._load():
            if row["asset_id"] == asset_id:
                return Asset(**row)
        raise AssetNotFoundError(asset_id)

    # ---------------------------------------------------------------- 写入

    def save(self, name: str, asset_type: str, params: dict, tags=None,
             is_public: bool = False, asset_id: str = None) -> Asset:
        """新增或更新资产；更新时自动保存历史版本。"""
        rows = self._load()
        now = _now()
        if asset_id:
            for i, row in enumerate(rows):
                if row["asset_id"] == asset_id:
                    history = row.get("history", []) + [{
                        "version": row["version"], "params": row["params"],
                        "saved_at": now,
                    }]
                    rows[i] = {
                        **row, "name": name, "params": params,
                        "tags": tags or row.get("tags", []), "updated_at": now,
                        "version": row["version"] + 1, "history": history,
                        "is_public": is_public,
                    }
                    self._dump(rows)
                    return Asset(**rows[i])
            raise AssetNotFoundError(asset_id)
        asset = Asset(
            asset_id=uuid.uuid4().hex[:8], asset_type=asset_type, name=name,
            params=params, tags=tags or [], created_at=now, updated_at=now,
            is_public=is_public,
        )
        rows.append(asset.to_dict())
        self._dump(rows)
        return asset

    def favorite(self, asset_id: str, on: bool = True) -> Asset:
        rows = self._load()
        for i, row in enumerate(rows):
            if row["asset_id"] == asset_id:
                rows[i]["favorites"] = max(row.get("favorites", 0) + (1 if on else -1), 0)
                rows[i]["is_favorite"] = on
                self._dump(rows)
                return Asset(**rows[i])
        raise AssetNotFoundError(asset_id)

    def rollback(self, asset_id: str, to_version: int) -> Asset:
        rows = self._load()
        for i, row in enumerate(rows):
            if row["asset_id"] == asset_id:
                target = next(
                    (h for h in row.get("history", []) if h["version"] == to_version),
                    None,
                )
                if target is None:
                    raise ValueError(f"资产 {asset_id} 不存在版本 v{to_version}")
                now = _now()
                history = row.get("history", []) + [{
                    "version": row["version"], "params": row["params"], "saved_at": now,
                }]
                rows[i] = {
                    **row, "params": target["params"], "updated_at": now,
                    "version": row["version"] + 1, "history": history,
                }
                self._dump(rows)
                return Asset(**rows[i])
        raise AssetNotFoundError(asset_id)

    def export(self, asset_id: str) -> str:
        """分享导出：资产完整 JSON。"""
        return json.dumps(self.get(asset_id).to_dict(), ensure_ascii=False, indent=2)
