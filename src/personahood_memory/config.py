"""Load optional ph-memory.toml + env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"


@dataclass
class Settings:
    root: Path
    model: str = "gpt-4.1-mini"
    model_context_tokens: int = 128_000
    max_live_tokens: int = 250_000
    openai_api_key: str = ""
    openai_base_url: str = DEFAULT_OPENAI_BASE

    @property
    def uses_local_endpoint(self) -> bool:
        """True for typical LAN/local OpenAI-compatible servers (http://…)."""
        base = (self.openai_base_url or "").strip()
        if not base:
            return False
        parsed = urlparse(base)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        # Plain http to a host is almost always a local/LAN llama.cpp/Ollama box.
        if parsed.scheme == "http":
            return True
        return False

    def require_inference_auth(self) -> str | None:
        """Return an error message if chat/harvest cannot run, else None."""
        if self.openai_api_key:
            return None
        if self.uses_local_endpoint:
            return None
        return (
            "Set OPENAI_API_KEY (or OPENROUTER_API_KEY), "
            "or point OPENAI_BASE_URL / openai_base_url at a local http:// server."
        )


def load_settings(root: Path, *, model: str | None = None) -> Settings:
    root = root.resolve()
    settings = Settings(root=root)
    cfg = root / "ph-memory.toml"
    if cfg.is_file():
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
        if isinstance(data.get("model"), str):
            settings.model = data["model"]
        if data.get("model_context_tokens") is not None:
            settings.model_context_tokens = int(data["model_context_tokens"])
        if data.get("max_live_tokens") is not None:
            settings.max_live_tokens = int(data["max_live_tokens"])
        if isinstance(data.get("openai_base_url"), str):
            settings.openai_base_url = data["openai_base_url"]
        if isinstance(data.get("openai_api_key"), str):
            settings.openai_api_key = data["openai_api_key"]
    if model:
        settings.model = model
    if os.environ.get("OPENAI_API_KEY"):
        settings.openai_api_key = os.environ["OPENAI_API_KEY"]
    elif os.environ.get("OPENROUTER_API_KEY"):
        settings.openai_api_key = os.environ["OPENROUTER_API_KEY"]
    if os.environ.get("OPENAI_BASE_URL"):
        settings.openai_base_url = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("PH_MEMORY_MODEL"):
        settings.model = os.environ["PH_MEMORY_MODEL"]
    # Local OpenAI-compatible servers usually accept any non-empty Bearer token.
    if not settings.openai_api_key and settings.uses_local_endpoint:
        settings.openai_api_key = "local"
    return settings
