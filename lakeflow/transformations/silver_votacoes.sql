-- lakeflow/transformations/silver_votacoes.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.votacoes (
    codigo_votacao STRING COMMENT 'Identificador único da votação (Votacao.CodigoSessaoVotacao).',
    codigo_materia STRING COMMENT 'Matéria que foi objeto desta votação.',
    data_votacao DATE COMMENT 'Data em que a votação ocorreu.',
    -- Uma matéria pode ter mais de uma votação (1º/2º turno de PEC, destaques votados
    -- separadamente do texto principal) -- estes dois campos existem pra permitir
    -- ordenar/distinguir essas votações. Deliberadamente NÃO escolhemos aqui uma
    -- "votação definitiva" por matéria: fazer isso direito exige saber se a matéria já
    -- está concluída (uma matéria com só 1 votação pode simplesmente ainda não ter
    -- chegado ao 2º turno ou ao destaque), sinal que não temos hoje.
    sequencial_sessao INT COMMENT 'Ordem desta votação dentro da sessão plenária (Votacao.SequencialSessao) -- distingue, por exemplo, o 1º do 2º turno de uma PEC, ou o texto principal de um destaque votado depois.',
    resultado STRING COMMENT 'Resultado declarado da votação (Votacao.Resultado): "A" aprovada, "R" rejeitada. Vem da fonte e NÃO é inferido da contagem de votos: três destaques com mais Sim que Não foram rejeitados por falta de quórum qualificado (a Emenda 2.203 à PLP 68/2024, por 33 a 32; a 2.223, por 37 a 24; a Emenda 587 à PLP 108/2024, por 33 a 27). É o campo que diz se uma emenda destacada entrou ou não no texto, e por isso decide qual documento é o texto-base ao pontuar a emenda.',
    descricao_votacao STRING COMMENT 'Texto descrevendo o que especificamente foi votado nesta votação (Votacao.DescricaoVotacao) -- ex.: "nos termos do parecer, ressalvados os destaques" vs. "Emenda nº 8... destacada". Complementa a ementa da matéria (que descreve a matéria como um todo, não a votação específica).',
    objeto_votado STRING COMMENT 'Que objeto o plenário decidiu nesta votação, derivado de descricao_votacao: "texto" (o texto da matéria, incluindo substitutivo, 1º/2º turno e PLV de MPV), "emenda" (emenda ou subemenda destacada), "artigo" (artigo, parágrafo ou expressão destacados) ou "requerimento" (adiamento, preferência, urgência, calendário -- sem conteúdo distributivo, fora do índice em definitivo). NULL quando a descrição não casa com nenhum padrão conhecido: é uma ALLOWLIST, então objeto desconhecido fica fora do índice por padrão, mesma regra de dim_tipo_materia.materia_substantiva. Existe porque a posição de um senador numa matéria precisa ser o voto sobre o objeto que recebeu a nota: até 2026-09-16 a posição vinha da votação mais recente, e em 29 matérias isso era um destaque, cujo sentido pode ser o oposto do texto (na PLP 210/2024 a Emenda 20 destacada suprimia parte do ajuste fiscal, e um "Não" a ela era apoio ao corte).',
    numero_objeto STRING COMMENT 'Número do objeto destacado, extraído de descricao_votacao: "157" para a Emenda 157 destacada, "30" para o art. 30 destacado. Vale "texto" quando objeto_votado = "texto", porque o texto é objeto único da matéria. NULL quando a descrição destaca um objeto mas não o numera -- caso da subemenda ao substitutivo da PLP 175/2024, que por isso fica fora do índice pela regra de allowlist. É o que distingue as três emendas destacadas de uma mesma matéria, e sem ele a chave de mart_posicao_senador não fecha.',
    CONSTRAINT codigo_votacao_not_null EXPECT (codigo_votacao IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Uma votação plenária por linha, vinculada à matéria votada e classificada pelo objeto que foi decidido.'
AS
WITH ultimo_lote_por_ano AS (
    SELECT payload
    FROM senado_votacoes.bronze.votacoes_lista_anual
    QUALIFY row_number() OVER (
        PARTITION BY split_part(split_part(_source_endpoint, '_', -1), '.json', 1)
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),

votacoes AS (
    SELECT value AS votacao
    FROM ultimo_lote_por_ano, LATERAL variant_explode(payload:ListaVotacoes.Votacoes.Votacao) AS t
),

campos AS (
    SELECT
        votacao:CodigoSessaoVotacao::STRING AS codigo_votacao,
        votacao:CodigoMateria::STRING AS codigo_materia,
        votacao:DataSessao::DATE AS data_votacao,
        votacao:SequencialSessao::INT AS sequencial_sessao,
        votacao:Resultado::STRING AS resultado,
        votacao:DescricaoVotacao::STRING AS descricao_votacao
    FROM votacoes
),

classificadas AS (
SELECT
    codigo_votacao,
    codigo_materia,
    data_votacao,
    sequencial_sessao,
    resultado,
    descricao_votacao,
    -- ALLOWLIST, na ordem em que os casos se excluem. O guarda de destaque é
    -- `destacad[oa]s?` (destacada/destacado/destacadas/destacados) e NÃO `destaque`:
    -- "nos termos do parecer, ressalvados os destaques" descreve o texto principal
    -- sendo votado COM os destaques ressalvados, não o destaque em si.
    CASE
        -- Requerimento primeiro: adiamento, preferência, urgência e calendário especial
        -- aparecem como "Votação nominal do Requerimento nº N...". Fora do índice em
        -- definitivo -- decidir quando votar não tem conteúdo distributivo.
        WHEN descricao_votacao RLIKE r'(?i)\bRequerimento\b' THEN 'requerimento'
        -- Artigo/parágrafo/expressão destacados: o plenário decidiu manter ou suprimir
        -- um trecho do texto. Objeto próprio, ainda sem nota (incremento 3).
        WHEN descricao_votacao RLIKE r'(?i)\bdestacad[oa]s?\b'
         AND descricao_votacao RLIKE r'(?i)^(votação\s+nominal\s+)?d[ao]s?\s+(art\.|artigo|§|express|dispositivos|capítulo|inciso|alínea|parágrafo)'
            THEN 'artigo'
        -- Emenda ou subemenda destacada: objeto próprio, com nota de delta (fact_emenda_scored).
        WHEN descricao_votacao RLIKE r'(?i)\bdestacad[oa]s?\b'
         AND descricao_votacao RLIKE r'(?i)^(votação\s+nominal\s+)?d[ao]\s+(sub)?emenda\b'
            THEN 'emenda'
        -- Texto da matéria. Inclui o substitutivo ("Emenda nº N (Substitutivo)", que é o
        -- próprio texto reescrito, não um destaque), o PLV de uma MPV, o Substitutivo da
        -- Câmara e os dois turnos de PEC -- o mesmo objeto votado duas vezes.
        WHEN NOT descricao_votacao RLIKE r'(?i)\bdestacad[oa]s?\b'
         AND (descricao_votacao RLIKE r'(?i)^votação\s+nominal\s+em\s+[12]º\s+turno\s+d[ao]\b'
              OR descricao_votacao RLIKE r'(?i)^(votação,?\s*(nominal,?)?\s*(em\s+(primeiro|segundo)\s+turno,?)?\s*)?(d[ao]s?\s+)?(projeto de lei|projeto de resolução|proposta de emenda|pec\s|pl\s|plp\s|plv\s|substitutivo da câmara|[12]º\s+turno\s+d[ao]\s+proposta|emenda\s+(nº?\s*)?[0-9.]+\s*\(substitutiv)')
            THEN 'texto'
    END AS objeto_votado,
    -- Número do objeto destacado, na mesma descrição de onde sai o objeto. Emenda e subemenda
    -- numeram com "nº"; artigo e parágrafo, com "art." -- e o ponto do milhar sai ("2.223" vira
    -- "2223") porque é assim que /processo/emenda numera.
    CASE
        WHEN descricao_votacao RLIKE r'(?i)\bd[ao]s?\s+(sub)?emenda\b'
            THEN replace(regexp_extract(descricao_votacao, r'(?i)emenda\s+n?[ºo°]?\s*([0-9.]+)', 1), '.', '')
        ELSE replace(regexp_extract(descricao_votacao, r'(?i)(?:art\.|artigo)\s*([0-9.]+)', 1), '.', '')
    END AS numero_do_destaque
FROM campos
QUALIFY row_number() OVER (PARTITION BY codigo_votacao ORDER BY data_votacao DESC) = 1
)

SELECT
    codigo_votacao,
    codigo_materia,
    data_votacao,
    sequencial_sessao,
    resultado,
    descricao_votacao,
    objeto_votado,
    -- O texto é objeto único da matéria, então não precisa de número e recebe 'texto'; destaque
    -- sem número na descrição fica NULL e, por allowlist, fora do índice.
    CASE
        WHEN objeto_votado = 'texto' THEN 'texto'
        WHEN objeto_votado IS NULL THEN NULL
        ELSE nullif(numero_do_destaque, '')
    END AS numero_objeto
FROM classificadas
