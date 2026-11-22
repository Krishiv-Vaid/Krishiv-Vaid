"""Load config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .theme import ROOT


@dataclass(frozen=True)
class GitHubConfig:
    login: str = "Krishiv-Vaid"
    window_days: int = 365
    exclude_repos: tuple[str, ...] = ()
    exclude_languages: tuple[str, ...] = ()
    min_language_share: float = 0.03


@dataclass(frozen=True)
class CoinConfig:
    size: int = 300
    frames: int = 72
    frame_ms: int = 55
    yaw: float = 34.0
    pitch: float = 9.0


@dataclass(frozen=True)
class Config:
    github: GitHubConfig = field(default_factory=GitHubConfig)
    coin: CoinConfig = field(default_factory=CoinConfig)


def load(path: Path = ROOT / "config.toml") -> Config:
    raw = tomllib.loads(path.read_text()) if path.exists() else {}
    gh = raw.get("github", {})
    coin = raw.get("coin", {})
    return Config(
        github=GitHubConfig(
            login=gh.get("login", "Krishiv-Vaid"),
            window_days=int(gh.get("window_days", 365)),
            exclude_repos=tuple(gh.get("exclude_repos", ())),
            exclude_languages=tuple(gh.get("exclude_languages", ())),
            min_language_share=float(gh.get("min_language_share", 0.03)),
        ),
        coin=CoinConfig(**{k: coin[k] for k in coin if k in CoinConfig.__dataclass_fields__}),
    )
