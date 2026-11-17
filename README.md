# Futebol de Bairro

Aplicação local para encontrar campos, organizar partidas informais e acompanhar confirmações de presença. Usa SQLite para os dados operacionais, MongoDB Atlas para respostas brutas das APIs e DuckDB para indicadores. Não precisa de Docker nem de instalação de banco local.

## Requisitos

- Python 3.11 ou superior (o ambiente atual tem Python 3.14)
- Node.js 20 ou superior (o ambiente atual tem Node.js 24)
- Uma URI configurada no MongoDB Atlas e acesso à internet para gravar dados brutos

## Configuração do MongoDB Atlas

1. Crie um cluster no MongoDB Atlas, um usuário de banco e uma regra de acesso de rede para o IP que usará a aplicação.
2. Se ainda não existir `.env`, copie `.env.example` para `.env`. Substitua `MONGO_URL` pela URI fornecida em **Connect → Drivers → Python**. Se `.env` já existir, edite essa configuração e confirme `SQLITE_PATH=data/football.sqlite` e `DUCKDB_PATH=data/analytics.duckdb`. Se a senha contiver caracteres especiais, use a senha codificada para URI indicada pelo Atlas.
3. Nunca compartilhe nem faça commit do `.env`.

Se o Atlas estiver fora do ar, a aplicação ainda permite usar o catálogo local, criar partidas e confirmar presença. Dados brutos de novas consultas não serão gravados até a conexão voltar; a falha aparece no log do backend e em `/api/health`.

Antes da importação, valide a URI do Atlas sem exibi-la no terminal:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.check_mongo
```

## Instalar e iniciar no PowerShell

Abra um PowerShell na pasta do projeto. O ambiente não precisa ser ativado, o que evita a política que bloqueia `npm.ps1`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configure a URI Atlas no `.env`; depois execute:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd --prefix frontend install
```

Abra dois terminais PowerShell na pasta do projeto. No primeiro, inicie a API:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

No segundo, inicie o frontend:

```powershell
npm.cmd --prefix frontend run dev
```

Abra <http://localhost:5173>. A documentação interativa da API fica em <http://localhost:8000/docs>. Para parar, pressione `Ctrl+C` nos dois terminais.

## Catálogo e integração

Para os módulos Python executados com `-m`, use o diretório `backend` como pasta atual. Para importar campos OpenStreetMap e guardar a resposta bruta no Atlas:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.import_osm
.\.venv\Scripts\python.exe -m app.export_knime_inputs
```

Execute o fluxo visual KNIME conforme [knime/README.md](knime/README.md) e importe suas saídas:

```powershell
.\.venv\Scripts\python.exe -m app.load_knime_outputs
```

Os arquivos SQLite e DuckDB ficam em `data/`. Campos de demonstração em São Paulo são sintéticos e estão identificados na interface; configure `DEMO_CITY`, `DEMO_REGION`, `DEMO_COUNTRY`, `DEMO_TIMEZONE` e `OVERPASS_BBOX` antes de iniciar para outra cidade.

## Funcionalidades

- Pesquisar campos e ver sua localização no mapa OpenStreetMap.
- Adicionar ou corrigir campos pelo catálogo.
- Criar partidas futuras com capacidade, confirmar presença e sair.
- Consultar previsão horária do Open-Meteo para o local e horário.
- Visualizar indicadores consolidados pelo KNIME e armazenados no DuckDB.

## Limitações

- Não há contas nem autenticação; partidas e presenças são compartilhadas entre visitantes.
- O sistema não reserva campos. A organização deve verificar disponibilidade e condições de uso.
- MongoDB Atlas requer configuração externa de conta, usuário e acesso de rede.
- Se o computador estiver totalmente sem internet, as APIs meteorológica e OpenStreetMap e a gravação Atlas não estarão disponíveis; os dados locais continuam acessíveis.
