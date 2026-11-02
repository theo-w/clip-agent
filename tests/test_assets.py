"""创作资产库测试：保存、更新版本、回滚、收藏、检索。"""
import pytest

from clip_agent.assets.library import AssetLibrary, AssetNotFoundError

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
