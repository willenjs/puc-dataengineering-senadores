# Contexto de Negócios e Perguntas (Etapa 2 e 4.1)

Este tópico ocupa dois arquivos: este, com o problema e as perguntas de negócio (Etapa 2), e [4_1-BuscaDeDados.md](4_1-BuscaDeDados.md), com a busca, a estrutura e a licença dos dados brutos (Etapa 4.1).

## Motivação

Há muitos anos em conversas com amigos pensávamos em fazer um site que guardasse e expusésse o histórico das ações dos nossos deputados e senadores e uma espécie de ranking dos políticos. Nunca acreditei em isenção completa, sempre entendi que todos temos uma mas muitos tentam não divulgá-la.

O eleitor tem acesso ao voto, mas quase nunca ao efeito dele. O Senado publica como cada senador votou em cada votação nominal do Plenário. Saber o que essas votações mudam na vida de quem ganha pouco ou de quem ganha muito é mais difícil: exige ler matérias longas, escritas em linguagem jurídica.

A cada quatro anos, por mais que pesquisémos, pouco conseguimos encontrar de forma concreta sobre quanto candidatos defenderam os nossos interesses no Congresso e Senado.

Encontrei nas LLMs uma boa ferramenta para tentar fazer uma avaliação minimamente "isenta" da atuação dos senadores e deputados, e é isto que tento fazer aqui.

## Problema

Entender, a partir das votações nominais do Plenário do Senado na 57ª legislatura
(2023-2026), para qual perfil socioeconômico cada senador tende a legislar: classe baixa ou
classe alta. O dado aberto do Senado registra o voto, mas não registra quem a matéria
beneficia. O projeto preenche essa lacuna com uma nota de impacto distributivo por matéria,
gerada por LLM, e a cruza com o voto de cada senador.

A partir desse cruzamento é possível gerar um rótulo, ou classificação, para cada senador: pró classe baixa, equilibrado ou pró classe alta. O rótulo é relativo, isto é, indica a posição do senador em relação aos colegas, e não um juízo absoluto sobre a quem ele serve. Como a nota do LLM varia de uma avaliação para outra, o rótulo só é publicado quando se mantém diante desse ruído; os senadores cuja posição muda entre avaliações ficam sem rótulo, marcados como "na fronteira" entre dois grupos.

## Escopo

- Casa: o Plenário do Senado Federal. Comissões e Câmara dos Deputados ficam de fora.
- Período: a 57ª legislatura, de 2023 a 2026. A coleta mais recente é de 15/09/2026, e a votação mais recente que ela traz é de 03/09/2026.
- Votações: só as nominais, que registram o voto de cada senador. As votações simbólicas não registram voto individual e não entram. As secretas contam para a participação, mas ficam fora do índice, porque não mostram para que lado o senador votou.
- Matérias: o índice usa só as matérias substantivas (definidas abaixo). A participação usa todas as votações nominais, e a concordância entre senadores usa todas as que têm voto aberto.
- Objeto votado: o texto da matéria e as emendas destacadas. Artigos destacados e requerimentos ficam fora do índice.

## Definições

| Termo | Significado |
|---|---|
| Classe baixa e classe alta | Os perfis "pobre" e "rico" que o LLM avalia em cada matéria. O prompt não fixa faixas de renda: pede que o modelo identifique quem ganha e quem perde com o texto e dê uma nota a cada perfil. O modelo também avalia a classe média, mas essa nota não é usada na análise. |
| Nota de impacto | Vai de -1 (claramente prejudicial ao perfil) a 1 (claramente benéfica). O valor 0 indica efeito neutro ou inexistente. |
| Matéria substantiva | Projetos de lei, propostas de emenda à Constituição, medidas provisórias, vetos e outros tipos que criam ou mudam normas. Indicações de autoridades, requerimentos e ofícios não entram, porque o texto deles não descreve efeito sobre a renda de ninguém. |
| Desvio em relação ao plenário | Em cada votação, a posição do senador é comparada com a média dos colegas que votaram. Apoiar mais que o plenário uma matéria que favorece a classe baixa, ou rejeitar mais uma que favorece a classe alta, é um desvio na direção da classe baixa. O índice do senador é a média desses desvios. |

## Perguntas específicas

1. Em matérias substantivas votadas nominalmente, cada senador desvia do plenário na direção
   da classe baixa ou da classe alta? É possível classificá-lo de forma relativa aos pares?
2. Esse desvio se agrega por partido e por UF, ou desaparece quando se sai do indivíduo?
3. O desvio de um senador muda de um ano para outro dentro da legislatura? Ele se aproxima de
   algum lado perto da eleição de 2026?
4. O Senado como colegiado converge para qual lado: as matérias que aprova favorecem mais a
   classe baixa ou a classe alta?
5. Quais votações são as mais reveladoras da posição de cada senador nas duas pontas do eixo?
6. Que fração do comportamento de voto de cada senador é observável? Quanto é voto secreto,
   ausência ou presidência da sessão?
7. Quais pares de senadores votam de forma mais parecida ou mais divergente, e quais bancadas
   estaduais votam de forma coesa?

Essas perguntas guiam a escolha das fontes, a granularidade das tabelas e as métricas da
Gold. Nenhuma delas é removida ao longo do trabalho; o que não foi respondido por completo é discutido
na [autoavaliação](5-Autoavaliacao.md).

## Como o trabalho foi planejado

Cada etapa abaixo está descrita no tópico indicado:

1. Buscar as fontes: a API de Dados Abertos do Senado, para os votos, e o texto votado de cada matéria, para o impacto ([4.1](4_1-BuscaDeDados.md)).
2. Coletar os dados com scripts em Python que rodam no Databricks e guardam as respostas da API sem alteração ([4.2](4_2-Coleta.md)).
3. Pedir a um LLM nove avaliações independentes de cada matéria votada e usar a mediana delas como nota ([4.1](4_1-BuscaDeDados.md) e [4.2](4_2-Coleta.md)).
4. Organizar os dados em três camadas (Bronze, Silver e Gold), com um esquema estrela na última e um catálogo de dados documentado ([4.3](4_3-Modelagem.md)).
5. Automatizar o caminho todo num pipeline que pode ser executado de novo quando houver votações novas ([4.4](4_4-Carga.md)).
6. Verificar a qualidade dos dados e responder às perguntas com consultas à Gold ([4.5](4_5-AnaliseDeDados.md)).

## Critérios de sucesso

Uma pergunta conta como respondida quando:

- a resposta vem de uma tabela da Gold, e a consulta que a produz aparece no texto, para que qualquer pessoa possa repeti-la;
- o rótulo publicado de cada senador resiste à variação das notas do LLM, e não depende de qual das avaliações foi usada;
- o índice ordena os partidos de forma coerente com o posicionamento conhecido de cada um.

O último critério é um teste de bom senso, e ele só vale porque o nome de quem propôs a matéria é retirado do texto antes de ir para o LLM. O modelo não sabe de que partido veio a proposta, então a ordem dos partidos não pode ser um reflexo disso.
