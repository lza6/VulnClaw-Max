"""Missing static assets must 404 instead of returning the SPA shell."""

from __future__ import annotations


def test_missing_asset_returns_none(monkeypatch, tmp_path):
    import vulnclaw.web.app as web_app

    dist_dir = tmp_path / "dist"
    static_dir = tmp_path / "static"
    (dist_dir / "assets").mkdir(parents=True)
    static_dir.mkdir()
    (dist_dir / "index.html").write_text("dist", encoding="utf-8")
    (dist_dir / "assets" / "app.js").write_text("js", encoding="utf-8")
    (static_dir / "index.html").write_text("static", encoding="utf-8")

    monkeypatch.setattr(web_app, "FRONTEND_DIST_DIR", dist_dir)
    monkeypatch.setattr(web_app, "STATIC_DIR", static_dir)

    assert web_app.resolve_web_asset("assets/app.js") == dist_dir / "assets" / "app.js"
    assert web_app.resolve_web_asset("assets/missing.js") is None
    assert web_app.resolve_web_asset("deep/spa/route") == dist_dir / "index.html"
    assert web_app.resolve_web_asset("") == dist_dir / "index.html"
