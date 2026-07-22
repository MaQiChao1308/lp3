import os
from datetime import datetime
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

SERVER_ID = os.getenv("SERVER_ID", "servidor_01")
PORT = int(os.getenv("PORT", "8001"))

# Converte as strings de data do .env em objetos date do Python
DATA_START = datetime.strptime(os.getenv("DATA_START", "2014-06-01"), "%Y-%m-%d").date()
DATA_END = datetime.strptime(os.getenv("DATA_END", "2014-06-30"), "%Y-%m-%d").date()

# Caminho do arquivo CSV de dados locais
DATA_FILE_PATH = os.getenv("DATA_FILE_PATH", "data/uber-raw-data-jun14.csv")

# Caminho do banco de dados SQLite local
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/uber-jun14.db")

# Processa a string de servidores conhecidos em uma lista
KNOWN_SERVERS_STR = os.getenv("KNOWN_SERVERS", "")
KNOWN_SERVERS = [
    s.strip() for s in KNOWN_SERVERS_STR.split(",") if s.strip()
] if KNOWN_SERVERS_STR else []