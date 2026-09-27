from senado_pipeline.extract_status_processos import extract_status_processos


def test_extract_status_processos_busca_status_de_cada_id():
    status = {
        "8349431": {"id": 8349431, "codigoMateria": 155651, "tramitando": "Não"},
        "9106586": {"id": 9106586, "codigoMateria": 175745, "tramitando": "Sim"},
    }

    def fake_fetch(path):
        id_processo = path.rsplit("/", 1)[-1]
        return status[id_processo]

    written = []

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_status_processos(
        id_processos=["8349431", "9106586"],
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-06",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"processos_extraidos": 2, "processos_falhos": []}
    assert (
        "status_processos/dt=2026-09-06/status_8349431.json",
        status["8349431"],
    ) in written
    assert len(written) == 2


def test_extract_status_processos_registra_falha_sem_derrubar_extracao():
    def fake_fetch(path):
        if path.endswith("8349431"):
            return {"id": 8349431, "tramitando": "Não"}
        raise RuntimeError("boom")

    summary = extract_status_processos(
        id_processos=["8349431", "9106586"],
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-06",
        fetch=fake_fetch,
        write=lambda *a, **k: "noop",
    )

    assert summary == {"processos_extraidos": 1, "processos_falhos": ["9106586"]}
