from unittest.mock import MagicMock

from scripts.run_llm_scoring import (
    AMOSTRAS_PADRAO,
    AnthropicLLMClient,
    buscar_chaves_existentes,
    buscar_materias_sem_ementa_vazia,
    chaves_no_volume,
    gravar_resposta_bruta,
    gravar_resultados,
    ler_amostras_pedidas,
    pontuar_e_gravar_incrementalmente,
)


class FakeAnthropicResponse:
    def __init__(self, text):
        self.content = [MagicMock(text=text)]


class FakeThinkingBlock:
    """Simula um bloco sem atributo `text` (ex: ThinkingBlock do SDK real)."""


def test_anthropic_llm_client_extrai_texto_da_resposta():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = FakeAnthropicResponse('{"ok": true}')

    cliente = AnthropicLLMClient(fake_client, model="claude-sonnet-5")
    resultado = cliente.complete("um prompt qualquer")

    assert resultado == '{"ok": true}'
    fake_client.messages.create.assert_called_once_with(
        model="claude-sonnet-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": "um prompt qualquer"}],
    )


def test_anthropic_llm_client_pula_bloco_sem_texto_antes_do_texto():
    fake_response = MagicMock()
    fake_response.content = [FakeThinkingBlock(), MagicMock(text='{"ok": true}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    cliente = AnthropicLLMClient(fake_client)
    resultado = cliente.complete("um prompt qualquer")

    assert resultado == '{"ok": true}'


def test_anthropic_llm_client_retorna_string_vazia_quando_nenhum_bloco_tem_texto():
    fake_response = MagicMock()
    fake_response.content = [FakeThinkingBlock()]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    cliente = AnthropicLLMClient(fake_client)
    resultado = cliente.complete("um prompt qualquer")

    assert resultado == ""


def test_buscar_materias_sem_ementa_vazia_retorna_lista_de_dicts():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("123", "Ementa A", "PL", "10", 2024, "Senador A", "Projeto de Lei"),
        ("456", "Ementa B", "PEC", "20", 2023, "Senadora B", "Proposta de Emenda à Constituição"),
    ]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    materias = buscar_materias_sem_ementa_vazia(conn)

    assert materias == [
        {
            "codigo_materia": "123", "ementa": "Ementa A", "sigla": "PL",
            "numero": "10", "ano": 2024, "autor": "Senador A",
            "tipo_descricao": "Projeto de Lei",
        },
        {
            "codigo_materia": "456", "ementa": "Ementa B", "sigla": "PEC",
            "numero": "20", "ano": 2023, "autor": "Senadora B",
            "tipo_descricao": "Proposta de Emenda à Constituição",
        },
    ]
    cursor.close.assert_called_once()

    sql = cursor.execute.call_args[0][0]
    assert "senado_votacoes.silver.fila_materias_pontuacao" in sql
    # Tarefa de ingestão não lê o Gold: a camada analítica existe para consumo, e a
    # dependência desta tarefa é declarada numa view de controle da Silver.
    assert "senado_votacoes.gold." not in sql
    # Os filtros (votada, substantiva, com ementa) saíram deste SQL e viraram a
    # definição da fila; quem os protege agora é test_filas_controle.py, que lê o
    # arquivo SQL -- inclusive a polaridade de materia_substantiva.


def test_prompt_version_e_v2():
    from scripts.run_llm_scoring import PROMPT_VERSION

    assert PROMPT_VERSION == "v2"


def test_pontuar_repassa_a_materia_inteira_para_o_score():
    # A v2 do prompt precisa de sigla/numero/ano/autor/tipo_descricao, não só da ementa:
    # o dict tem que chegar inteiro em score_materia.
    materia = {
        "codigo_materia": "123", "ementa": "Ementa A", "sigla": "PL",
        "numero": "10", "ano": 2024, "autor": "Senador A", "tipo_descricao": "Projeto de Lei",
    }
    recebidas = []

    def fake_score(m, prompt_version, llm_client, amostra=1, registrar_resposta=None):
        recebidas.append((m, prompt_version))
        return {
            "codigo_materia": m["codigo_materia"],
            "prompt_version": prompt_version,
            "amostra": amostra,
            "status": "ok",
        }

    gravados = []
    pontuadas = pontuar_e_gravar_incrementalmente(
        "/vol", "2026-09-14", [materia], set(), MagicMock(), "v2",
        score=fake_score,
        gravar=lambda root, resultados, data: gravados.extend(resultados),
    )

    assert pontuadas == 1
    assert recebidas == [(materia, "v2")]
    assert gravados[0]["prompt_version"] == "v2"


def test_buscar_chaves_existentes_retorna_set_de_tuplas():
    cursor = MagicMock()
    cursor.fetchall.return_value = [("123", "texto", "v1", 1)]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    chaves = buscar_chaves_existentes(conn)

    assert chaves == {("123", "texto", "v1", 1)}

    sql = cursor.execute.call_args[0][0]
    assert "senado_votacoes.bronze.materia_llm_scores_raw" in sql
    assert "status" in sql
    assert "'ok'" in sql
    # materia_llm_scores_raw é Auto Loader-fed (Plano 1): não tem codigo_materia/
    # prompt_version como colunas typed -- precisam vir de dentro do payload, igual
    # ao silver_materia_scores.sql (ver commit que corrigiu esse mesmo bug lá).
    assert "payload:codigo_materia" in sql
    assert "payload:prompt_version" in sql
    # As linhas v1/v2 já gravadas não têm `amostra` no payload: sem o coalesce elas
    # voltariam com NULL e nunca casariam com a chave (código, versão, 1), fazendo a
    # rodada seguinte repontuar -- e repagar -- as 113 matérias inteiras.
    assert "payload:amostra" in sql
    assert "coalesce" in sql.lower()


def test_chaves_no_volume_encontra_arquivos_com_status_ok(tmp_path):
    materia_dir = tmp_path / "materia_llm_scores_raw" / "dt=2026-09-02"
    materia_dir.mkdir(parents=True)
    (materia_dir / "123_v1.json").write_text(
        '{"codigo_materia": "123", "prompt_version": "v1", "status": "ok"}'
    )
    (materia_dir / "456_v1.json").write_text(
        '{"codigo_materia": "456", "prompt_version": "v1", "status": "ok"}'
    )

    chaves = chaves_no_volume(str(tmp_path))

    assert chaves == {("123", "texto", "v1", 1), ("456", "texto", "v1", 1)}


def test_chaves_no_volume_ignora_arquivos_needs_review(tmp_path):
    # Regressão: uma tentativa anterior que falhou (LLM não devolveu JSON parseável
    # nas 2 tentativas de score_materia) grava um arquivo needs_review no Volume que
    # nunca é removido. Se chaves_no_volume contasse esse arquivo só pela existência
    # (sem olhar o status dentro), a matéria ficaria bloqueada para sempre -- nenhuma
    # execução futura a re-tentaria, mesmo com buscar_chaves_existentes corretamente
    # não contando needs_review como pronto (ela só olha status='ok' na tabela Bronze).
    materia_dir = tmp_path / "materia_llm_scores_raw" / "dt=2026-09-02"
    materia_dir.mkdir(parents=True)
    (materia_dir / "789_v1.json").write_text(
        '{"codigo_materia": "789", "prompt_version": "v1", "status": "needs_review"}'
    )

    chaves = chaves_no_volume(str(tmp_path))

    assert chaves == set()


def test_chaves_no_volume_retorna_vazio_quando_diretorio_nao_existe(tmp_path):
    chaves = chaves_no_volume(str(tmp_path / "nao_existe"))

    assert chaves == set()


def test_gravar_resultados_escreve_um_arquivo_por_resultado():
    escritos = []

    def fake_write(volume_root, relative_path, data):
        escritos.append((volume_root, relative_path, data))
        return f"{volume_root}/{relative_path}"

    resultado = {
        "codigo_materia": "123",
        "prompt_version": "v1",
        "amostra": 1,
        "status": "ok",
        "nota_pobre": 0.5,
        "justificativa_pobre": "x",
        "nota_classe_media": 0.1,
        "justificativa_classe_media": "y",
        "nota_rico": -0.2,
        "justificativa_rico": "z",
    }

    gravar_resultados(
        "/Volumes/senado_votacoes/bronze/raw_landing",
        [resultado],
        "2026-09-02",
        write=fake_write,
    )

    assert escritos == [
        (
            "/Volumes/senado_votacoes/bronze/raw_landing",
            "materia_llm_scores_raw/dt=2026-09-02/123_v1_amostra1.json",
            resultado,
        )
    ]


def test_pontuar_e_gravar_incrementalmente_grava_cada_resultado_imediatamente():
    gravados = []

    def fake_gravar(volume_root, resultados, extraction_date):
        gravados.append(resultados)

    def fake_score(materia, prompt_version, llm_client, amostra=1, registrar_resposta=None):
        return {
            "codigo_materia": materia["codigo_materia"],
            "prompt_version": prompt_version,
            "amostra": amostra,
            "status": "ok",
        }

    materias = [
        {"codigo_materia": "1", "ementa": "a"},
        {"codigo_materia": "2", "ementa": "b"},
    ]

    pontuadas = pontuar_e_gravar_incrementalmente(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        materias=materias,
        existentes=set(),
        llm_client=MagicMock(),
        prompt_version="v1",
        score=fake_score,
        gravar=fake_gravar,
    )

    assert pontuadas == 2
    assert gravados == [
        [{"codigo_materia": "1", "prompt_version": "v1", "amostra": 1, "status": "ok"}],
        [{"codigo_materia": "2", "prompt_version": "v1", "amostra": 1, "status": "ok"}],
    ]


def test_pontuar_e_gravar_incrementalmente_continua_apos_excecao_inesperada():
    gravados = []

    def fake_gravar(volume_root, resultados, extraction_date):
        gravados.append(resultados)

    def fake_score(materia, prompt_version, llm_client, amostra=1, registrar_resposta=None):
        if materia["codigo_materia"] == "1":
            raise RuntimeError("falha de rede simulada")
        return {
            "codigo_materia": materia["codigo_materia"],
            "prompt_version": prompt_version,
            "amostra": amostra,
            "status": "ok",
        }

    materias = [
        {"codigo_materia": "1", "ementa": "a"},
        {"codigo_materia": "2", "ementa": "b"},
    ]

    pontuadas = pontuar_e_gravar_incrementalmente(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        materias=materias,
        existentes=set(),
        llm_client=MagicMock(),
        prompt_version="v1",
        score=fake_score,
        gravar=fake_gravar,
    )

    assert pontuadas == 1
    assert gravados == [[{"codigo_materia": "2", "prompt_version": "v1", "amostra": 1, "status": "ok"}]]


def test_pontuar_e_gravar_incrementalmente_pula_materias_ja_pontuadas():
    # Conta as chamadas em vez de levantar: um AssertionError dentro do fake seria engolido pelo
    # `except Exception` de pontuar_e_gravar_incrementalmente, e o teste passaria mesmo sem o
    # pulo de already_scored -- justamente o que impede uma segunda rodada de pagar de novo.
    chamadas = []

    def score_contando(materia, prompt_version, llm_client):
        chamadas.append(materia["codigo_materia"])
        return {"codigo_materia": materia["codigo_materia"], "prompt_version": prompt_version, "status": "ok"}

    pontuadas = pontuar_e_gravar_incrementalmente(
        volume_root="/Volumes/senado_votacoes/bronze/raw_landing",
        extraction_date="2026-09-02",
        materias=[{"codigo_materia": "1", "ementa": "a"}],
        existentes={("1", "v2")},
        llm_client=MagicMock(),
        prompt_version="v2",
        score=score_contando,
        gravar=lambda volume_root, resultados, extraction_date: None,
    )

    assert chamadas == []
    assert pontuadas == 0


# --- amostra, trilha da resposta crua e repetibilidade (decisões 1.2, 4.3 e 4.4) ---


def test_chaves_no_volume_le_a_amostra_de_dentro_do_payload(tmp_path):
    """A chave sai do payload, não do nome do arquivo: com três segmentos o
    `rpartition("_")` de antes devolveria ("123_v2", "amostra2") e a chave ficaria errada
    justamente na rodada que o índice de amostra existe para permitir."""
    materia_dir = tmp_path / "materia_llm_scores_raw" / "dt=2026-09-16"
    materia_dir.mkdir(parents=True)
    (materia_dir / "123_v2_amostra1.json").write_text(
        '{"codigo_materia": "123", "prompt_version": "v2", "amostra": 1, "status": "ok"}'
    )
    (materia_dir / "123_v2_amostra2.json").write_text(
        '{"codigo_materia": "123", "prompt_version": "v2", "amostra": 2, "status": "ok"}'
    )

    chaves = chaves_no_volume(str(tmp_path))

    assert chaves == {("123", "texto", "v2", 1), ("123", "texto", "v2", 2)}


def test_chaves_no_volume_trata_arquivo_sem_amostra_como_amostra_1(tmp_path):
    """Os 113 arquivos v2 gravados em 2026-09-15 não têm o campo. Se contassem como outra
    coisa, a rodada de repetibilidade repontuaria a amostra 1 inteira em vez da 2."""
    materia_dir = tmp_path / "materia_llm_scores_raw" / "dt=2026-09-15"
    materia_dir.mkdir(parents=True)
    (materia_dir / "123_v2.json").write_text(
        '{"codigo_materia": "123", "prompt_version": "v2", "status": "ok"}'
    )

    assert chaves_no_volume(str(tmp_path)) == {("123", "texto", "v2", 1)}


def test_gravar_resultados_inclui_a_amostra_no_nome_do_arquivo():
    escritos = []

    def fake_write(volume_root, relative_path, data):
        escritos.append(relative_path)
        return f"{volume_root}/{relative_path}"

    gravar_resultados(
        "/Volumes/raiz",
        [{"codigo_materia": "123", "prompt_version": "v2", "amostra": 2, "status": "ok"}],
        "2026-09-16",
        write=fake_write,
    )

    assert escritos == ["materia_llm_scores_raw/dt=2026-09-16/123_v2_amostra2.json"]


def test_gravar_resposta_bruta_usa_caminho_proprio_fora_do_bronze():
    """Um caminho separado no Volume mantém o contrato congelado do Bronze intocado: o Auto
    Loader de materia_llm_scores_raw ingere tudo que cai lá dentro como JSON de nota, e a
    resposta crua não é uma nota."""
    escritos = []

    def fake_write(volume_root, relative_path, data):
        escritos.append((relative_path, data))
        return f"{volume_root}/{relative_path}"

    gravar_resposta_bruta(
        "/Volumes/raiz",
        "2026-09-16",
        codigo_materia="123",
        prompt_version="v2",
        amostra=2,
        tentativa=1,
        resposta_bruta="```json\n{...}\n```",
        write=fake_write,
    )

    caminho, conteudo = escritos[0]
    assert caminho.startswith("materia_llm_scores_resposta_bruta/")
    assert not caminho.startswith("materia_llm_scores_raw/")
    assert caminho == (
        "materia_llm_scores_resposta_bruta/dt=2026-09-16/123_v2_amostra2_tentativa1.json"
    )
    assert conteudo["resposta_bruta"] == "```json\n{...}\n```"
    assert conteudo["codigo_materia"] == "123"
    assert conteudo["prompt_version"] == "v2"
    assert conteudo["amostra"] == 2
    assert conteudo["tentativa"] == 1


def test_pontuar_e_gravar_percorre_todas_as_amostras_pedidas():
    chamadas = []
    gravados = []

    def fake_score(materia, prompt_version, llm_client, amostra=1, registrar_resposta=None):
        chamadas.append((materia["codigo_materia"], amostra))
        return {
            "codigo_materia": materia["codigo_materia"],
            "prompt_version": prompt_version,
            "amostra": amostra,
            "status": "ok",
        }

    pontuadas = pontuar_e_gravar_incrementalmente(
        "/Volumes/raiz",
        "2026-09-16",
        [{"codigo_materia": "123", "ementa": "E"}],
        set(),
        llm_client=object(),
        prompt_version="v2",
        amostras=3,
        score=fake_score,
        gravar=lambda root, resultados, data: gravados.extend(resultados),
    )

    assert chamadas == [("123", 1), ("123", 2), ("123", 3)]
    assert pontuadas == 3
    assert [g["amostra"] for g in gravados] == [1, 2, 3]


def test_pontuar_e_gravar_pula_apenas_a_amostra_ja_pontuada():
    """O caso exato da rodada de repetibilidade: a amostra 1 das 113 matérias já está no
    Bronze, e só a 2 precisa ser paga."""
    chamadas = []

    def fake_score(materia, prompt_version, llm_client, amostra=1, registrar_resposta=None):
        chamadas.append(amostra)
        return {
            "codigo_materia": materia["codigo_materia"],
            "prompt_version": prompt_version,
            "amostra": amostra,
            "status": "ok",
        }

    pontuadas = pontuar_e_gravar_incrementalmente(
        "/Volumes/raiz",
        "2026-09-16",
        [{"codigo_materia": "123", "ementa": "E"}],
        {("123", "texto", "v2", 1)},
        llm_client=object(),
        prompt_version="v2",
        amostras=2,
        score=fake_score,
        gravar=lambda root, resultados, data: None,
    )

    assert chamadas == [2]
    assert pontuadas == 1


def test_ler_amostras_pedidas_prefere_argv_depois_env_depois_o_padrao():
    assert ler_amostras_pedidas(["--amostras", "3"], {}) == 3
    assert ler_amostras_pedidas([], {"SENADO_SCORING_AMOSTRAS": "2"}) == 2
    assert ler_amostras_pedidas([], {}) == AMOSTRAS_PADRAO
    # `.env.example` embarca chaves vazias: depois de `cp .env.example .env` a variável
    # EXISTE com valor "", e um int("") derrubaria a task inteira.
    assert ler_amostras_pedidas([], {"SENADO_SCORING_AMOSTRAS": ""}) == AMOSTRAS_PADRAO
    # Argumentos de outras tasks do Job chegam no mesmo sys.argv e não podem confundir.
    assert ler_amostras_pedidas(["--outra-coisa", "9"], {}) == AMOSTRAS_PADRAO


def test_amostras_padrao_e_1():
    """Rodar o Job sem pedir nada não pode multiplicar o custo de API."""
    assert AMOSTRAS_PADRAO == 1


def test_gravar_resultados_nao_sobrescreve_duas_emendas_da_mesma_materia():
    escritos = []
    resultados = [
        {"codigo_materia": "160197", "numero_objeto": "139", "prompt_version": "emenda-v1", "amostra": 1},
        {"codigo_materia": "160197", "numero_objeto": "147", "prompt_version": "emenda-v1", "amostra": 1},
        {"codigo_materia": "160197", "numero_objeto": "texto", "prompt_version": "v3-com-empurrao", "amostra": 1},
    ]
    gravar_resultados("/vol", resultados, "2026-09-23",
                      write=lambda raiz, caminho, dados: escritos.append(caminho))
    assert len(set(escritos)) == 3
    assert escritos[0].endswith("160197_emenda139_emenda-v1_amostra1.json")
    # O texto mantém o caminho de sempre: nada do que já foi gravado muda de lugar.
    assert escritos[2].endswith("160197_v3-com-empurrao_amostra1.json")
