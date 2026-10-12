from pathlib import Path

from personahood_memory.config import load_settings
from personahood_memory.layout import init_workspace


def test_local_http_endpoint_skips_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    root = init_workspace(tmp_path)
    (root / "ph-memory.toml").write_text(
        'openai_base_url = "http://fedora:8080/v1"\nmodel = "llama3.2"\n',
        encoding="utf-8",
    )
    s = load_settings(root)
    assert s.uses_local_endpoint
    assert s.require_inference_auth() is None
    assert s.openai_api_key == "local"
    assert s.model == "llama3.2"


def test_openrouter_requires_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    root = init_workspace(tmp_path)
    (root / "ph-memory.toml").write_text(
        'openai_base_url = "https://openrouter.ai/api/v1"\nmodel = "qwen/qwen3.8-flash"\n',
        encoding="utf-8",
    )
    s = load_settings(root)
    assert not s.uses_local_endpoint
    assert s.require_inference_auth()


def test_openrouter_api_key_alias(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    root = init_workspace(tmp_path)
    s = load_settings(root)
    assert s.openai_api_key == "sk-or-test"
    assert s.require_inference_auth() is None


def test_cloud_openai_requires_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    root = init_workspace(tmp_path)
    s = load_settings(root)
    assert not s.uses_local_endpoint
    assert s.require_inference_auth()
