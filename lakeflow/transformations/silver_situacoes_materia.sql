-- lakeflow/transformations/silver_situacoes_materia.sql
-- Payload bruto é um array JSON no nível raiz (não um objeto com namespace, diferente
-- das demais fontes Bronze deste pipeline) -- variant_explode direto no payload.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.situacoes_materia (
    sigla STRING COMMENT 'Código curto da situação de tramitação (ex.: TNJR, RMCD, APRVD).',
    descricao STRING COMMENT 'Texto completo da situação de tramitação.',
    data_inicio DATE COMMENT 'Data a partir da qual este código passou a ser usado.',
    data_fim DATE COMMENT 'Data em que este código deixou de ser usado -- NULL quando ainda está ativo.',
    CONSTRAINT sigla_not_null EXPECT (sigla IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Domínio controlado (referência oficial) de todas as situações de tramitação possíveis para uma matéria/processo -- dá significado a dim_materia.sigla_situacao_atual. Fonte: /processo/tipos-situacao (175 códigos, ativos e históricos, confirmados sem sigla duplicada).'
AS
WITH ultimo_lote AS (
    SELECT payload
    FROM senado_votacoes.bronze.referencia_situacoes
    QUALIFY row_number() OVER (
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),
itens AS (
    SELECT value AS item
    FROM ultimo_lote, LATERAL variant_explode(payload) AS t
)
SELECT
    item:sigla::STRING AS sigla,
    item:descricao::STRING AS descricao,
    item:dataInicio::DATE AS data_inicio,
    item:dataFim::DATE AS data_fim
FROM itens
