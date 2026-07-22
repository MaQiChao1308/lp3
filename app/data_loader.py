import os
import pandas as pd
from app.config import DATA_FILE_PATH, SERVER_ID

class DataLoader:
    def __init__(self):
        # Inicializa um DataFrame vazio para evitar erros caso os dados não carreguem
        self.df = pd.DataFrame(columns=['Date/Time', 'Lat', 'Lon', 'Base', 'datetime'])

    def load_data(self):
        """Lê o arquivo CSV local e o carrega na memória RAM."""
        if not DATA_FILE_PATH:
            print(f"[{SERVER_ID}] Erro: DATA_FILE_PATH não configurado.")
            return

        # Verifica se o arquivo CSV de fato existe no caminho indicado
        if not os.path.exists(DATA_FILE_PATH):
            print(f"[{SERVER_ID}] Erro: Arquivo de dados não encontrado em {DATA_FILE_PATH}")
            return

        print(f"[{SERVER_ID}] Carregando dados locais de: {DATA_FILE_PATH}...")
        try:
            # Lê o arquivo CSV
            self.df = pd.read_csv(DATA_FILE_PATH)
            
            # Converte a coluna Date/Time para o tipo datetime de forma rápida usando formato específico
            self.df['datetime'] = pd.to_datetime(self.df['Date/Time'], format="%m/%d/%Y %H:%M:%S", errors='coerce')
            
            # Remove registros com data inválida
            self.df = self.df.dropna(subset=['datetime'])
            
            print(f"[{SERVER_ID}] Carregamento concluído! {len(self.df)} registros carregados.")
        except Exception as e:
            print(f"[{SERVER_ID}] Falha ao carregar arquivo CSV: {e}")

    def get_local_summary(self, start_date, end_date, base=None):
        """Filtra e agrega os dados locais no período selecionado (start_date e end_date inclusive)."""
        if self.df.empty:
            return {
                "pickup_count": 0,
                "base_counts": {},
                "first_pickup": None,
                "last_pickup": None
            }

        # Filtra por intervalo de datas (comparando apenas a data YYYY-MM-DD, ignorando a hora)
        mask = (self.df['datetime'].dt.date >= start_date) & (self.df['datetime'].dt.date <= end_date)
        filtered_df = self.df[mask]

        # Se o cliente filtrou por uma base específica (ex: B02512)
        if base:
            filtered_df = filtered_df[filtered_df['Base'] == base]

        # Caso não haja nenhuma viagem no período/filtros selecionados
        if filtered_df.empty:
            return {
                "pickup_count": 0,
                "base_counts": {},
                "first_pickup": None,
                "last_pickup": None
            }

        # Agrega a contagem de viagens por base TLC
        base_counts = filtered_df['Base'].value_counts().to_dict()

        # Encontra a primeira e a última viagem no período
        first_dt = filtered_df['datetime'].min()
        last_dt = filtered_df['datetime'].max()

        return {
            "pickup_count": len(filtered_df),
            "base_counts": base_counts,
            "first_pickup": first_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "last_pickup": last_dt.strftime("%Y-%m-%d %H:%M:%S")
        }

# Instância global única para ser importada no restante do sistema
data_loader = DataLoader()
