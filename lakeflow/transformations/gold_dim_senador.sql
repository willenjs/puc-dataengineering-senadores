-- lakeflow/transformations/gold_dim_senador.sql
-- Formaliza o nome dimensional sobre a entidade limpa da Silver -- sem transformação
-- adicional (ver silver_senadores.sql para a lógica de origem).
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.dim_senador (
    codigo_senador STRING NOT NULL PRIMARY KEY COMMENT 'Identificador único do senador.',
    nome_senador STRING COMMENT 'Nome parlamentar do senador.',
    partido STRING COMMENT 'Sigla do partido do senador no momento da extração.',
    uf STRING COMMENT 'Unidade federativa (estado) representada pelo senador.',
    url_foto STRING COMMENT 'URL da foto oficial do senador.',
    mandato_inicio INT COMMENT 'Ano de início do mandato atual do senador.',
    mandato_fim INT COMMENT 'Ano de término do mandato atual do senador.'
)
COMMENT 'Star schema formal: um senador por linha (mesma entidade de silver.senadores, sem transformação adicional).'
AS SELECT * FROM senado_votacoes.silver.senadores
