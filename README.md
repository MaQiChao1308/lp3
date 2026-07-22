# UNEB - LPIII: Sistema Distribuído de Consultas com Dataset Uber

Este repositório contém a implementação do trabalho prático da disciplina de **Linguagem de Programação III (LPIII)** na **UNEB**. 

O objetivo do projeto é construir um sistema distribuído de servidores HTTP usando **FastAPI** capaz de responder a consultas analíticas sobre corridas do Uber em Nova York (ano de 2014) de forma particionada. Nenhum servidor possui o dataset completo; em vez disso, cada nó é responsável por uma partição dos dados (ex: um mês específico) e coopera com os demais nós para resolver consultas globais distribuídas.

---

## 🛠️ Tecnologias Utilizadas
* **Linguagem:** Python 3.12+
* **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/)
* **Servidor ASGI:** [Uvicorn](https://www.uvicorn.org/)
* **Banco de Dados Local:** [SQLite](https://www.sqlite.org/) (com índices de busca em tempo $O(\log N)$)
* **Manipulação de Dados:** [Pandas](https://pandas.pydata.org/) (para conversão e inserção inicial no SQLite)
* **Variáveis de Ambiente:** [python-dotenv](https://github.com/theofidry/django-dotenv-filename)
* **Cliente HTTP Assíncrono:** [HTTPX](https://www.python-httpx.org/) (para requisições concorrentes entre os nós)

---

## 📂 Estrutura do Projeto
```text
.
├── app/
│   ├── __init__.py
│   ├── cluster_client.py  # Cliente HTTP assíncrono (HTTPX) para consulta remota aos nós
│   ├── config.py          # Gerenciamento de variáveis de ambiente e configurações
│   ├── data_loader.py     # Consultas SQL locais no SQLite indexado
│   ├── init_db.py         # Script de carga inicial do CSV para o banco SQLite
│   └── main.py            # Definição das rotas e inicialização do FastAPI
├── data/
│   ├── uber-raw-data-jun14.csv  # Dataset CSV local (exemplo para Junho/2014)
│   └── uber-jun14.db            # Banco SQLite local indexado (gerado pelo init_db.py)
├── .env                   # Configurações do nó local
├── .env.example           # Exemplo de configuração de variáveis
├── requirements.txt       # Dependências do projeto
└── README.md              # Instruções do projeto
```

---

## ⚙️ Configuração e Variáveis de Ambiente

O comportamento de cada servidor (nó) é definido através de um arquivo `.env` localizado na raiz do projeto. Duplique o arquivo `.env.example` para `.env`:

```bash
cp .env.example .env
```

Campos configuráveis no `.env`:
* `SERVER_ID`: Identificador único do servidor (ex: `servidor_01`).
* `PORT`: Porta HTTP na qual o servidor irá rodar (ex: `8001`).
* `DATA_START` / `DATA_END`: O período (datas inclusive) que define os dados locais sob responsabilidade deste servidor (ex: `2014-06-01` e `2014-06-30`).
* `DATA_FILE_PATH`: Caminho relativo do arquivo CSV local correspondente à partição (ex: `data/uber-raw-data-jun14.csv`).
* `DATABASE_PATH`: Caminho do banco de dados SQLite local (ex: `data/uber-jun14.db`).
* `KNOWN_SERVERS`: Lista separada por vírgulas de outros servidores conhecidos no cluster (ex: `http://localhost:8002,http://localhost:8003`).

---

## 🚀 Como Executar

### 1. Pré-requisitos
Certifique-se de ter o Python 3 instalado. Criar e ativar o ambiente virtual:

```bash
# Criar o ambiente virtual
python3 -m venv .venv

# Ativar o ambiente virtual
source .venv/bin/activate
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Inicializar o Banco de Dados SQLite (Seed)
Antes de rodar a API pela primeira vez, execute o script para converter o CSV em um banco SQLite indexado:
```bash
python -m app.init_db
```

### 4. Iniciar o servidor local
```bash
python -m uvicorn app.main:app --port 8001 --reload
```
*(Ou acesse a documentação Swagger interativa em `http://localhost:8001/docs`)*

---

## 📡 Endpoints da API

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
Retorna os dados que o servidor possui e a lista de outros servidores conhecidos do cluster.
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
      "http://localhost:8002",
      "http://localhost:8003"
    ]
  }
  ```

### `GET /local/summary`
Consulta os dados armazenados apenas no banco local deste nó. Não faz chamadas de rede para outros nós.
* **Parâmetros de Consulta:**
  * `start_date` (Obrigatório, `YYYY-MM-DD`): Data de início da busca.
  * `end_date` (Obrigatório, `YYYY-MM-DD`): Data de término da busca.
  * `base` (Opcional, `string`): Filtra por uma base TLC específica (ex: `B02512`).
* **Exemplo de Chamada:**
  `GET http://localhost:8001/local/summary?start_date=2014-06-01&end_date=2014-06-02&base=B02512`
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
4. Faz o roteamento inteligente: se a data pesquisada não intersectar o período de um nó vizinho, a chamada é ignorada de forma otimizada.
5. Consolida todas as métricas de forma unificada e retorna a resposta global.

* **Exemplo de Chamada Sucesso (100% Completo):**
  `GET http://localhost:8001/summary?start_date=2014-04-01&end_date=2014-06-30`
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
      "pickup_count": 145020,
      "base_counts": {
        "B02512": 32100,
        "B02598": 54200,
        "B02617": 58720
      },
      "first_pickup": "2014-04-01 00:00:00",
      "last_pickup": "2014-06-30 23:59:00"
    }
  }
  ```

* **Exemplo de Retorno com Falha Parcial (Tolerância a Erros):**
  Caso um servidor remoto (ex: `servidor_03`) esteja indisponível ou offline, o coordenador retorna os dados agregados dos nós disponíveis e marca `"complete": false`:
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
      "servidor_03"
    ],
    "query": {
      "start_date": "2014-04-01",
      "end_date": "2014-06-30",
      "base": null
    },
    "result": {
      "pickup_count": 92300,
      "base_counts": {
        "B02512": 21000,
        "B02598": 71300
      },
      "first_pickup": "2014-04-01 00:00:00",
      "last_pickup": "2014-05-31 23:58:00"
    }
  }
  ```

---

## 🌐 Estratégia de Particionamento e Descoberta

* **Particionamento por Mês:** O dataset de corridas do Uber (2014) é segmentado por mês. Cada nó gerencia seu próprio arquivo de dados ou banco SQLite local (ex: servidor 1 gerencia abril, servidor 2 gerencia maio, servidor 3 gerencia junho, etc.).
* **Descoberta de Nós & Roteamento Inteligente:** O coordenador lê os servidores conhecidos através da lista `KNOWN_SERVERS`. Antes de consultar os outros nós, o coordenador analisa se o período pesquisado se sobrepõe à partição do nó vizinho, evitando tráfego de rede desnecessário.
