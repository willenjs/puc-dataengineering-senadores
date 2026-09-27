-- lakeflow/transformations/silver_emenda_scores.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.emenda_scores (
    codigo_materia STRING COMMENT 'Matéria a que a emenda destacada pertence.',
    numero_objeto STRING COMMENT 'Número da emenda destacada, que com a matéria forma a chave.',
    prompt_version STRING COMMENT 'Versão do prompt (emenda-v1): o dispositivo da emenda mais o texto-base.',
    n_amostras INT COMMENT 'Quantas amostras formam a nota: sempre 9, porque a emenda só é publicada com as 9 (decisão de 2026-09-17).',
    nota_classe_baixa DOUBLE COMMENT 'Mediana das 9 amostras da nota do DELTA para a classe baixa: -1 é aprovar a emenda piorar claramente a situação dela em relação ao texto-base, 0 é não mudar nada, 1 é melhorar claramente.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa da amostra cuja nota de classe baixa é a mediana (menor índice em caso de empate): texto que o modelo escreveu para exatamente a nota publicada ao lado.',
    amostra_justificativa_classe_baixa INT COMMENT 'De qual amostra veio justificativa_classe_baixa, para a auditoria fechar contra silver.materia_scores_amostras e a resposta crua no Volume.',
    nota_classe_alta DOUBLE COMMENT 'Mediana das 9 amostras da nota do DELTA para a classe alta, na mesma escala.',
    justificativa_classe_alta STRING COMMENT 'Justificativa da amostra cuja nota de classe alta é a mediana (menor índice em caso de empate).',
    amostra_justificativa_classe_alta INT COMMENT 'De qual amostra veio justificativa_classe_alta.',
    fonte_texto STRING COMMENT 'Documento que serviu de texto-base. Ver senado_pipeline/emenda_destacada.py.',
    ids_documento STRING COMMENT 'Ids dos PDFs do texto-base, separados por vírgula.',
    CONSTRAINT codigo_materia_not_null EXPECT (codigo_materia IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_baixa_range EXPECT (nota_classe_baixa BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_alta_range EXPECT (nota_classe_alta BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE,
    -- A mediana de um número ímpar de amostras é sempre a nota de uma delas; se a amostra da
    -- justificativa não for achada, a mediana não é o que se pensa, e a atualização falha.
    CONSTRAINT justificativa_baixa_encontrada EXPECT (amostra_justificativa_classe_baixa IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT justificativa_alta_encontrada EXPECT (amostra_justificativa_classe_alta IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT emenda_so_com_9_amostras EXPECT (n_amostras = 9) ON VIOLATION FAIL UPDATE
)
COMMENT 'Nota de cada emenda destacada que teve votação nominal, uma linha por (matéria, emenda). A nota é a de um DELTA: o efeito de APROVAR a emenda em relação ao texto-base, que é o texto como estava quando o destaque foi votado -- por isso ela NÃO é comparável com a nota de uma matéria, que é de nível. Mediana de 9 amostras, com a justificativa da amostra mediana, e nunca publicada com menos de 9. Emenda sem base verificável fica fora: a 804 da PEC 45/2019, aprovada por subemenda oral, e a subemenda sem número da PLP 175/2024.'
AS
-- Allowlist das versões PUBLICADAS, com a prioridade de cada uma. Até 2026-09-17 a versão
-- vigente era a do arquivo mais recente; com a v3 gravando duas variantes do teste A/B, "a mais
-- recente" seria a última variante coletada, então a prioridade passa a ser declarada.
-- v3-com-empurrao venceu o A/B em 2026-09-18: 20 matérias com viés exatamente 0 sem o empurrão
-- contra 16 com ele, e a regra declarada antes manda manter o empurrão quando sem ele há mais
-- zeros (spec da v3, seção 7).
WITH candidatas AS (
    SELECT * FROM senado_votacoes.silver.emenda_scores_amostras
    WHERE prompt_version = 'emenda-v1' AND amostra BETWEEN 1 AND 9
),
-- A emenda só entra com as 9 amostras: a mediana de 7 não é a mediana de 9, e a estabilidade do
-- rótulo foi calculada para 9.
completas AS (
    SELECT codigo_materia, numero_objeto
    FROM candidatas
    GROUP BY codigo_materia, numero_objeto
    HAVING count(DISTINCT amostra) = 9
),
conjunto AS (
    SELECT c.*
    FROM candidatas c
    JOIN completas k ON k.codigo_materia = c.codigo_materia AND k.numero_objeto = c.numero_objeto
),
medianas AS (
    SELECT
        codigo_materia,
        numero_objeto,
        prompt_version,
        CAST(count(*) AS INT) AS n_amostras,
        median(nota_classe_baixa) AS nota_classe_baixa,
        median(nota_classe_alta) AS nota_classe_alta
    FROM conjunto
    GROUP BY codigo_materia, numero_objeto, prompt_version
)
-- A justificativa não tem mediana: vem da amostra cuja nota daquela classe É a mediana, com
-- desempate pelo menor índice, por classe (decisão de 2026-09-17).
SELECT
    m.codigo_materia,
    m.numero_objeto,
    m.prompt_version,
    m.n_amostras,
    m.nota_classe_baixa,
    min_by(c.justificativa_classe_baixa, c.amostra) FILTER (WHERE c.nota_classe_baixa = m.nota_classe_baixa) AS justificativa_classe_baixa,
    min(c.amostra) FILTER (WHERE c.nota_classe_baixa = m.nota_classe_baixa) AS amostra_justificativa_classe_baixa,
    m.nota_classe_alta,
    min_by(c.justificativa_classe_alta, c.amostra) FILTER (WHERE c.nota_classe_alta = m.nota_classe_alta) AS justificativa_classe_alta,
    min(c.amostra) FILTER (WHERE c.nota_classe_alta = m.nota_classe_alta) AS amostra_justificativa_classe_alta,
    max(c.fonte_texto) AS fonte_texto,
    max(c.ids_documento) AS ids_documento
FROM medianas m
JOIN conjunto c ON c.codigo_materia = m.codigo_materia AND c.numero_objeto = m.numero_objeto
                AND c.prompt_version = m.prompt_version
GROUP BY m.codigo_materia, m.numero_objeto, m.prompt_version, m.n_amostras,
         m.nota_classe_baixa, m.nota_classe_alta
