"""创作资产库测试：保存、更新版本、回滚、收藏、检索、导出/导入流通。"""
import json

import pytest

import clip_agent.skills  # noqa: F401  导入即注册内置 Skill（依赖校验用）
from clip_agent.assets.library import AssetLibrary, AssetNotFoundError
from clip_agent.assets.sharing import (
    AssetImportError, check_dependencies, export_asset, import_asset,
)

PARAMS_V1 = {"brightness": 0.1, "contrast": 1.1}
PARAMS_V2 = {"brightness": 0.2, "contrast": 1.3}


@pytest.fixture()
def lib(tmp_path):
    return AssetLibrary(tmp_path / "assets.json")


def test_seed_presets_on_first_load(lib):
    assert lib.get("color001").name == "清冷胶片感"


def test_save_and_update_versioning(lib):
    asset = lib.save("我的预设", "color_preset", PARAMS_V1, tags=["测试"])
    assert asset.version == 1
    updated = lib.save("我的预设", "color_preset", PARAMS_V2,
                       asset_id=asset.asset_id)
    assert updated.version == 2
    assert updated.history[0]["params"] == PARAMS_V1


def test_rollback(lib):
    asset = lib.save("我的预设", "color_preset", PARAMS_V1)
    lib.save("我的预设", "color_preset", PARAMS_V2, asset_id=asset.asset_id)
    rolled = lib.rollback(asset.asset_id, to_version=1)
    assert rolled.params == PARAMS_V1
    assert rolled.version == 3  # 回滚也是一次版本推进，可再次回滚


def test_rollback_unknown_version(lib):
    asset = lib.save("我的预设", "color_preset", PARAMS_V1)
    with pytest.raises(ValueError):
        lib.rollback(asset.asset_id, to_version=99)


def test_favorite_and_search(lib):
    asset = lib.save("夜拍增强", "color_preset", {"gamma": 0.9}, tags=["我的夜景测试"])
    lib.favorite(asset.asset_id)
    rows = lib.list(tag="我的夜景测试")
    assert len(rows) == 1 and rows[0].favorites == 1


def test_get_not_found(lib):
    with pytest.raises(AssetNotFoundError):
        lib.get("nope")


# ---------------------------------------------------------------- V1.1 流通

def _write_clipasset(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_export_generates_share_code(lib, tmp_path):
    asset = lib.save("我的预设", "color_preset", PARAMS_V1)
    out, code = export_asset(lib, asset.asset_id, out=tmp_path / "x.clipasset")
    assert out.exists()
    assert code.startswith("CA-") and len(code) == 8
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "clipasset"
    assert payload["share_code"] == code
    assert payload["asset"]["params"] == PARAMS_V1


def test_import_roundtrip_into_fresh_library(lib, tmp_path):
    asset = lib.save("我的预设", "color_preset", PARAMS_V1,
                    tags=["测试"], dependencies=[{"skill_id": "S001", "min_version": "1.0"}])
    out, code = export_asset(lib, asset.asset_id, out=tmp_path / "x.clipasset")

    lib2 = AssetLibrary(tmp_path / "b.json")
    imported = import_asset(lib2, str(out))
    assert imported.params == PARAMS_V1
    assert imported.share_code == code
    assert imported.installs == 1
    assert lib2.get(imported.asset_id).name == "我的预设"


def test_import_idempotent_on_same_code_same_params(lib, tmp_path):
    asset = lib.save("我的预设", "color_preset", PARAMS_V1)
    out, _ = export_asset(lib, asset.asset_id, out=tmp_path / "x.clipasset")
    count = len(lib.list())
    first = import_asset(lib, str(out))  # 同库重复导入
    assert first.asset_id == asset.asset_id
    assert first.version == 1
    assert len(lib.list()) == count  # 幂等导入未新增条目


def test_import_same_code_new_params_upgrades_version(lib, tmp_path):
    payload = {
        "format": "clipasset", "format_version": 1, "share_code": "CA-TEST01",
        "asset": {
            "asset_id": "ext12345", "asset_type": "color_preset",
            "name": "外部预设", "params": PARAMS_V1,
            "dependencies": [{"skill_id": "S001", "min_version": "1.0"}],
        },
    }
    _write_clipasset(tmp_path / "v1.clipasset", payload)
    first = import_asset(lib, str(tmp_path / "v1.clipasset"))
    assert first.version == 1 and first.share_code == "CA-TEST01"

    # 同分享码、新参数 → 判定为同源资产的新版本，升级而非重复入库
    payload["asset"]["params"] = PARAMS_V2
    _write_clipasset(tmp_path / "v2.clipasset", payload)
    upgraded = import_asset(lib, str(tmp_path / "v2.clipasset"))
    assert upgraded.asset_id == first.asset_id
    assert upgraded.version == 2
    assert upgraded.params == PARAMS_V2
    # 历史可回滚
    rolled = lib.rollback(first.asset_id, to_version=1)
    assert rolled.params == PARAMS_V1


def test_import_rejects_missing_dependency(lib, tmp_path):
    payload = {
        "format": "clipasset", "format_version": 1, "share_code": "CA-BAD001",
        "asset": {
            "asset_id": "ext12345", "asset_type": "color_preset",
            "name": "坏资产", "params": {},
            "dependencies": [{"skill_id": "S999", "min_version": "1.0"}],
        },
    }
    _write_clipasset(tmp_path / "bad.clipasset", payload)
    with pytest.raises(AssetImportError, match="S999"):
        import_asset(lib, str(tmp_path / "bad.clipasset"))
    assert all(a.asset_id != "ext12345" for a in lib.list())  # 未静默入库


def test_import_rejects_version_mismatch(lib, tmp_path):
    payload = {
        "format": "clipasset", "format_version": 1, "share_code": "CA-BAD002",
        "asset": {
            "asset_id": "ext12346", "asset_type": "color_preset",
            "name": "超前版本资产", "params": {},
            "dependencies": [{"skill_id": "S001", "min_version": "9.9"}],
        },
    }
    _write_clipasset(tmp_path / "ver.clipasset", payload)
    with pytest.raises(AssetImportError, match="版本不满足"):
        import_asset(lib, str(tmp_path / "ver.clipasset"))


def test_import_rejects_bad_format(lib, tmp_path):
    bad = _write_clipasset(tmp_path / "plain.json", {"hello": 1})
    with pytest.raises(AssetImportError, match="clipasset"):
        import_asset(lib, str(bad))
    with pytest.raises(AssetImportError, match="不存在"):
        import_asset(lib, str(tmp_path / "nope.clipasset"))


def test_check_dependencies_allows_registered_skill():
    assert check_dependencies([{"skill_id": "S001", "min_version": "1.0"}]) == []
    assert check_dependencies(None) == []


def test_import_assigns_new_id_on_collision(lib, tmp_path):
    # 导入资产的 ID 与本地已有资产冲突但分享码不同 → 分配新 ID，不覆盖本地资产
    local = lib.save("本地同名ID资产", "color_preset", {"brightness": 0.5})
    payload = {
        "format": "clipasset", "format_version": 1, "share_code": "CA-NEWONE",
        "asset": {
            "asset_id": local.asset_id, "asset_type": "color_preset",
            "name": "外部资产", "params": {"brightness": 0.9},
        },
    }
    _write_clipasset(tmp_path / "ext.clipasset", payload)
    imported = import_asset(lib, str(tmp_path / "ext.clipasset"))
    assert imported.asset_id != local.asset_id
    assert lib.get(local.asset_id).params == {"brightness": 0.5}
