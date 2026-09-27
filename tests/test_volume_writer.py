import json
from pathlib import Path

from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume


def test_build_bronze_relative_path_particiona_por_entidade_e_data():
    path = build_bronze_relative_path("senadores", "2026-09-02", "lista_atual")
    assert path == "senadores/dt=2026-09-02/lista_atual.json"


def test_write_json_to_volume_grava_payload_e_retorna_caminho(tmp_path):
    relative_path = build_bronze_relative_path("senadores", "2026-09-02", "lista_atual")

    full_path = write_json_to_volume(str(tmp_path), relative_path, {"a": 1})

    assert full_path == (tmp_path / relative_path).as_posix()
    conteudo = json.loads(Path(full_path).read_text(encoding="utf-8"))
    assert conteudo == {"a": 1}


def test_write_json_to_volume_cria_diretorios_intermediarios(tmp_path):
    relative_path = build_bronze_relative_path("materias_detalhe", "2026-09-02", "detalhe_170530")

    full_path = write_json_to_volume(str(tmp_path), relative_path, {"codigo": "170530"})

    assert Path(full_path).exists()
