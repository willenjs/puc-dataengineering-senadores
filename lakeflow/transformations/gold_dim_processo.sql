-- lakeflow/transformations/gold_dim_processo.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.dim_processo (
    id_processo STRING NOT NULL PRIMARY KEY COMMENT 'Identificador do processo legislativo -- FK para dim_materia.id_processo.',
    tramitando STRING COMMENT '"Sim" se o processo ainda está em tramitação, "Não" se já concluiu.',
    situacao_atual STRING COMMENT 'Texto da situação de tramitação atual.',
    sigla_situacao_atual STRING COMMENT 'Código curto da situação atual -- FK para dim_situacao_materia.',
    data_situacao_atual DATE COMMENT 'Data em que a situação atual foi atingida.',
    materia_concluida BOOLEAN COMMENT 'tramitando = "Não" -- não é esperada nova votação sob este id_processo.',
    CONSTRAINT fk_dim_processo_situacao FOREIGN KEY (sigla_situacao_atual) REFERENCES senado_votacoes.gold.dim_situacao_materia(sigla)
)
COMMENT 'Star schema formal: um processo por linha (mesma entidade de silver.status_processos, sem transformação adicional). Escopado às matérias efetivamente votadas -- não cobre as ~18k matérias de dim_materia todas.'
AS SELECT * FROM senado_votacoes.silver.status_processos
