import os
import sqlite3
import pandas as pd
from app.config import DATA_FILE_PATH, DATABASE_PATH

def init_db():
    if not DATA_FILE_PATH or not os.path.exists(DATA_FILE_PATH):
        print(f"Erro: Arquivo CSV fonte não encontrado em {DATA_FILE_PATH}")
        return

    # Garante que a pasta de destino exista
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    print(f"Criando/Conectando ao banco de dados SQLite em: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Se a tabela já existir, recria para garantir carga limpa
    cursor.execute("DROP TABLE IF EXISTS rides")
    cursor.execute("""
        CREATE TABLE rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            lat REAL,
            lon REAL,
            base TEXT NOT NULL
        )
    """)

    print(f"Lendo dados do CSV: {DATA_FILE_PATH}...")
    df = pd.read_csv(DATA_FILE_PATH)

    # Converte para datetime e formata para string ISO (YYYY-MM-DD HH:MM:SS)
    dt_series = pd.to_datetime(df['Date/Time'], format="%m/%d/%Y %H:%M:%S", errors='coerce')
    df['datetime'] = dt_series.dt.strftime("%Y-%m-%d %H:%M:%S")

    # Remove registros com data inválida
    df = df.dropna(subset=['datetime'])

    # Prepara o dataframe para inserção na tabela
    df_to_insert = pd.DataFrame({
        'datetime': df['datetime'],
        'lat': df['Lat'],
        'lon': df['Lon'],
        'base': df['Base']
    })

    print(f"Inserindo {len(df_to_insert)} registros no SQLite...")
    df_to_insert.to_sql('rides', conn, if_exists='append', index=False)

    print("Criando índices de busca rápida (datetime e base)...")
    cursor.execute("CREATE INDEX idx_rides_datetime ON rides(datetime);")
    cursor.execute("CREATE INDEX idx_rides_base ON rides(base);")
    cursor.execute("CREATE INDEX idx_rides_datetime_base ON rides(datetime, base);")

    conn.commit()
    conn.close()
    print(f"Banco de dados SQLite inicializado com sucesso em {DATABASE_PATH}!")

if __name__ == "__main__":
    init_db()
