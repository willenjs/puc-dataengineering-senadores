-- lakeflow/transformations/silver_fila_materias_pontuacao.sql
-- View de controle da tarefa llm_scoring -- ver o cabeçalho de
-- silver_fila_materias_detalhe.sql para o papel do prefixo fila_.
--
-- O escopo é a regra de custo do projeto: pontuar só o que foi efetivamente votado
-- (~360 matérias, não as ~18k apresentadas) e só tipo substantivo, que é uma redução
-- de cerca de 50x na conta de API. A allowlist de siglas continua morando em
-- silver_tipos_materia.sql; aqui ela é lida, nunca repetida.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.fila_materias_pontuacao (
    codigo_materia STRING COMMENT 'Código da matéria a pontuar -- metade da chave do score, junto com prompt_version e amostra.',
    ementa STRING COMMENT 'Ementa da matéria, o texto que os prompts v1/v2 pontuam. Nunca nula nesta view.',
    sigla STRING COMMENT 'Sigla do tipo da matéria (PL, PEC, ...), usada na identificação que vai no prompt.',
    numero STRING COMMENT 'Número da matéria dentro do ano, usado na identificação que vai no prompt.',
    ano INT COMMENT 'Ano de apresentação da matéria, usado na identificação que vai no prompt.',
    autor STRING COMMENT 'Autoria da matéria, como o Senado publica.',
    tipo_descricao STRING COMMENT 'Nome completo do tipo de matéria (de silver.tipos_materia), que o prompt v2 usa como contexto.'
)
COMMENT 'Fila da tarefa llm_scoring: matérias com ementa, de tipo substantivo e com pelo menos uma votação registrada. Uma linha por matéria elegível, independentemente de já ter score -- o que já foi pontuado é descartado pelo próprio script, que cruza esta fila com as chaves (codigo_materia, prompt_version, amostra) já gravadas na Bronze e no Volume.'
AS
SELECT DISTINCT
    m.codigo_materia,
    m.ementa,
    m.sigla,
    m.numero,
    m.ano,
    m.autor,
    t.descricao AS tipo_descricao
FROM senado_votacoes.silver.materias m
JOIN senado_votacoes.silver.votacoes v ON v.codigo_materia = m.codigo_materia
JOIN senado_votacoes.silver.tipos_materia t ON t.sigla = m.sigla
WHERE m.ementa IS NOT NULL
  AND t.materia_substantiva
