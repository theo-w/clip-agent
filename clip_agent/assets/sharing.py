"""资产流通（V1.1 生态 P1，对齐 docs/ECOSYSTEM-PLAN.md 第 3 节）。

三种能力：
- 导出：单资产 → .clipasset 文件（JSON + 元数据 + 依赖声明 + 分享码）；
- 分享码：由资产内容哈希生成（同内容同码），是导入判重的依据；
- 导入即用：先校验依赖（Skill 未注册/停用/版本不满足 → 明确报错，不静默入库），
  再按分享码判重——同码同参数幂等返回，同码新参数升级为本地新版本，全新资产入库。

设计原则：**资产是参数，不是代码**——.clipasset 不含任何可执行内容，
规避分享链路上的安全与兼容问题。
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import fields
from pathlib import Path

from ..core.registry import REGISTRY
from .library import Asset, AssetLibrary

CLIPASSET_FORMAT = "clipasset"
CLIPASSET_VERSION = 1
SHARE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # 去除易混淆字符 0/O/1/I/L


class AssetImportError(ValueError):
    """导入校验失败：格式不合法 / 依赖不满足。"""


def _share_code(data: dict) -> str:
    """分享码 = 内容哈希前 5 位。同内容同码 → 导入幂等；改参数即换码。"""
    fingerprint = json.dumps(
        [data.get("asset_type", ""), data.get("params", {})],
        ensure_ascii=False, sort_keys=True,
    )
    digest = hashlib.sha1(fingerprint.encode("utf-8")).digest()
    code = "".join(SHARE_CODE_ALPHABET[b % len(SHARE_CODE_ALPHABET)] for b in digest[:5])
    return f"CA-{code}"


def _norm_version(version: str) -> list:
    """版本号归一化为 3 段整数元组：'1.2' → [1, 2, 0]。"""
    nums = []
    for part in str(version).split("."):
        nums.append(int(part) if part.strip().isdigit() else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[:3]


def check_dependencies(dependencies: list) -> list:
    """校验资产依赖，返回问题清单（空列表 = 可安全导入）。"""
    problems = []
    for dep in dependencies or []:
        skill_id = dep.get("skill_id", "")
        min_version = dep.get("min_version", "1.0")
        skill = REGISTRY.get(skill_id)
        if skill is None:
            problems.append(f"依赖 Skill {skill_id} 未注册")
        elif not skill.meta.is_enable:
            problems.append(f"依赖 Skill {skill_id} 当前已停用（先 skills --enable {skill_id}）")
        elif _norm_version(skill.meta.version) < _norm_version(min_version):
            problems.append(
                f"依赖 Skill {skill_id} 版本不满足：需要 ≥ v{min_version}，"
                f"当前 v{skill.meta.version}"
            )
    return problems


def export_asset(lib: AssetLibrary, asset_id: str, out: str = None):
    """导出资产为 .clipasset 分享文件；返回 (文件路径, 分享码)。

    分享码由内容哈希生成并持久化回资产——同内容同码，是导入判重的依据。
    """
    asset = lib.get(asset_id)
    code = asset.share_code or _share_code(asset.to_dict())
    if asset.share_code != code:
        lib.mark_shared(asset_id, code)
    payload = {
        "format": CLIPASSET_FORMAT,
        "format_version": CLIPASSET_VERSION,
        "share_code": code,
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "asset": {**asset.to_dict(), "share_code": code},
    }
    out_path = Path(out) if out else Path.cwd() / f"{asset.asset_id}.clipasset"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path, code


def import_asset(lib: AssetLibrary, file_path: str) -> Asset:
    """导入 .clipasset 文件到本地资产库；校验失败抛 AssetImportError。"""
    path = Path(file_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise AssetImportError(f"文件不存在：{file_path}")
    except json.JSONDecodeError as exc:
        raise AssetImportError(f"不是合法的 JSON 文件：{exc}")

    if not isinstance(payload, dict) or payload.get("format") != CLIPASSET_FORMAT:
        raise AssetImportError("不是有效的 .clipasset 文件（缺少 format=clipasset 标识）")
    if int(payload.get("format_version", 0)) > CLIPASSET_VERSION:
        raise AssetImportError(
            f"文件格式版本 v{payload['format_version']} 高于当前支持 v{CLIPASSET_VERSION}，请升级工具后重试"
        )

    raw = payload.get("asset")
    if not isinstance(raw, dict):
        raise AssetImportError("文件缺少 asset 字段")
    for key in ("asset_type", "name", "params"):
        if key not in raw:
            raise AssetImportError(f"文件缺少必要字段：{key}")

    problems = check_dependencies(raw.get("dependencies") or [])
    if problems:
        raise AssetImportError("依赖校验未通过：" + "；".join(problems))

    allowed = {f.name for f in fields(Asset)}
    data = {k: v for k, v in raw.items() if k in allowed}
    data.setdefault("asset_id", uuid.uuid4().hex[:8])
    data["share_code"] = payload.get("share_code") or _share_code(data)
    data["license"] = data.get("license") or "free"

    existing = lib.find_by_share_code(data["share_code"])
    if existing is None:
        return lib.insert_imported(data)
    if existing.params == data.get("params"):
        return existing  # 幂等导入：同码同参数不重复入库
    # 同源资产的新参数：升级为本地新版本（历史可回滚）
    return lib.save(
        data.get("name", existing.name), data.get("asset_type", existing.asset_type),
        data.get("params", {}), tags=data.get("tags") or existing.tags,
        is_public=existing.is_public, asset_id=existing.asset_id,
    )
