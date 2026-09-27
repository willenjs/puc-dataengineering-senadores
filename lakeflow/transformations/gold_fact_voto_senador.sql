-- lakeflow/transformations/gold_fact_voto_senador.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.fact_voto_senador (
    codigo_votacao STRING NOT NULL COMMENT 'FK para fact_votacao.',
    codigo_senador STRING NOT NULL COMMENT 'FK para dim_senador.',
    voto_raw STRING COMMENT 'Valor original do campo Voto retornado pela API.',
    voto STRING COMMENT 'Voto normalizado em 5 categorias: Sim, Não, Abstenção, Secreto (votação secreta) ou Ausente -- ver silver_votos.sql para o mapeamento completo a partir de voto_raw.',
    CONSTRAINT fk_voto_votacao FOREIGN KEY (codigo_votacao) REFERENCES senado_votacoes.gold.fact_votacao(codigo_votacao),
    CONSTRAINT fk_voto_senador FOREIGN KEY (codigo_senador) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador)
)
COMMENT 'Star schema formal: um voto por linha (mesma entidade de silver.votos, sem transformação adicional).'
AS SELECT * FROM senado_votacoes.silver.votos
