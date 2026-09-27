-- lakeflow/transformations/silver_materias.sql
-- Une duas fontes: matérias encontradas pela busca por ano (materias_pesquisa) e
-- matérias buscadas individualmente por código (materias_detalhe) -- estas cobrem
-- matérias referenciadas por uma votação de 2023-2026 mas que a busca por ano de
-- apresentação não retornou.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.materias (
    codigo_materia STRING COMMENT 'Identificador único da matéria na API do Senado.',
    sigla STRING COMMENT 'Sigla do tipo de matéria (PL, PEC, PLP, MPV, etc.).',
    numero STRING COMMENT 'Número da matéria dentro do seu tipo/ano.',
    ano INT COMMENT 'Ano de apresentação da matéria.',
    ementa STRING COMMENT 'Título/descrição oficial da matéria -- texto usado como entrada para o scoring por LLM.',
    autor STRING COMMENT 'Autor da matéria (senador, comissão ou bancada); serializado como string quando é uma estrutura complexa.',
    data_apresentacao DATE COMMENT 'Data de apresentação da matéria.',
    id_processo STRING COMMENT 'Identificador do processo legislativo desta matéria (IdentificacaoProcesso) -- chave para status_processos (tramitando/situação atual) e para o substituto oficial /processo/{id} dos endpoints de matéria descontinuados.',
    CONSTRAINT codigo_materia_not_null EXPECT (codigo_materia IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT ementa_not_null EXPECT (ementa IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Uma matéria legislativa (projeto de lei, PEC, etc.) por linha, apresentada entre 2023 e 2026 ou referenciada por uma votação do período.'
AS
WITH ultimo_lote_por_ano AS (
    -- `ano` (coluna) não é populada pelo Auto Loader -- dedupamos pelo nome do
    -- arquivo em `_source_endpoint` (ex: .../pesquisa_2023.json -> "2023").
    SELECT payload
    FROM senado_votacoes.bronze.materias_pesquisa
    QUALIFY row_number() OVER (
        PARTITION BY split_part(split_part(_source_endpoint, '_', -1), '.json', 1)
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),

materias_pesquisa AS (
    SELECT value AS materia
    FROM ultimo_lote_por_ano, LATERAL variant_explode(payload:PesquisaBasicaMateria.Materias.Materia) AS t
),

de_pesquisa AS (
    SELECT
        materia:Codigo::STRING AS codigo_materia,
        materia:Sigla::STRING AS sigla,
        materia:Numero::STRING AS numero,
        materia:Ano::INT AS ano,
        materia:Ementa::STRING AS ementa,
        -- Autor pode ser um objeto (comissão/bancada) em vez de string simples;
        -- ::STRING serializa como JSON string nesse caso.
        materia:Autor::STRING AS autor,
        materia:Data::DATE AS data_apresentacao,
        materia:IdentificacaoProcesso::STRING AS id_processo,
        -- Prioridade de desempate quando o mesmo código aparece nas duas fontes: o
        -- detalhe individual (2) é mais completo/canônico que o resumo de busca.
        2 AS prioridade_fonte
    FROM materias_pesquisa
),

ultimo_lote_detalhe AS (
    SELECT payload
    FROM senado_votacoes.bronze.materias_detalhe
    QUALIFY row_number() OVER (
        PARTITION BY split_part(split_part(_source_endpoint, '_', -1), '.json', 1)
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),

de_detalhe AS (
    SELECT
        payload:DetalheMateria.Materia.IdentificacaoMateria.CodigoMateria::STRING AS codigo_materia,
        payload:DetalheMateria.Materia.IdentificacaoMateria.SiglaSubtipoMateria::STRING AS sigla,
        payload:DetalheMateria.Materia.IdentificacaoMateria.NumeroMateria::STRING AS numero,
        payload:DetalheMateria.Materia.IdentificacaoMateria.AnoMateria::INT AS ano,
        payload:DetalheMateria.Materia.DadosBasicosMateria.EmentaMateria::STRING AS ementa,
        payload:DetalheMateria.Materia.DadosBasicosMateria.Autor::STRING AS autor,
        payload:DetalheMateria.Materia.DadosBasicosMateria.DataApresentacao::DATE AS data_apresentacao,
        payload:DetalheMateria.Materia.IdentificacaoMateria.IdentificacaoProcesso::STRING AS id_processo,
        1 AS prioridade_fonte
    FROM ultimo_lote_detalhe
),

unidas AS (
    SELECT * FROM de_pesquisa
    UNION ALL
    SELECT * FROM de_detalhe
)

SELECT
    codigo_materia,
    sigla,
    numero,
    ano,
    ementa,
    autor,
    data_apresentacao,
    id_processo
FROM unidas
QUALIFY row_number() OVER (PARTITION BY codigo_materia ORDER BY prioridade_fonte) = 1
