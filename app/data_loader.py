import os
import sqlite3
from app.config import DATABASE_PATH, SERVER_ID

class DataLoader:
    def __init__(self):
        self.db_path = DATABASE_PATH

    def load_data(self):
        """Verifica se o banco de dados SQLite existe e está pronto; se não existir, cria e popula automaticamente."""
        if not os.path.exists(self.db_path):
            print(f"[{SERVER_ID}] Banco de dados não encontrado em {self.db_path}. Criando e populando banco SQLite automaticamente...")
            try:
                from app.init_db import init_db
                init_db()
            except Exception as e:
                print(f"[{SERVER_ID}] Erro ao inicializar banco de dados SQLite automaticamente: {e}")
                return

        print(f"[{SERVER_ID}] Conectado com sucesso ao banco de dados SQLite: {self.db_path}")

    def get_local_summary(self, start_date, end_date, base=None):
        """Filtra e agrega os dados locais no SQLite usando consultas SQL otimizadas por índice."""
        if not os.path.exists(self.db_path):
            # Se ainda não existir por algum motivo, tenta inicializar de forma defensiva
            try:
                from app.init_db import init_db
                init_db()
            except Exception:
                pass
                
        if not os.path.exists(self.db_path):
            return {
                "pickup_count": 0,
                "base_counts": {},
                "first_pickup": None,
                "last_pickup": None
            }

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Ajusta datas para cobrir o dia completo em formato ISO (YYYY-MM-DD HH:MM:SS)
        start_str = f"{start_date} 00:00:00"
        end_str = f"{end_date} 23:59:59"

        # 1. Consulta principal: contagem total, primeiro e último pickup no período
        query_main = """
            SELECT COUNT(*) as pickup_count,
                   MIN(datetime) as first_pickup,
                   MAX(datetime) as last_pickup
            FROM rides
            WHERE datetime >= ? AND datetime <= ?
        """
        params = [start_str, end_str]
        if base:
            query_main += " AND base = ?"
            params.append(base)

        cursor.execute(query_main, params)
        res_main = cursor.fetchone()

        pickup_count = res_main['pickup_count'] if res_main else 0
        if not res_main or pickup_count == 0:
            conn.close()
            return {
                "pickup_count": 0,
                "base_counts": {},
                "first_pickup": None,
                "last_pickup": None
            }

        # 2. Consulta para agregação de contagens por base TLC
        query_bases = """
            SELECT base, COUNT(*) as count
            FROM rides
            WHERE datetime >= ? AND datetime <= ?
        """
        params_bases = [start_str, end_str]
        if base:
            query_bases += " AND base = ?"
            params_bases.append(base)
        query_bases += " GROUP BY base"

        cursor.execute(query_bases, params_bases)
        res_bases = cursor.fetchall()

        base_counts = {row['base']: row['count'] for row in res_bases}

        conn.close()

        return {
            "pickup_count": pickup_count,
            "base_counts": base_counts,
            "first_pickup": res_main['first_pickup'],
            "last_pickup": res_main['last_pickup']
        }

    def get_local_heatmap(self, start_date, end_date, base=None, limit=2000):
        """Retorna pontos de latitude/longitude agrupados por grade geográfica para o mapa de calor."""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        start_str = f"{start_date} 00:00:00"
        end_str = f"{end_date} 23:59:59"

        query = """
            SELECT ROUND(lat, 3) as lat,
                   ROUND(lon, 3) as lon,
                   COUNT(*) as count
            FROM rides
            WHERE datetime >= ? AND datetime <= ? AND lat IS NOT NULL AND lon IS NOT NULL
        """
        params = [start_str, end_str]
        if base:
            query += " AND base = ?"
            params.append(base)

        query += " GROUP BY ROUND(lat, 3), ROUND(lon, 3) ORDER BY count DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [[row['lat'], row['lon'], row['count']] for row in rows]

# Instância global única para ser importada no restante do sistema
data_loader = DataLoader()
