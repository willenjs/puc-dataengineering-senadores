from senado_pipeline.extract_senadores import extract_senadores


def test_extract_senadores_grava_payload_bruto_e_conta_parlamentares():
    lista_payload = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {"IdentificacaoParlamentar": {"CodigoParlamentar": "123"}},
                    {"IdentificacaoParlamentar": {"CodigoParlamentar": "456"}},
                ]
            }
        }
    }
    written = []

    def fake_fetch(path):
        assert path == "/senador/lista/legislatura/57"
        return lista_payload

    def fake_write(volume_root, relative_path, data):
        written.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    summary = extract_senadores(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=fake_fetch,
        write=fake_write,
    )

    assert summary == {"senadores_extraidos": 2}
    assert written == [("senadores/dt=2026-09-02/lista_atual.json", lista_payload)]


def test_extract_senadores_lida_com_parlamentar_unico_nao_envolto_em_lista():
    lista_payload = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": {"IdentificacaoParlamentar": {"CodigoParlamentar": "123"}}
            }
        }
    }

    summary = extract_senadores(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        fetch=lambda path: lista_payload,
        write=lambda *a, **k: "noop",
    )

    assert summary == {"senadores_extraidos": 1}
