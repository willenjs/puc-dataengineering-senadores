"""Escrita de payloads brutos da API do Senado num Volume do Unity Catalog (camada Bronze)."""
from __future__ import annotations

import json
from pathlib import Path


def build_bronze_relative_path(entidade: str, extraction_date: str, filename: str) -> str:
    """Monta o caminho relativo particionado: <entidade>/dt=<data>/<arquivo>.json"""
    return f"{entidade}/dt={extraction_date}/{filename}.json"


def write_json_to_volume(volume_root: str, relative_path: str, data: dict) -> str:
    """Grava `data` como JSON em <volume_root>/<relative_path> e retorna o caminho completo."""
    full_path = Path(volume_root) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return full_path.as_posix()
