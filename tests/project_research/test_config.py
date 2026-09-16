import json

import pytest

from project_research.config import load_config, load_project_config


def write(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"project_research": settings}), encoding="utf-8")


def test_local_settings_merge_and_explicit_bom_file_stands_alone(tmp_path):
    write(tmp_path / "config/project.example.json", {"top_k": 2, "codex": {"timeout_seconds": 90}})
    write(tmp_path / "config/project.local.json", {"topic": "context", "codex": {"attempts": 1}})
    config = load_config(tmp_path)
    assert config.topic == "context" and config.top_k == 2
    assert config.codex.timeout_seconds == 90 and config.codex.attempts == 1
    explicit = tmp_path / "explicit.json"
    explicit.write_text('{"project_research": {"topic": "explicit"}}', encoding="utf-8-sig")
    config = load_config(tmp_path, explicit)
    assert config.topic == "explicit" and config.top_k == 5 and config.codex.timeout_seconds == 300


def test_legacy_local_project_block_and_new_local_precedence(tmp_path):
    write(tmp_path / "config/providers.local.json", {"topic": "legacy"})
    assert load_config(tmp_path).topic == "legacy"
    write(tmp_path / "config/project.local.json", {"topic": "new"})
    assert load_config(tmp_path).topic == "new"


def test_removed_sources_cannot_be_silently_enabled():
    assert load_project_config({"sources": {"academic": False, "media": False}}).sources.hackernews
    for source in ("academic", "media"):
        with pytest.raises(ValueError, match="has been removed"):
            load_project_config({"sources": {source: True}})


@pytest.mark.parametrize("value", [[], {"project_research": []}, {"project_research": {"top_k": "bad"}}])
def test_malformed_config_is_not_silently_accepted(tmp_path, value):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(tmp_path, path)
