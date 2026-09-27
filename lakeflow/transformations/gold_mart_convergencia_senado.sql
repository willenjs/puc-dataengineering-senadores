-- lakeflow/transformations/gold_mart_convergencia_senado.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_convergencia_senado (
    classe STRING NOT NULL PRIMARY KEY COMMENT 'Classe a que o indicador se refere: "baixa" ou "alta". Os nomes seguem nota_classe_baixa/nota_classe_alta e o tipo Classe do site.',
    indice_convergencia DOUBLE COMMENT 'Em [-1, 1]. Para cada matéria substantiva pontuada com posição, o apoio líquido do plenário, (votos Sim - votos Não) / (Sim + Não), multiplicado pela nota da matéria para a classe; depois a média simples entre as matérias. Positivo = o Senado aprovou mais o que beneficia a classe e barrou mais o que a prejudica; 0 = neutro. Escala ABSOLUTA e sem constante calibrada: os limites -1 e +1 são os da própria nota, não os do intervalo observado, então o número não muda de significado quando as notas da v3 chegarem. É pequeno em módulo porque o efeito é pequeno, não por defeito de escala.',
    n_materias BIGINT COMMENT 'Quantidade de matérias na média. Cada matéria pesa igual, qualquer que seja o número de senadores que votou nela: a pergunta é o que o Senado decidiu, não o que cada senador fez.',
    n_materias_unanimes BIGINT COMMENT 'Dentre n_materias, quantas não tiveram nenhum voto contrário ou nenhum favorável. Elas ENTRAM na média, de propósito, ao contrário do índice por senador: aqui não há centragem, uma votação unânime tem apoio líquido de +1 ou -1 e é a expressão mais forte de convergência do plenário. Excluí-las inverteria a comparação entre as classes (medido em 2026-09-16: com todas, baixa +0,135 e alta +0,086; sem as 49 unânimes de 96, baixa +0,041 e alta +0,056).',
    CONSTRAINT classe_valida EXPECT (classe IN ('baixa', 'alta')) ON VIOLATION FAIL UPDATE
)
COMMENT 'Convergência do Senado com cada classe: quanto o plenário, como um todo, aprovou o que beneficia aquela classe. Alimenta o medidor "Convergência Média do Senado" da Tríade no site. Substitui a média das médias por senador de indice_classe_baixa/indice_classe_alta que o site calculava até 2026-09-16, que tinha dois defeitos: pesava igualmente um senador com 2 posições e um com 90, e, enquanto aquelas colunas excluíam as posições unânimes, deixava de fora exatamente as votações em que o Senado convergiu. É uma medida por matéria e não por senador, e por isso lê mart_contribuicao_senador_materia, onde o sinal do voto e as contagens do plenário já estão resolvidos.'
AS
-- avg(contribuicao_classe_baixa) numa matéria é nota_classe_baixa * (n_sim - n_nao) /
-- (n_sim + n_nao): contribuicao_classe_baixa é a nota com o sinal do voto, e a média do
-- sinal entre os senadores que votaram Sim ou Não é o apoio líquido. Assim a regra de sinal
-- continua vivendo só na base compartilhada. n_sim_plenario/n_nao_plenario são constantes
-- dentro da matéria, então max() só as recupera.
WITH por_materia AS (
    SELECT
        codigo_materia,
        avg(contribuicao_classe_baixa) AS apoio_classe_baixa,
        avg(contribuicao_classe_alta) AS apoio_classe_alta,
        max(least(n_sim_plenario, n_nao_plenario)) = 0 AS unanime
    FROM senado_votacoes.gold.mart_contribuicao_senador_materia
    -- Só o objeto TEXTO. O medidor é por matéria, e desde 2026-09-23 a contribuição também tem
    -- linhas de emenda destacada, cuja nota é de delta: misturá-las somaria duas grandezas
    -- diferentes e ainda contaria duas vezes as matérias com destaque.
    WHERE objeto_votado = 'texto'
    GROUP BY codigo_materia
)
SELECT
    'baixa' AS classe,
    avg(apoio_classe_baixa) AS indice_convergencia,
    count(*) AS n_materias,
    count(CASE WHEN unanime THEN 1 END) AS n_materias_unanimes
FROM por_materia
UNION ALL
SELECT
    'alta' AS classe,
    avg(apoio_classe_alta) AS indice_convergencia,
    count(*) AS n_materias,
    count(CASE WHEN unanime THEN 1 END) AS n_materias_unanimes
FROM por_materia
