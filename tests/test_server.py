from subscription_reasoning_bench.server import capabilities, find_ui_dir


def test_ui_assets_exist():
    ui_dir = find_ui_dir()
    assert (ui_dir / "index.html").is_file()
    assert (ui_dir / "app.js").is_file()


def test_capability_matrix_does_not_claim_claude_ultra():
    matrix = capabilities()
    assert "ultra" in matrix["codex"]["efforts"]
    assert "ultra" not in matrix["claude"]["efforts"]
