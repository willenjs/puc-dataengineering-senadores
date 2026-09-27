# Autoavaliação

O objetivo foi atingido em parte. As sete perguntas têm resposta a partir da Gold, mas a resposta ao problema central ficou mais restrita do que eu gostaria. A maior parte das votações nominais do Plenário é secreta (240 de 423), e sobram 96 matérias com voto aberto e efeito sobre a renda para formar o índice. O rótulo (a favor da classe alta ou a favor da classe baixa) de cada senador passou a ser relativo aos colegas e não algo geral. Por exemplo, eu não conseguiria dizer que 80 dos 81 senadores, por exemplo, são na prática a favor da classe alta ou baixa. Só 64 dos 82 senadores elegíveis recebem rótulo, porque nos demais a variação do LLM bastaria para mudar o grupo o que tornaria o rótulo completamente "suspeito". Duas extensões ficaram de fora: uma nota para quem propõe as matérias, e não só para quem vota nelas, que não coube no prazo e a análise de legislaturas anteriores, que multiplicaria o custo das chamadas ao LLM.

A plataforma foi a parte mais tranquila. Com experiência prévia em Snowflake, a passagem para o Databricks foi natural e até prazerosa, e usar Lakeflow, Unity Catalog e Asset Bundles na prática foi um dos principais ganhos do trabalho, junto com a chance de tirar da gaveta uma ideia de projeto. Fiz questão de usar o pipeline dentro do Databricks para aprender realmente. As dificuldades vieram dos dados e do método: a API do Senado, com a busca por ano incompleta, o voto secreto registrado como "Votou" e o partido sem histórico. A escolha do texto realmente votado entre os PDFs de cada matéria, a base estatística, principalmente para o tratamento das diferentes respostas do LLM, em que foi preciso bastante apoio de ferramentas de IA para definir o caminho. Como próximos passos ficariam coletar as votações de legislaturas anteriores, guardar o histórico de partido (versionamento) transformando `dim_senador` em Slowly Changing Dimensions, levar a pontuação v3 para dentro do Job e repetir a avaliação com outros LLMs, para reduzir o risco de um viés próprio de um único modelo.

## Estado de cada pergunta

| Pergunta | Estado | O que limitou a resposta | Onde |
|---|---|---|---|
| 1 | Respondida em parte | O rótulo é relativo aos colegas. Recebem rótulo 64 senadores; 18 ficam na fronteira e 22 não têm votações divididas suficientes. | `gold.mart_alinhamento_senador` |
| 2 | Respondida | O partido explica a maior parte das diferenças; a UF não explica mais que o acaso. | `gold.mart_alinhamento_partido_uf` |
| 3 | Respondida em parte | As posições são estáveis de 2023 a 2025. Em 2026 houve poucas votações divididas, e o efeito da eleição não pôde ser testado. | `gold.mart_alinhamento_temporal` |
| 4 | Respondida | A diferença entre as classes fica dentro da margem de erro. | `gold.mart_convergencia_senado` |
| 5 | Respondida | | `gold.mart_destaque_senador` |
| 6 | Respondida | | `gold.mart_participacao_senador` |
| 7 | Respondida | | `gold.mart_concordancia_par_senadores` e `gold.mart_coesao_bancada_uf` |
