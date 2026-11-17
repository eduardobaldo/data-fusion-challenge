# Executar a integração no KNIME

O workflow usa arquivos CSV exportados do SQLite, transforma o catálogo e calcula indicadores; o carregador Python grava o catálogo de volta no SQLite e os indicadores no DuckDB.

## 1. Gerar ou atualizar as entradas

Na raiz do repositório, abra o PowerShell e rode:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.export_knime_inputs
```

Isso cria `data/raw/venues.csv`, `data/raw/matches.csv` e `data/raw/osm_latest.json`. A conexão Atlas não é necessária para exportar os dois CSVs. No ambiente atual, `matches.csv` tem uma partida demonstrativa, capacidade 10 e uma presença; `venues.csv` contém os campos disponíveis em São Paulo.

## 2. Criar o workflow

1. Abra o **KNIME Analytics Platform** e escolha o workspace.
2. No Explorer, clique com o botão direito em **LOCAL**, escolha **New Workflow**, nomeie `futebol-de-bairro-integration` e abra-o.
3. Nos exemplos abaixo, use a raiz do projeto como base. No computador desta equipe, ela é `C:\Users\aluno\Desktop\Eduardo 02.2026\Integração de Dados\09112026\desafio_data_fusion`. Se o projeto estiver em outro local, ajuste os caminhos no seletor de arquivos do KNIME.

O workflow terá dois ramos independentes:

```text
CSV Reader (venues) → Duplicate Row Filter → CSV Writer (venues limpos)
CSV Reader (matches) → GroupBy → Column Renamer → Expression → Column Filter → CSV Writer (métricas)
```

## 3. Ramo do catálogo de campos

1. Pesquise **CSV Reader** no Node Repository, arraste para o canvas e configure o arquivo `data/raw/venues.csv`. Use **Local File System**, separador vírgula e a primeira linha como nomes das colunas. Confira na prévia que aparecem `osm_type`, `osm_id`, `name`, `latitude`, `longitude`, `address`, `city`, `region` e `source`.
2. Conecte um **Duplicate Row Filter**. Na configuração de duplicidade, selecione as colunas `osm_type` e `osm_id` como chave e mantenha uma linha por chave. Isso mantém distintos os elementos `node`, `way` ou `relation` que tenham o mesmo número OSM.
3. Conecte um **CSV Writer**. Defina a saída como `data/processed/venues.csv`, com cabeçalho, separador vírgula e codificação UTF-8. A tabela de entrada do projeto já rejeita coordenadas ausentes, então não precisa de um filtro adicional de linhas.
4. Execute os três nós em ordem, usando botão direito → **Execute** em cada um. Confirme que o Writer terminou sem erro e que o arquivo de saída existe.

## 4. Ramo das métricas

1. Adicione outro **CSV Reader** e selecione `data/raw/matches.csv`. Confirme que `id`, `capacity` e `attendee_count` foram interpretados como números; se aparecerem como texto, ajuste o tipo na configuração do leitor.
2. Conecte **GroupBy**. Na seção **Groups**, selecione `city`. Em agregações manuais, defina `id` → **Count**, `attendee_count` → **Sum** e `capacity` → **Sum**. Execute e verifique que há uma linha para cada cidade.
3. Conecte **Column Renamer** e renomeie as três colunas de agregação para `partidas_total`, `participantes_total` e `capacidade_total`. O nome que o GroupBy atribui pode variar conforme a opção de nomeação; escolha as colunas pelo nome original e operação aplicada.
4. Conecte o nó atual **Expression** (não o antigo **Column Expressions (legacy)**). Adicione a expressão `100.0 * $participantes_total / $capacidade_total`; configure a saída para criar uma nova coluna numérica chamada `ocupacao_media`. No nó **Expression**, a referência termina no nome da coluna, sem um `$` final. A capacidade de uma partida é sempre maior que zero. Se o arquivo não contiver partidas, o ramo não terá linha de métrica para calcular.
5. Conecte **Column Filter** e mantenha apenas `city`, `partidas_total`, `participantes_total` e `ocupacao_media`. Não inclua `capacidade_total` na saída final.
6. Conecte um **CSV Writer** com saída `data/processed/metrics.csv`, cabeçalho, vírgula e UTF-8. Execute os nós em ordem e confira a prévia/arquivo: com os dados demonstrativos atuais, as métricas esperadas são 1 partida, 1 participante e 10% de ocupação.

O KNIME atual usa a linguagem de expressões para o nó **Expression**; a forma curta de referenciar colunas é `$nome_da_coluna` (sem `$` final). A documentação oficial descreve a sintaxe, o editor e a saída de novas colunas. [Guia de expressões do KNIME](https://docs.knime.com/ap/latest/knime_expressions_guide/index.html)

## 5. Carregar as saídas no SQLite e DuckDB

Feche os CSVs em outros programas, se estiverem abertos. No PowerShell, ainda dentro de `backend`, rode:

```powershell
.\.venv\Scripts\python.exe -m app.load_knime_outputs
```

O carregador atualiza os campos no SQLite sem duplicar chaves OSM e substitui as métricas no DuckDB. Não é necessário iniciar o backend para rodar este comando. Com a API aberta, atualize a página para ver os indicadores novos.

## Solução de problemas

- **CSV Reader não encontra o arquivo:** use o caminho absoluto no seletor KNIME. O caminho relativo é relativo ao workflow, não necessariamente à raiz do repositório.
- **As colunas numéricas aparecem como texto:** no leitor, escolha o tipo numérico para as colunas indicadas; se necessário, adicione **String to Number** antes do GroupBy.
- **O Writer não sobrescreve o resultado:** feche o CSV em Excel/LibreOffice e execute o Writer novamente.
- **O carregador diz que faltam saídas:** confirme que ambos os Writers criaram `data/processed/venues.csv` e `data/processed/metrics.csv` na pasta `data` da raiz do repositório.
