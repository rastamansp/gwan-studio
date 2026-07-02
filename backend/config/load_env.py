"""Carrega variáveis de ambiente de arquivos .env para dev local."""
from __future__ import annotations

import os
from pathlib import Path


def _parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if '=' not in line:
        return None
    key, _, value = line.partition('=')
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return key, value


def _load_file(path: Path, *, override: bool) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        parsed = _parse_line(raw)
        if not parsed:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value


def load_env() -> None:
    """gwan-studio/.env (defaults) → backend/.env.local (override)."""
    backend_dir = Path(__file__).resolve().parent.parent
    studio_dir = backend_dir.parent
    _load_file(studio_dir / '.env', override=False)
    _load_file(backend_dir / '.env.local', override=True)
