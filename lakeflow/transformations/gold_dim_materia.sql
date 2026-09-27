-- lakeflow/transformations/gold_dim_materia.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.dim_materia (
    codigo_materia STRING NOT NULL PRIMARY KEY COMMENT 'Identificador único da matéria.',
    sigla STRING COMMENT 'Sigla do tipo de matéria (PL, PEC, PLP, MPV, etc.) -- FK para dim_tipo_materia.',
    numero STRING COMMENT 'Número da matéria dentro do seu tipo/ano.',
    ano INT COMMENT 'Ano de apresentação da matéria.',
    ementa STRING NOT NULL COMMENT 'Título/descrição oficial da matéria.',
    autor STRING COMMENT 'Autor da matéria.',
    data_apresentacao DATE COMMENT 'Data de apresentação da matéria.',
    id_processo STRING COMMENT 'Identificador do processo legislativo desta matéria -- FK para dim_processo, mas só populado lá para matérias efetivamente votadas (dim_processo é escopado, não cobre as ~18k matérias todas).',
    CONSTRAINT fk_dim_materia_tipo FOREIGN KEY (sigla) REFERENCES senado_votacoes.gold.dim_tipo_materia(sigla)
)
COMMENT 'Star schema formal: uma matéria por linha (mesma entidade de silver.materias, sem transformação adicional).'
AS SELECT * FROM senado_votacoes.silver.materias
