# LPIII: Sistema Distribuído de Consultas com Dataset Uber

Este repositório contém a implementação do trabalho prático da disciplina de **Linguagem de Programação III (LPIII)** na **UNEB**. 

O objetivo do projeto é construir um sistema distribuído de servidores HTTP usando **FastAPI** capaz de responder a consultas analíticas sobre corridas do Uber em Nova York (ano de 2014) de forma particionada. Nenhum servidor possui o dataset completo; em vez disso, cada nó é responsável por uma partição dos dados (ex: um mês específico) e coopera com os demais nós para resolver consultas globais distribuídas.

---

## Tecnologias Utilizadas
* **Linguagem:** Python 3.12+
* **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/)
* **Servidor ASGI:** [Uvicorn](https://www.uvicorn.org/)
* **Manipulação de Dados:** [Pandas](https://pandas.pydata.org/)
* **Variáveis de Ambiente:** [python-dotenv](https://github.com/theofidry/django-dotenv-filename)
* **Cliente HTTP:** [HTTPX](https://www.python-httpx.org/) (para requisições assíncronas entre os nós)

---

## Estrutura do Projeto
```text
.
├── app/
│   ├── __init__.py
│   ├── config.py          # Gerenciamento de variáveis de ambiente e configurações
│   ├── data_loader.py     # Leitura e filtragem dos arquivos CSV locais na memória RAM
│   └── main.py            # Definição das rotas e inicialização do FastAPI
├── data/
│   └── uber-raw-data-jun14.csv  # Dataset local (exemplo para Junho/2014)
├── .env                   # Configurações do nó local (não commitado)
├── .env.example           # Exemplo de configuração de variáveis
├── requirements.txt       # Dependências do projeto
└── README.md              # Instruções do projeto
```

---

## Configuração e Variáveis de Ambiente

O comportamento de cada servidor (nó) é definido através de um arquivo `.env` localizado na raiz do projeto. Duplique o arquivo `.env.example` para `.env`:

```bash
cp .env.example .env
```

Campos configuráveis no `.env`:
* `SERVER_ID`: Identificador único do servidor (ex: `servidor_01`).
* `PORT`: Porta HTTP na qual o servidor irá rodar (ex: `8001`).
* `DATA_START` / `DATA_END`: O período (datas inclusive) que define os dados locais sob responsabilidade deste servidor (ex: `2014-06-01` e `2014-06-30`).
* `DATA_FILE_PATH`: Caminho relativo do arquivo CSV local correspondente à partição (ex: `data/uber-raw-data-jun14.csv`).
* `KNOWN_SERVERS`: Lista separada por vírgulas de outros servidores conhecidos no cluster (ex: `http://localhost:8002,http://localhost:8003`).

---

## Como Executar

### 1. Pré-requisitos
Certifique-se de ter o Python 3 instalado. Recomendamos utilizar um ambiente virtual (`venv`):

```bash
# Criar o ambiente virtual
python3 -m venv .venv

# Ativar o ambiente virtual
# No Linux/macOS:
source .venv/bin/activate
# No Windows:
.venv\Scripts\activate
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Iniciar o servidor local
```bash
python -m uvicorn app.main:app --port 8001 --reload
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

### `GET /metadata` (Requisito da Especificação)
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
Consulta os dados armazenados apenas na memória deste nó. Não faz chamadas para outros nós.
* **Parâmetros de Consulta:**
  * `start_date` (Obrigatório, `YYYY-MM-DD`): Data de início da busca.
  * `end_date` (Obrigatório, `YYYY-MM-DD`): Data de término da busca.
  * `base` (Opcional, `string`): Filtra por uma base TLC específica (ex: `B02512`).
* **Exemplo de chamada:**
  `GET http://localhost:8001/local/summary?start_date=2014-06-01&end_date=2014-06-30&base=B02512`
* **Exemplo de Retorno:**
  ```json
  {
    "server_id": "servidor_01",
    "scope": "local",
    "result": {
      "pickup_count": 32509,
      "base_counts": {
        "B02512": 32509
      },
      "first_pickup": "2014-06-01 00:00:00",
      "last_pickup": "2014-06-30 23:52:00"
    }
  }
  ```

### `GET /summary` (Requisito da Especificação)
Executa a consulta de forma **distribuída**. O servidor que recebe esta chamada atua como coordenador:
1. Valida os parâmetros locais.
2. Consulta sua própria partição local via `/local/summary`.
3. Dispara requisições HTTP assíncronas concorrentes para a rota `/local/summary` dos outros servidores conhecidos cujas partições de datas se sobrepõem ao intervalo pesquisado.
4. Consolida todas as métricas parciais de forma combinada e retorna a resposta final unificada.
* **Parâmetros de Consulta:** Os mesmos de `/local/summary`.

---

## Estratégia de Particionamento e Descoberta

* **Particionamento por Mês:** Para simular o ambiente distribuído, o dataset de corridas do Uber (2014) foi segmentado por mês. Cada nó do cluster assume a responsabilidade de gerenciar o arquivo CSV de um único mês (ex: servidor 1 gerencia abril, servidor 2 gerencia maio, servidor 3 gerencia junho, etc.).
* **Descoberta de Nós:** Cada nó conhece a existência e as portas de comunicação dos outros servidores do cluster por meio da lista configurada na variável `KNOWN_SERVERS` no `.env`.
