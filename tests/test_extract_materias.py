from senado_pipeline.extract_materias import extract_materias, extract_materias_faltantes


def test_extract_materias_busca_todos_os_anos_e_grava_payload_bruto():
    pesquisa_por_ano = {
        2023: {"PesquisaBasicaMateria": {"Materias": {"Materia": [{"Codigo": "111"}]}}},
        2024: {"PesquisaBasicaMateria": {"Materias": {"Materia": [{"Codigo": "222"}]}}},
        2025: {"PesquisaBasicaMateria": {"Materias": {"Materia": []}}},
        2026: {"PesquisaBasicaMateria": {"Materias": {"Materia": []}}},
    }

    def fake_fetch(path, params=None):
        assert path == "/materia/pesquisa/lista"
        return pesquisa_por_ano[params["ano"]]

    written = []

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_materias(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"anos_extraidos": 4, "anos_falhos": []}
    assert (
        "materias/dt=2026-09-02/pesquisa_2023.json",
        pesquisa_por_ano[2023],
    ) in written
    assert len(written) == 4


def test_extract_materias_registra_ano_com_falha_sem_derrubar_extracao():
    def fake_fetch(path, params=None):
        if params["ano"] == 2023:
            return {"PesquisaBasicaMateria": {"Materias": {"Materia": []}}}
        raise RuntimeError("boom")

    summary = extract_materias(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=lambda *a, **k: "noop",
    )

    assert summary == {"anos_extraidos": 1, "anos_falhos": [2024, 2025, 2026]}


def test_extract_materias_faltantes_busca_detalhe_de_cada_codigo():
    detalhes = {
        "170530": {"DetalheMateria": {"Materia": {"IdentificacaoMateria": {"CodigoMateria": "170530"}}}},
        "172059": {"DetalheMateria": {"Materia": {"IdentificacaoMateria": {"CodigoMateria": "172059"}}}},
    }

    def fake_fetch(path):
        codigo = path.rsplit("/", 1)[-1]
        return detalhes[codigo]

    written = []

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_materias_faltantes(
        codigos=["170530", "172059"],
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"materias_extraidas": 2, "materias_falhas": []}
    assert (
        "materias_detalhe/dt=2026-09-02/detalhe_170530.json",
        detalhes["170530"],
    ) in written
    assert len(written) == 2


def test_extract_materias_faltantes_registra_falha_sem_derrubar_extracao():
    def fake_fetch(path):
        if path.endswith("170530"):
            return {"DetalheMateria": {"Materia": {}}}
        raise RuntimeError("boom")

    summary = extract_materias_faltantes(
        codigos=["170530", "172059"],
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=lambda *a, **k: "noop",
    )

    assert summary == {"materias_extraidas": 1, "materias_falhas": ["172059"]}
