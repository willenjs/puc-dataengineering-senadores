-- lakeflow/transformations/gold_fact_votacao.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.fact_votacao (
    codigo_votacao STRING NOT NULL PRIMARY KEY COMMENT 'Identificador único da votação.',
    codigo_materia STRING COMMENT 'FK para dim_materia -- matéria que foi objeto desta votação.',
    data_votacao DATE COMMENT 'Data em que a votação ocorreu.',
    sequencial_sessao INT COMMENT 'Ordem desta votação dentro da sessão plenária -- distingue 1º/2º turno, texto principal vs. destaque.',
    resultado STRING COMMENT 'Resultado declarado da votação: "A" aprovada, "R" rejeitada. Vem da fonte, nunca da contagem de votos -- um destaque pode ter mais Sim que Não e ser rejeitado por falta de quórum qualificado. Ver silver_votacoes.sql.',
    descricao_votacao STRING COMMENT 'Texto descrevendo o que especificamente foi votado nesta votação (matéria como um todo, emenda, destaque, etc.).',
    objeto_votado STRING COMMENT 'Objeto decidido nesta votação: "texto", "emenda", "artigo" ou "requerimento"; NULL quando a descrição não casa com nenhum padrão conhecido. Allowlist derivada em silver_votacoes.sql -- a expressão vive lá e só lá; consumidores leem esta coluna.',
    numero_objeto STRING COMMENT 'Número do objeto destacado ("157" para a Emenda 157), "texto" quando o objeto é o texto da matéria, NULL quando o destaque não numera o objeto. Ver silver_votacoes.sql.',
    CONSTRAINT fk_votacao_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia)
)
COMMENT 'Star schema formal: uma votação por linha (mesma entidade de silver.votacoes, sem transformação adicional).'
AS SELECT * FROM senado_votacoes.silver.votacoes
