from senado_pipeline.extract_referencias import extract_tipos_materia, extract_tipos_situacao


def test_extract_tipos_situacao_busca_lista_inteira_e_grava_payload_bruto():
    lista = [
        {"id": 86, "sigla": "AGDDO", "descricao": "AGENDADA PARA ORDEM DO DIA", "dataInicio": "1900-01-01T00:00:00", "dataFim": None},
        {"id": 142, "sigla": "TNJR", "descricao": "TRANSFORMADA EM NORMA JURÍDICA", "dataInicio": "2007-01-01T00:00:00", "dataFim": None},
    ]

    def fake_fetch(path):
        assert path == "/processo/tipos-situacao"
        return lista

    written = []

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_tipos_situacao(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-06",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"situacoes_extraidas": 2}
    assert written == [("referencia_situacoes/dt=2026-09-06/tipos_situacao.json", lista)]


def test_extract_tipos_materia_busca_lista_inteira_e_grava_payload_bruto():
    lista = [
        {"sigla": "PL", "descricao": "Projeto de Lei", "dataInicio": "1900-01-01T00:00:00", "dataFim": None},
        {"sigla": "PEC", "descricao": "Proposta de Emenda à Constituição", "dataInicio": "1900-01-01T00:00:00", "dataFim": None},
    ]

    def fake_fetch(path):
        assert path == "/processo/siglas"
        return lista

    written = []

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_tipos_materia(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-06",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"tipos_extraidos": 2}
    assert written == [("referencia_tipos_materia/dt=2026-09-06/tipos_materia.json", lista)]
