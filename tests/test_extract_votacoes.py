from senado_pipeline.extract_votacoes import extract_votacoes


def test_extract_votacoes_busca_arquivo_anual_de_cada_ano():
    payloads = {ano: {"ListaVotacoes": {"Votacoes": {"Votacao": []}}} for ano in range(2023, 2027)}

    def fake_fetch(path):
        ano = int(path.replace("/arquivos/ListaVotacoes", "").replace(".json", ""))
        return payloads[ano]

    written = []

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_votacoes(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"anos_extraidos": 4, "anos_falhos": []}
    assert ("votacoes/dt=2026-09-02/lista_2023.json", payloads[2023]) in written
    assert len(written) == 4


def test_extract_votacoes_registra_ano_com_falha_sem_derrubar_extracao():
    def fake_fetch(path):
        if "2023" in path:
            return {"ListaVotacoes": {"Votacoes": {"Votacao": []}}}
        raise RuntimeError("boom")

    summary = extract_votacoes(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=lambda *a, **k: "noop",
    )

    assert summary == {"anos_extraidos": 1, "anos_falhos": [2024, 2025, 2026]}
