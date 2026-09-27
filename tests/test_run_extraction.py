from unittest.mock import patch

from scripts.run_extraction import run_all


def test_run_all_chama_as_cinco_extracoes_e_consolida_resumo():
    with (
        patch("scripts.run_extraction.extract_senadores") as mock_senadores,
        patch("scripts.run_extraction.extract_materias") as mock_materias,
        patch("scripts.run_extraction.extract_votacoes") as mock_votacoes,
        patch("scripts.run_extraction.extract_tipos_situacao") as mock_tipos_situacao,
        patch("scripts.run_extraction.extract_tipos_materia") as mock_tipos_materia,
    ):
        mock_senadores.return_value = {"senadores_extraidos": 81}
        mock_materias.return_value = {"anos_extraidos": 4, "anos_falhos": []}
        mock_votacoes.return_value = {"anos_extraidos": 4, "anos_falhos": []}
        mock_tipos_situacao.return_value = {"situacoes_extraidas": 175}
        mock_tipos_materia.return_value = {"tipos_extraidos": 184}

        resumo = run_all("/Volumes/senado_votacoes/bronze/raw_landing", "2026-09-02")

        assert resumo == {
            "senadores": {"senadores_extraidos": 81},
            "materias": {"anos_extraidos": 4, "anos_falhos": []},
            "votacoes": {"anos_extraidos": 4, "anos_falhos": []},
            "tipos_situacao": {"situacoes_extraidas": 175},
            "tipos_materia": {"tipos_extraidos": 184},
        }
        mock_senadores.assert_called_once()
        mock_materias.assert_called_once()
        mock_votacoes.assert_called_once()
        mock_tipos_situacao.assert_called_once()
        mock_tipos_materia.assert_called_once()
