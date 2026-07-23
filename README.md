# UNEB - LPIII: Sistema Distribuído de Consultas com Dataset Uber

Este repositório contém a implementação do trabalho prático da disciplina de **Linguagem de Programação III (LPIII)** na **UNEB**. 

O objetivo do projeto é construir um sistema distribuído de servidores HTTP usando **FastAPI** capaz de responder a consultas analíticas sobre corridas do Uber em Nova York (ano de 2014) de forma particionada. Nenhum servidor possui o dataset completo; em vez disso, cada nó é responsável por uma partição dos dados (ex: um mês específico) e coopera com os demais nós para resolver consultas globais distribuídas.

---

## Tecnologias Utilizadas
* **Linguagem:** Python 3.12+
* **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/)
* **Servidor ASGI:** [Uvicorn](https://www.uvicorn.org/)
* **Banco de Dados Local:** [SQLite](https://www.sqlite.org/) (com índices de busca otimizados nas colunas `datetime` e `base`)
* **Manipulação de Dados:** [Pandas](https://pandas.pydata.org/) (para carga inicial do CSV no SQLite)
* **Variáveis de Ambiente:** [python-dotenv](https://github.com/theofidry/django-dotenv-filename)
* **Cliente HTTP Assíncrono:** [HTTPX](https://www.python-httpx.org/) (para requisições concorrentes entre os nós)

---

## Estrutura do Projeto
```text
.
├── app/
│   ├── __init__.py
│   ├── cluster_client.py  # Cliente HTTP assíncrono (HTTPX) com pre-flight de metadados e resiliência
│   ├── config.py          # Gerenciamento de variáveis de ambiente e configurações
│   ├── data_loader.py     # Consultas SQL locais no SQLite e inicialização automática no startup
│   ├── init_db.py         # Script de carga inicial do CSV para o banco SQLite indexado
│   └── main.py            # Definição das rotas e inicialização do FastAPI
├── data/
│   ├── uber-raw-data-jun14.csv  # Dataset CSV local original
│   └── uber-jun14.db            # Banco SQLite local indexado (gerado automaticamente)
├── generate_mock_data.py   # Script auxiliar: gera CSVs leves para simulação local do cluster
├── run_cluster.sh          # Script auxiliar: inicia/para 3 nós locais para testes
├── test_cluster.py         # Script auxiliar: executa a bateria de testes automatizados do cluster
├── .env                   # Configurações do nó local
├── .env.example           # Exemplo de configuração de variáveis
├── requirements.txt       # Dependências do projeto
└── README.md              # Documentação oficial do projeto
```

---

## Configuração e Variáveis de Ambiente

O comportamento de cada servidor (nó) é definido através do arquivo `.env` localizado na raiz do projeto. Duplique o arquivo `.env.example` para `.env`:

```bash
cp .env.example .env
```

Campos configuráveis no `.env`:
* `SERVER_ID`: Identificador único do servidor (ex: `servidor_01`).
* `PORT`: Porta HTTP na qual o servidor irá rodar (ex: `8000`).
* `DATA_START` / `DATA_END`: O período (datas inclusive) que define os dados locais sob responsabilidade deste servidor (ex: `2014-06-01` e `2014-06-30`).
* `DATA_FILE_PATH`: Caminho relativo do arquivo CSV local correspondente à partição (ex: `data/uber-raw-data-jun14.csv`).
* `DATABASE_PATH`: Caminho do banco de dados SQLite local (ex: `data/uber-jun14.db`).
* `KNOWN_SERVERS`: Lista separada por vírgulas de outros servidores conhecidos no cluster (ex: `http://192.168.1.10:8000,http://192.168.1.15:8000`).

---

## Como Executar

### 1. Pré-requisitos e Instalação
Certifique-se de ter o Python 3 instalado. Criar e ativar o ambiente virtual:

```bash
# Criar o ambiente virtual
python3 -m venv .venv

# Ativar o ambiente virtual
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

---

### 🌐 Execução no Dia da Apresentação (1 Servidor por Equipe)

No dia do teste oficial em sala de aula (onde cada equipe roda em seu próprio computador):

1. **Atualize o arquivo `.env`** adicionando os IPs e portas das outras equipes na variável `KNOWN_SERVERS`.
2. **Suba o servidor da sua equipe:**

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Nota:** Se o arquivo de banco de dados SQLite (`.db`) ainda não existir no seu computador, o sistema irá criar e popular o banco automaticamente a partir do CSV no momento em que o servidor for iniciado!

---

### 🧪 Execução Local para Testes (Simulando 3 Nós na Mesma Máquina)

Caso queira testar o cluster completo sozinho na sua máquina antes da apresentação:

1. **Iniciar o Cluster Simulado (3 Nós nas portas 8001, 8002 e 8003):**
   ```bash
   ./run_cluster.sh start
   ```

2. **Rodar a Bateria de Testes Automatizados (Consulta distribuída e tolerância a falhas):**
   ```bash
   python3 test_cluster.py
   ```

3. **Parar o Cluster Simulado:**
   ```bash
   ./run_cluster.sh stop
   ```

---

## Endpoints da API

### `GET /health`
Verifica se o servidor está ativo.
* **Exemplo de Retorno:**
  ```json
  {
    "status": "ok",
    "server_id": "servidor_01"
  }
  ```

### `GET /metadata`
Retorna a partição de dados de responsabilidade do nó local e a lista de outros servidores conhecidos.
* **Exemplo de Retorno:**
  ```json
  {
    "server_id": "servidor_01",
    "owns": {
      "date_start": "2014-06-01",
      "date_end": "2014-06-30",
      "partition_description": "Dados de junho/2014"
    },
    "known_servers": [
      "http://192.168.1.10:8000",
      "http://192.168.1.15:8000"
    ]
  }
  ```

### `GET /local/summary`
Consulta os dados armazenados apenas no banco SQLite local deste nó. Não faz chamadas de rede para outros nós.
* **Parâmetros de Consulta:**
  * `start_date` (Obrigatório, `YYYY-MM-DD`): Data de início da busca.
  * `end_date` (Obrigatório, `YYYY-MM-DD`): Data de término da busca.
  * `base` (Opcional, `string`): Filtra por uma base TLC específica (ex: `B02512`).
* **Exemplo de Chamada:**
  `GET http://localhost:8000/local/summary?start_date=2014-06-01&end_date=2014-06-02&base=B02512`
* **Exemplo de Retorno:**
  ```json
  {
    "server_id": "servidor_01",
    "scope": "local",
    "complete": true,
    "result": {
      "pickup_count": 1800,
      "base_counts": {
        "B02512": 1800
      },
      "first_pickup": "2014-06-01 00:00:00",
      "last_pickup": "2014-06-02 23:48:00"
    }
  }
  ```

### `GET /summary` (Consulta Distribuída Coordenada)
Executa a consulta de forma **distribuída**. O servidor que recebe esta chamada atua como coordenador:
1. Valida se a data inicial não é maior que a data final.
2. Consulta sua partição local via SQLite se o intervalo da busca se sobrepor ao seu período.
3. Dispara requisições HTTP assíncronas concorrentes (via `HTTPX`) para a rota `/local/summary` dos outros nós do cluster.
4. Faz o roteamento inteligente: consulta os metadados do nó vizinho e ignora chamadas se as datas não se sobrepuserem.
5. Consolida todas as métricas de forma unificada e retorna a resposta global.

* **Exemplo de Chamada Sucesso (100% Completo):**
  `GET http://localhost:8000/summary?start_date=2014-04-01&end_date=2014-06-30`
* **Exemplo de Retorno:**
  ```json
  {
    "coordinator": "servidor_01",
    "scope": "distributed",
    "complete": true,
    "servers_contacted": [
      "servidor_01",
      "servidor_02",
      "servidor_03"
    ],
    "failed_servers": [],
    "query": {
      "start_date": "2014-04-01",
      "end_date": "2014-06-30",
      "base": null
    },
    "result": {
      "pickup_count": 665844,
      "base_counts": {
        "B02512": 32887,
        "B02598": 243403,
        "B02617": 184882,
        "B02682": 195324,
        "B02764": 9348
      },
      "first_pickup": "2014-04-01 00:05:58",
      "last_pickup": "2014-06-30 23:59:00"
    }
  }
  ```

* **Exemplo de Retorno com Falha Parcial (Tolerância a Erros):**
  Caso um servidor remoto esteja indisponível ou offline, o coordenador retorna os dados agregados dos nós disponíveis e marca `"complete": false`:
  ```json
  {
    "coordinator": "servidor_01",
    "scope": "distributed",
    "complete": false,
    "servers_contacted": [
      "servidor_01",
      "servidor_02"
    ],
    "failed_servers": [
      "http://192.168.1.20:8000"
    ],
    "query": {
      "start_date": "2014-04-01",
      "end_date": "2014-06-30",
      "base": null
    },
    "result": {
      "pickup_count": 2000,
      "base_counts": {
        "B02512": 300,
        "B02598": 1700
      },
      "first_pickup": "2014-04-01 00:05:58",
      "last_pickup": "2014-05-31 23:58:00"
    }
  }
  ```

---

## Estratégia de Particionamento e Resiliência

* **Particionamento por Mês:** O dataset de corridas do Uber (2014) é segmentado por mês. Cada nó gerencia seu próprio banco SQLite local.
* **Descoberta de Nós & Roteamento Inteligente:** O coordenador lê os servidores conhecidos através da lista `KNOWN_SERVERS`. Antes de realizar a consulta pesada de dados, o coordenador avalia se o período pesquisado possui interseção com as datas de responsabilidade do nó remoto.
* **Tolerância a Falhas:** Em caso de estouro de timeout, falha de rede ou indisponibilidade de um nó, o sistema registra o servidor em `failed_servers` e devolve a resposta agregada parcial garantindo a estabilidade da aplicação sem lançar exceções HTTP 500.
