"""资产发现（P2 本地先行版）：质量分聚合、素材去重复用、资产广场 CLI/HTML。"""
from datetime import datetime, timedelta

from clip_agent.assets.discovery import (
    AssetInsight,
    quality_score,
    rank,
    use_index,
    weekly_reused_assets,
)
from clip_agent.assets.library import Asset, AssetLibrary
from clip_agent.metrics.tracker import MetricsTracker

BASE = datetime(2026, 11, 2, 12, 0, 0)


def _lib(tmp_path):
    return AssetLibrary(tmp_path / "assets.json")


def _events(uses):
    """uses: [(asset_id, material, days_ago)] → use 埋点列表。"""
    out = []
    for asset_id, material, days_ago in uses:
        ts = BASE - timedelta(days=days_ago)
        out.append({
            "type": "asset", "action": "use", "asset_id": asset_id,
            "material": material, "ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
        })
    return out


def test_quality_score_weights_and_caps():
    asset = Asset(asset_id="x", asset_type="color_preset", name="x", params={},
                  favorites=3, installs=5)
    # 10 次复用：0.5×0.5 + 0.3×0.3 + 0.2×0.5 = 0.44
    assert quality_score(asset, 10) == 44.0
    # 复用封顶 20、收藏封顶 10、导入封顶 10
    assert quality_score(asset, 100) == 69.0


def test_use_index_dedupes_same_material(tmp_path):
    events = _events([
        ("combo001", "a.mp4", 0),
        ("combo001", "a.mp4", 2),
        ("combo001", "b.mp4", 3),
    ])
    index = use_index(events, now=BASE)
    assert len(index["combo001"]["materials"]) == 2
    assert len(index["combo001"]["weekly_materials"]) == 2

    insights = rank(_lib(tmp_path), events, now=BASE)
    combo = next(i for i in insights if i.asset.asset_id == "combo001")
    assert isinstance(combo, AssetInsight)
    assert combo.reuse == 2 and combo.weekly_reuse == 2
    assert combo.score == 5.0  # 0.5×2/20×100


def test_weekly_reuse_window_excludes_old_events():
    events = _events([("combo001", "old.mp4", 10)])
    assert weekly_reused_assets(events, now=BASE) == 0
    events.append({
        "type": "asset", "action": "use", "asset_id": "combo002",
        "material": "new.mp4", "ts": BASE.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    assert weekly_reused_assets(events, now=BASE) == 1


def test_rank_sorts_by_score_and_labels_source(tmp_path):
    lib = _lib(tmp_path)
    community = lib.save("我的口播预设", "color_preset", {"brightness": 0.1},
                         tags=["口播"], is_public=False)
    events = _events([
        (community.asset_id, "m1.mp4", 0),
        (community.asset_id, "m2.mp4", 0),
        (community.asset_id, "m3.mp4", 0),
        (community.asset_id, "m3.mp4", 0),  # 同素材重复，只计 3 个素材
    ])
    insights = rank(lib, events, now=BASE)
    assert insights[0].asset.asset_id == community.asset_id  # 7.5 分高于种子 0 分
    assert insights[0].badge == "社区热门"
    seed = next(i for i in insights if i.asset.asset_id == "combo001")
    assert seed.badge == "官方精选"
    assert seed.reuse == 0

    tag_ids = {i.asset.asset_id for i in rank(lib, [], tag="口播", now=BASE)}
    assert tag_ids == {"combo001", "combo003", community.asset_id}


def test_track_asset_records_material(tmp_path):
    tracker = MetricsTracker(tmp_path / "metrics.jsonl")
    tracker.track_asset("use", "combo001", material="demo.mp4")
    tracker.track_asset("save", "combo001")
    events = tracker.load_events()
    assert events[0]["material"] == "demo.mp4"
    assert "material" not in events[1]


def test_cli_discover_and_html(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLIP_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    from clip_agent.__main__ import main

    lib = AssetLibrary(tmp_path / "data" / "assets.json")
    lib.save("口播 <b>脚本</b>", "color_preset", {}, tags=["口播"], is_public=False)
    tracker = MetricsTracker()
    tracker.track_asset("use", "combo001", material="a.mp4")
    tracker.track_asset("use", "combo001", material="b.mp4")

    assert main(["assets", "discover"]) == 0
    out = capsys.readouterr().out
    assert "资产广场" in out and "combo001" in out
    assert "本周复用 1 个资产" in out and "质量分" in out

    assert main(["assets", "discover", "--tag", "口播", "--html"]) == 0
    out = capsys.readouterr().out
    assert "combo003" in out and "color001" not in out
    html = (tmp_path / "output" / "square.html").read_text(encoding="utf-8")
    assert "创作资产广场" in html and "口播净化流水线" in html
    assert "&lt;b&gt;脚本&lt;/b&gt;" in html and "<b>脚本</b>" not in html
    assert "score-fill" in html and "5.0" in html
