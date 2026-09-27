-- lakeflow/transformations/gold_dim_situacao_materia.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.dim_situacao_materia (
    sigla STRING NOT NULL PRIMARY KEY COMMENT 'Código curto da situação de tramitação (ex.: TNJR, RMCD, APRVD).',
    descricao STRING COMMENT 'Texto completo da situação de tramitação.',
    data_inicio DATE COMMENT 'Data a partir da qual este código passou a ser usado.',
    data_fim DATE COMMENT 'Data em que este código deixou de ser usado -- NULL quando ainda está ativo.'
)
COMMENT 'Star schema formal: domínio controlado de situações de tramitação (mesma entidade de silver.situacoes_materia, sem transformação adicional) -- dá significado a dim_processo.sigla_situacao_atual.'
AS SELECT * FROM senado_votacoes.silver.situacoes_materia
