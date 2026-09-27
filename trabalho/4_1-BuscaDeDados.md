# Contexto de Negócios e Perguntas (Etapa 2 e 4.1): busca e estrutura dos dados brutos

Continuação do tópico iniciado em [2-Objetivo.md](2-Objetivo.md), onde estão o problema e as perguntas.

A fonte principal é a API de Dados Abertos do Senado Federal. Essa base foi escolhida porque as perguntas do objetivo pedem o voto nominal de cada senador em cada votação do Plenário, e só o Senado publica isso de forma oficial e completa. Uma base que trouxesse apenas o resultado agregado das votações responderia à pergunta sobre o Senado como colegiado, mas não às perguntas sobre indivíduos, partidos, UFs e pares de senadores.

O recorte é a 57ª legislatura, de 2023 a 2026. Ele cobre os mandatos atuais e mantém o volume de matérias pequeno o bastante para que cada uma seja pontuada por um LLM a um custo aceitável.

## O que a API fornece

Quatro conjuntos de dados sustentam o projeto:

- os senadores da legislatura, com partido, UF e datas do mandato;
- as matérias apresentadas, com sigla, ementa e situação;
- as votações do Plenário, com a descrição do que foi votado e o resultado;
- o voto de cada senador em cada votação.

Um quinto conjunto, a lista de siglas de tipos de matéria, serve para separar o que é conteúdo do que é procedimento. Das 184 siglas, a maioria é procedimental (indicações de autoridades, requerimentos, ofícios). Uma ementa desse tipo não descreve impacto nas classes sociais, então só entram no índice as siglas de projetos, propostas de emenda, medidas provisórias e vetos.

Para o impacto nas classes sociais, a API não ajuda diretamente. Ela registra como cada senador votou, mas não diz a quem a matéria beneficia. Por isso o projeto acrescenta uma segunda fonte, que é o texto votado de cada matéria, obtido pelo endpoint de processo. Esse texto é enviado a um LLM, que devolve a nota de impacto sobre a classe baixa e sobre a classe alta. A escolha de fonte, portanto, tem duas metades: a API diz quem votou o quê, e o documento diz o que estava sendo votado.

## Estrutura dos dados brutos

A API responde em JSON aninhado, e cada resposta é gravada inteira, sem alteração, num arquivo do Volume. O Auto Loader transforma cada arquivo numa linha de uma tabela Bronze, com três colunas iguais em todas as fontes: `payload` (o JSON inteiro, do tipo `VARIANT`), `_source_endpoint` (o caminho do arquivo, que contém a data da coleta) e `_loaded_at` (o momento da carga). Por isso uma linha da Bronze não é um senador ou uma votação, e sim uma resposta da API. Como a mesma consulta é repetida em datas diferentes, a Bronze guarda várias cópias do mesmo conteúdo, e a Silver faz a deduplicação, ficando só com a mais recente.

| Tabela Bronze | Endpoint | Linhas (arquivos) | Estrutura do JSON | Campos usados pelo projeto |
|---|---|---|---|---|
| `senadores_lista_atual` | `/senador/lista/legislatura/57` | 10 | `ListaParlamentarLegislatura.Parlamentares.Parlamentar[]`; cada parlamentar tem `IdentificacaoParlamentar` e `Mandatos.Mandato[]` | `CodigoParlamentar`, `NomeParlamentar`, `SiglaPartidoParlamentar`, `UrlFotoParlamentar`; do mandato, `UfParlamentar`, `PrimeiraLegislaturaDoMandato.DataInicio` e `SegundaLegislaturaDoMandato.DataFim` |
| `materias_pesquisa` | `/materia/pesquisa/lista?ano=` | 40 | `PesquisaBasicaMateria.Materias.Materia[]`, com 10 campos por matéria | `Codigo`, `Sigla`, `Numero`, `Ano`, `Ementa`, `Autor`, `Data`, `IdentificacaoProcesso` |
| `materias_detalhe` | `/materia/{codigo}` | 44 | `DetalheMateria.Materia`, com os blocos `IdentificacaoMateria` e `DadosBasicosMateria` | os mesmos oito campos de `materias_pesquisa`, com outros nomes (`CodigoMateria`, `EmentaMateria`, `DataApresentacao` etc.) |
| `votacoes_lista_anual` | `/arquivos/ListaVotacoes{ano}.json` | 40 | `ListaVotacoes.Votacoes.Votacao[]`, com 21 campos por votação; dentro de cada uma, `Votos.VotoParlamentar[]`, com 9 campos por voto | da votação: `CodigoSessaoVotacao`, `CodigoMateria`, `DataSessao`, `SequencialSessao`, `Resultado`, `DescricaoVotacao`; do voto: `CodigoParlamentar` e `Voto` |
| `status_processos` | `/processo/{id}` | 1.083 | um objeto por processo, com 26 campos no primeiro nível (tramitação, documentos, despachos, autuações) | `id`, `tramitando`, `situacaoAtual`, `siglaSituacaoAtual`, `dataSituacaoAtual` |
| `referencia_tipos_materia` | `/processo/siglas` | 3 | lista de objetos com `sigla`, `descricao`, `dataInicio` e `dataFim` | todos os quatro |
| `referencia_situacoes` | `/processo/tipos-situacao` | 3 | lista com os mesmos quatro campos | todos os quatro |
| `materia_llm_scores_raw` | gerada pelo projeto, não pela API | 3.007 | um objeto por amostra: `codigo_materia`, `prompt_version`, `amostra`, `nota_pobre`, `justificativa_pobre`, `nota_classe_media`, `justificativa_classe_media`, `nota_rico`, `justificativa_rico`, `status`, `tentativa`, `modelo`, `fonte_texto`, `ids_documento`, `id_lote`; nas emendas, também `objeto_votado` e `numero_objeto` | as notas e justificativas das classes baixa e alta, a versão, a amostra e o status |

Na fonte há mais campos do que o projeto usa. Uma votação traz 21 campos e só 6 são necessários. O voto traz nome, partido, UF e foto do senador, mas esses dados vêm da dimensão de senadores (`dim_senador`), para que não haja duas versões do mesmo atributo. Dois detalhes da fonte pesam na modelagem. A pesquisa por ano e o detalhe individual devolvem a mesma matéria em formatos diferentes, e a Silver junta as duas com um `UNION ALL`. Já os nomes `nota_pobre` e `nota_rico` foram fixados na primeira versão do prompt e não mudam na Bronze, para não obrigar a pontuar tudo de novo; a Silver os renomeia para `nota_classe_baixa` e `nota_classe_alta`.

## Licença e condições de uso

Os dados vêm do portal de Dados Abertos do Senado Federal. O portal não adota uma licença nomeada, como Creative Commons. Em vez disso, define que um dado é aberto quando pode ser usado livremente por qualquer pessoa, "exigindo-se, no máximo, citar sua proveniência" ([Sobre Dados Abertos](https://www12.senado.leg.br/dados-abertos/sobre)). O Plano de Dados Abertos 2026/2028 fundamenta essa política na Lei de Acesso à Informação (Lei nº 12.527/2011) e no Ato da Comissão Diretora nº 9/2012, e define dado aberto como aquele disponibilizado sob licença que permita livre utilização, consumo e cruzamento. A API não exige cadastro nem autenticação. O único limite de uso declarado na documentação é técnico: mais de 10 requisições por segundo podem receber o erro HTTP 429.

Os textos das matérias enviados ao LLM também são de livre uso. São atos oficiais, e a Lei de Direitos Autorais (Lei nº 9.610/1998, art. 8º, IV) exclui da proteção os textos de leis, decretos, regulamentos e demais atos oficiais.

O projeto cumpre a única condição da fonte ao citar o Senado Federal como origem dos dados. As notas de impacto por classe não são dados do Senado: são produzidas pelo projeto, com um LLM, e devem ser lidas como avaliação do projeto, não como informação oficial.

## Como uma matéria é pontuada

O LLM usado é o claude-sonnet-5, da Anthropic. Ele recebe o texto da matéria na forma em que foi votada, junto com a sigla, o número, o ano e a ementa. Antes de dar as notas, o prompt pede que ele identifique quem ganha e quem perde com o texto: que grupo recebe um benefício direto (transferência de renda, acesso a serviço, direito novo, redução de imposto) e quem paga o custo (tributo, perda de direito ou de benefício). Depois ele dá uma nota de -1 a 1 para três perfis de brasileiro, pobre, classe média e rico, com uma justificativa curta para cada nota. A resposta segue um formato fixo, com campos definidos, para que nenhuma nota se perca na leitura. A nota da classe média é guardada, mas não entra na análise.

O prompt tem uma frase lembrando que matérias fiscais, tributárias ou de gasto público quase sempre afetam a renda de alguém, mesmo quando o texto é técnico. A frase foi testada antes de ficar. As 96 matérias foram avaliadas nove vezes com ela e nove vezes sem ela, e a regra de decisão foi escrita antes de ver os resultados: a frase ficaria se, sem ela, mais matérias recebessem a mesma nota para as duas classes. Foi o que aconteceu (20 matérias sem a frase, contra 16 com ela), e a frase ficou.

Antes de o texto ir para o LLM, saem dele o nome de quem propôs, relatou ou assinou a matéria, o cabeçalho do gabinete e as linhas de assinatura. Um texto em que ainda sobra o nome de algum parlamentar é recusado. Sem essa limpeza, o modelo poderia julgar a matéria pelo partido do autor, e a comparação entre partidos feita na Análise perderia o valor.

As emendas destacadas passam pelo mesmo processo, com uma diferença: o LLM avalia o efeito de aprovar a emenda sobre o texto-base, isto é, o texto da matéria sem ela.

Os dois prompts abaixo são cópias exatas do que foi enviado, geradas a partir de [`src/senado_pipeline/llm_scorer.py`](../src/senado_pipeline/llm_scorer.py). Esta é a V3 (terceira versão) dos prompts.

<details>
<summary>Prompt das matérias (versão <code>v3-com-empurrao</code>, usada nas 96 notas publicadas)</summary>

Parte 1, o documento:

```text
Matéria votada no Senado Federal do Brasil.

Tipo: {sigla} -- {tipo_descricao}
Identificação: {sigla} {numero}/{ano}
Ementa: "{ementa}"

<texto_votado>
{texto da matéria, extraído do PDF e sem nomes de parlamentares}
</texto_votado>
```

Parte 2, as instruções:

```text
Você é um analista legislativo imparcial. Acima está o texto da matéria na forma em que foi votado, entre as marcas <texto_votado>.

Avalie o impacto distributivo desse texto para três perfis de brasileiro: pobre, classe média e rico. Antes de atribuir as notas, identifique quem ganha e quem perde: que grupo recebe o benefício direto (transferência de renda, acesso a serviço, direito novo, redução de carga), quem arca com o custo (tributo, restrição de direito, perda de benefício), e se o efeito é concentrado ou difuso. Matéria fiscal, tributária ou de gasto público quase sempre tem efeito distributivo, mesmo quando o texto é técnico e não nomeia nenhum grupo; só use notas próximas de 0 quando realmente não houver efeito identificável. Se o efeito for o mesmo para os três perfis, dê a mesma nota aos três.

Responda com um objeto JSON com os campos abaixo. Todo o raciocínio deve ficar dentro do campo "analise_distributiva":
- "analise_distributiva": quem ganha, quem perde, em até 3 frases
- "nota_pobre": número entre -1 e 1
- "justificativa_pobre": explicação em até 2 frases
- "nota_classe_media": número entre -1 e 1
- "justificativa_classe_media": explicação em até 2 frases
- "nota_rico": número entre -1 e 1
- "justificativa_rico": explicação em até 2 frases

Onde -1 significa claramente prejudicial a esse perfil, 0 significa neutro/não se aplica, e 1 significa claramente benéfico.
```

Nas 5 matérias que vieram da Câmara e receberam emendas do Senado, o documento traz dois blocos, `<texto_recebido>` e `<emendas_do_senado>`. Nesse caso, a primeira frase das instruções passa a ser "Acima estão o texto recebido da Câmara dos Deputados, entre as marcas <texto_recebido>, e as emendas que o Senado aprovou a ele, entre as marcas <emendas_do_senado>. O que foi votado é o texto recebido com essas emendas aplicadas.", e "desse texto" vira "do texto recebido tal como fica com as emendas aplicadas".

</details>

<details>
<summary>Prompt das emendas destacadas (versão <code>emenda-v1</code>, usada nas 29 notas publicadas)</summary>

Parte 1, o texto-base:

```text
Texto em discussão no Senado Federal do Brasil, na forma em que estava quando a emenda abaixo foi votada.

Tipo: {sigla} -- {tipo_descricao}
Identificação: {sigla} {numero}/{ano}
Ementa: "{ementa}"

<texto_base>
{texto-base, extraído do PDF e sem nomes de parlamentares}
</texto_base>
```

Parte 2, a emenda e as instruções:

```text
Você é um analista legislativo imparcial. Acima está o texto-base, entre as marcas <texto_base>. Abaixo está a parte normativa de uma emenda a esse texto, entre as marcas <emenda>; ela foi destacada para votação em separado.

<emenda>
{parte normativa da emenda}
</emenda>

Avalie o impacto distributivo de APROVAR a emenda, em relação ao texto-base, para três perfis de brasileiro: pobre, classe média e rico. A nota é da MUDANÇA que a emenda faz, não do texto-base: se a emenda melhora a situação de um perfil em relação ao texto-base, a nota dele é positiva; se piora, negativa; se não muda nada para ele, 0. Antes de atribuir as notas, identifique o que a emenda altera no texto-base, quem ganha e quem perde com essa alteração, e se o efeito é concentrado ou difuso. Matéria fiscal, tributária ou de gasto público quase sempre tem efeito distributivo, mesmo quando o texto é técnico e não nomeia nenhum grupo; só use notas próximas de 0 quando realmente não houver efeito identificável. Se o efeito for o mesmo para os três perfis, dê a mesma nota aos três.

Responda com um objeto JSON com os campos abaixo. Todo o raciocínio deve ficar dentro do campo "analise_distributiva":
- "analise_distributiva": o que a emenda muda, quem ganha, quem perde, em até 3 frases
- "nota_pobre": número entre -1 e 1
- "justificativa_pobre": explicação em até 2 frases
- "nota_classe_media": número entre -1 e 1
- "justificativa_classe_media": explicação em até 2 frases
- "nota_rico": número entre -1 e 1
- "justificativa_rico": explicação em até 2 frases

Onde -1 significa que aprovar a emenda é claramente prejudicial a esse perfil, 0 que não muda nada para ele, e 1 que é claramente benéfico.
```

Quando o texto-base é composto de dois documentos, o texto recebido da Câmara e as emendas do Senado, cada um vem com a sua marca (`<texto_recebido>` e `<emendas_do_senado>`), e a primeira frase cita as duas.

</details>

## Nove amostras por matéria

Cada matéria não é avaliada uma vez pelo LLM, e sim nove. Uma amostra é uma avaliação completa e independente: o mesmo texto e o mesmo prompt são enviados ao modelo, que devolve as notas e as justificativas. A nota publicada da matéria é a mediana das nove notas, e a justificativa publicada é a da amostra cuja nota é igual à mediana.

O motivo é que o LLM é um avaliador estocástico: avaliando duas vezes a mesma matéria com o mesmo prompt, as notas mudam. Num teste de repetição com 113 matérias, a diferença média no eixo do índice foi de 0,117, quase igual à causada por trocar a versão do prompt (0,152), e 7 matérias trocaram de sinal, o mesmo número da troca de versão. No resultado final, 10 dos 81 senadores elegíveis mudaram de grupo só por causa de qual avaliação tinha sido gravada. Como o rótulo de cada senador é publicado ao lado do nome de uma pessoa real, ele não pode depender do acaso de uma única resposta.

Nove amostras servem a três finalidades. A mediana é imune a uma amostra com nota absurda. Nove é ímpar, então a mediana é sempre a nota de uma amostra real, que tem justificativa própria. E várias amostras permitem medir o ruído: o pipeline sorteia, entre as nove, qual usar em cada matéria, refaz o índice milhares de vezes e só publica o rótulo do senador que se mantém no mesmo grupo em pelo menos 95% das repetições (ver 4.5). Com uma amostra por matéria isso não seria possível, e o rótulo não poderia ser publicado. A simulação feita antes da coleta indicou que, com 5 amostras, cerca de 14% dos senadores elegíveis ficariam na fronteira, e com 9 cerca de 6% (5 de 81). Por isso o projeto começou direto em nove, ao custo de nove chamadas por matéria.

## Limites

Alguns problemas só apareceram depois que os dados começaram a ser usados.

A listagem de matérias por ano não devolve tudo o que acaba sendo votado. Um projeto apresentado antes de 2023 e ainda em tramitação em 2024, por exemplo, não aparece na pesquisa de 2023 a 2026. O pipeline (jobs em Python) resolve isso comparando as matérias que aparecem nas votações com as que já foram carregadas, e buscando individualmente as que faltam pelo endpoint de detalhe de matéria.

O voto secreto não tem direção pública. A API o registra como "Votou", e esse é o valor mais frequente da base, mais que "Sim". Tratá-lo como ausência faria um senador presente parecer faltoso, então ele é uma categoria própria. Essas votações contam para a participação e ficam fora do índice, porque não há como saber para que lado o senador votou.

A API não informa liderança partidária nem distingue titular de suplente no momento do voto. A lista de senadores inclui todos os titulares e suplentes que já ocuparam a cadeira, e como suplentes votam de verdade quando substituem um titular, não dá para simplesmente removê-los. Por isso uma mesma UF pode aparecer com mais de três senadores.

## Por que essa base serve

Ela cobre o período inteiro da legislatura, traz o voto individual e é a fonte oficial, o que importa num projeto que rotula parlamentares. Os limites acima estão documentados, e nenhum deles impede que as perguntas sejam respondidas. A principal ressalva é que o impacto de cada matéria vem do julgamento de um LLM, sem equivalente oficial. A Análise discute o quanto isso limita as conclusões.
