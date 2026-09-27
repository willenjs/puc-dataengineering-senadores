-- lakeflow/transformations/gold_mart_contribuicao_senador_materia.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_contribuicao_senador_materia (
    codigo_senador STRING NOT NULL COMMENT 'FK para dim_senador.',
    codigo_materia STRING NOT NULL COMMENT 'FK para dim_materia.',
    objeto_votado STRING NOT NULL COMMENT 'Objeto que o senador votou: "texto" (o texto da matéria) ou "emenda" (emenda destacada). A nota do texto é de NÍVEL e a da emenda é de DELTA (o efeito de aprová-la em relação ao texto-base), mas as duas entram no índice do mesmo jeito: com o sinal do voto e centradas pela média do plenário NAQUELE objeto.',
    numero_objeto STRING NOT NULL COMMENT 'Número do objeto: "texto" ou o número da emenda destacada.',
    codigo_votacao STRING NOT NULL COMMENT 'FK para fact_votacao -- a votação que definiu a posição (herdada de mart_posicao_senador).',
    voto STRING NOT NULL COMMENT 'Sim ou Não (posição definitiva, de mart_posicao_senador). Abstenção/Ausente/Secreto não geram linha -- sem sentido de voto não há direção a atribuir.',
    nota_classe_baixa DOUBLE COMMENT 'Nota do objeto para a classe baixa: de fact_materia_scored quando o objeto é o texto (nível), de fact_emenda_scored quando é uma emenda destacada (delta).',
    nota_classe_alta DOUBLE COMMENT 'Nota do objeto para a classe alta: de fact_materia_scored quando o objeto é o texto (nível), de fact_emenda_scored quando é uma emenda destacada (delta).',
    vies_distributivo DOUBLE COMMENT 'nota_classe_baixa - nota_classe_alta, em [-2, 2]. Positivo = o objeto favorece a classe baixa mais que a alta. Eixo único: uma matéria boa para as duas classes tem viés ~0 e deixa de inflar o índice, ao contrário dos dois eixos independentes usados até 2026-09-14.',
    contribuicao_classe_baixa DOUBLE COMMENT 'nota_classe_baixa com o sinal do voto (Sim mantém, Não inverte).',
    contribuicao_classe_alta DOUBLE COMMENT 'nota_classe_alta com o sinal do voto (Sim mantém, Não inverte).',
    contribuicao_bruta DOUBLE COMMENT 'vies_distributivo com o sinal do voto: apoiar matéria pró-classe-baixa ou bloquear matéria pró-classe-alta é positivo; o inverso é negativo.',
    contribuicao_centrada DOUBLE COMMENT 'contribuicao_bruta menos a média de contribuicao_bruta entre todos os senadores que se posicionaram (Sim/Não) neste objeto. Mede o desvio do senador em relação ao plenário; objeto votado por unanimidade dá exatamente 0 para todo mundo, por construção.',
    n_sim_plenario BIGINT COMMENT 'Quantidade de senadores que votaram Sim neste objeto (posição definitiva).',
    n_nao_plenario BIGINT COMMENT 'Quantidade de senadores que votaram Não neste objeto (posição definitiva). Um objeto é considerado "contestado" a partir de 5 votos Não -- limiar usado por mart_alinhamento_senador.n_posicoes_contestadas e como filtro de candidatas em mart_destaque_senador.',
    CONSTRAINT contribuicao_centrada_not_null EXPECT (contribuicao_centrada IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT pk_mart_contribuicao_senador_materia PRIMARY KEY (codigo_senador, codigo_materia, objeto_votado, numero_objeto),
    CONSTRAINT fk_mart_contribuicao_senador FOREIGN KEY (codigo_senador) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador),
    CONSTRAINT fk_mart_contribuicao_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia),
    CONSTRAINT fk_mart_contribuicao_votacao FOREIGN KEY (codigo_votacao) REFERENCES senado_votacoes.gold.fact_votacao(codigo_votacao)
)
COMMENT 'Contribuição de cada posição (senador x objeto votado) para o índice de viés distributivo: eixo único nota_classe_baixa - nota_classe_alta, com o sinal do voto e centrado pela média do plenário no mesmo objeto. O objeto é o texto da matéria (nota de nível, de fact_materia_scored) ou uma emenda destacada (nota de delta, de fact_emenda_scored); a centragem é feita dentro do objeto, porque o plenário de uma emenda não é o do texto. Só matérias substantivas (dim_tipo_materia.materia_substantiva), pontuadas e concluídas (mart_posicao_senador já garante a conclusão). Base de mart_alinhamento_senador, mart_alinhamento_partido_uf, mart_alinhamento_temporal e mart_destaque_senador -- a lógica de sinal/viés/centragem vive só aqui, no mesmo papel que mart_posicao_senador já cumpre para a resolução de posição definitiva.'
AS
WITH posicoes AS (
    -- Texto da matéria: a nota é de nível, e vem de fact_materia_scored.
    SELECT
        ps.codigo_senador,
        ps.codigo_materia,
        ps.objeto_votado,
        ps.numero_objeto,
        ps.codigo_votacao,
        ps.voto,
        ms.nota_classe_baixa,
        ms.nota_classe_alta,
        CASE WHEN ps.voto = 'Sim' THEN 1.0 ELSE -1.0 END AS sinal,
        ms.nota_classe_baixa - ms.nota_classe_alta AS vies_distributivo
    FROM senado_votacoes.gold.mart_posicao_senador ps
    JOIN senado_votacoes.gold.fact_materia_scored ms ON ms.codigo_materia = ps.codigo_materia
    JOIN senado_votacoes.gold.dim_materia m ON m.codigo_materia = ps.codigo_materia
    JOIN senado_votacoes.gold.dim_tipo_materia t ON t.sigla = m.sigla
    WHERE ps.voto IN ('Sim', 'Não')
      AND t.materia_substantiva
      AND ps.objeto_votado = 'texto'

    UNION ALL

    -- Emenda destacada: a nota é de DELTA (efeito de aprovar a emenda sobre o texto-base), e por
    -- isso o join é por (matéria, emenda). O sinal do voto é o mesmo: votar Sim num destaque é
    -- adotar a mudança, votar Não é recusá-la. Emenda sem nota (sem base verificável, ou ainda
    -- não pontuada) simplesmente não entra.
    SELECT
        ps.codigo_senador,
        ps.codigo_materia,
        ps.objeto_votado,
        ps.numero_objeto,
        ps.codigo_votacao,
        ps.voto,
        es.nota_classe_baixa,
        es.nota_classe_alta,
        CASE WHEN ps.voto = 'Sim' THEN 1.0 ELSE -1.0 END AS sinal,
        es.nota_classe_baixa - es.nota_classe_alta AS vies_distributivo
    FROM senado_votacoes.gold.mart_posicao_senador ps
    JOIN senado_votacoes.gold.fact_emenda_scored es
        ON es.codigo_materia = ps.codigo_materia AND es.numero_objeto = ps.numero_objeto
    JOIN senado_votacoes.gold.dim_materia m ON m.codigo_materia = ps.codigo_materia
    JOIN senado_votacoes.gold.dim_tipo_materia t ON t.sigla = m.sigla
    WHERE ps.voto IN ('Sim', 'Não')
      AND t.materia_substantiva
      AND ps.objeto_votado = 'emenda'
),
-- A centragem é DENTRO do objeto: o plenário de uma emenda destacada não é o mesmo do texto, e
-- centrar a emenda pela média do texto misturaria duas grandezas diferentes.
plenario AS (
    SELECT
        codigo_materia,
        objeto_votado,
        numero_objeto,
        avg(sinal * vies_distributivo) AS contribuicao_media_plenario,
        count(CASE WHEN voto = 'Sim' THEN 1 END) AS n_sim_plenario,
        count(CASE WHEN voto = 'Não' THEN 1 END) AS n_nao_plenario
    FROM posicoes
    GROUP BY codigo_materia, objeto_votado, numero_objeto
)
SELECT
    p.codigo_senador,
    p.codigo_materia,
    p.objeto_votado,
    p.numero_objeto,
    p.codigo_votacao,
    p.voto,
    p.nota_classe_baixa,
    p.nota_classe_alta,
    p.vies_distributivo,
    p.sinal * p.nota_classe_baixa AS contribuicao_classe_baixa,
    p.sinal * p.nota_classe_alta AS contribuicao_classe_alta,
    p.sinal * p.vies_distributivo AS contribuicao_bruta,
    p.sinal * p.vies_distributivo - pl.contribuicao_media_plenario AS contribuicao_centrada,
    pl.n_sim_plenario,
    pl.n_nao_plenario
FROM posicoes p
JOIN plenario pl ON pl.codigo_materia = p.codigo_materia
                AND pl.objeto_votado = p.objeto_votado
                AND pl.numero_objeto = p.numero_objeto
