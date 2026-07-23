import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import SERVER_ID, DATA_START, DATA_END, KNOWN_SERVERS
from app.data_loader import data_loader
from app.cluster_client import fetch_remote_summaries, fetch_remote_heatmaps

# 1. Configuração do ciclo de vida (Lifespan)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{SERVER_ID}] Iniciando servidor...")
    data_loader.load_data()  # Lê o arquivo CSV e guarda na RAM
    yield
    print(f"[{SERVER_ID}] Desligando servidor...")

# 2. Inicialização do FastAPI passando o lifespan configurado
app = FastAPI(
    title=f"Uber Query Service ({SERVER_ID})",
    lifespan=lifespan
)

# Montagem de arquivos estáticos para a interface Web Dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": f"Uber Query Service ({SERVER_ID}) está ativo. Acesse /docs para a API."}

# 3. Rota de Healthcheck: para verificar se a API está no ar
@app.get("/health")
def health():
    return {"status": "ok", "server_id": SERVER_ID}

# Rota de Metadados: retorna informações sobre a partição local e vizinhos
@app.get("/metadata")
def metadata():
    months_pt = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
        7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    month_name = months_pt.get(DATA_START.month, "local")
    partition_description = f"Dados de {month_name}/{DATA_START.year}"
    
    return {
        "server_id": SERVER_ID,
        "owns": {
            "date_start": DATA_START.strftime("%Y-%m-%d"),
            "date_end": DATA_END.strftime("%Y-%m-%d"),
            "partition_description": partition_description
        },
        "known_servers": KNOWN_SERVERS
    }

# 4. Rota Local: responde consultas sobre a partição local de dados
@app.get("/local/summary")
def local_summary(
    start_date: date = Query(..., description="Data inicial do período (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Data final do período (YYYY-MM-DD)"),
    base: str = Query(None, description="Código da base TLC (ex: B02512) - Opcional")
):
    # Validação: data de início não pode ser posterior à data de fim
    if start_date > end_date:
        raise HTTPException(
            status_code=400, 
            detail="A data inicial (start_date) não pode ser maior que a data final (end_date)."
        )
    
    # Chama o data_loader para filtrar o CSV carregado na memória
    resultado = data_loader.get_local_summary(start_date, end_date, base)
    
    return {
        "server_id": SERVER_ID,
        "scope": "local",
        "complete": True,
        "result": resultado
    }

# 5. Rota Distribuída: Coordenador de consultas globais
@app.get("/summary")
async def summary(
    start_date: date = Query(..., description="Data inicial do período (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Data final do período (YYYY-MM-DD)"),
    base: Optional[str] = Query(None, description="Código da base TLC (ex: B02512) - Opcional")
):
    if start_date > end_date:
        raise HTTPException(
            status_code=400, 
            detail="A data inicial (start_date) não pode ser maior que a data final (end_date)."
        )

    servers_contacted: List[str] = []
    failed_servers: List[str] = []
    results_to_aggregate: List[Dict[str, Any]] = []

    # 5.1 Processamento Local
    local_overlaps = not (end_date < DATA_START or start_date > DATA_END)
    if local_overlaps:
        local_result = data_loader.get_local_summary(start_date, end_date, base)
        results_to_aggregate.append(local_result)
        servers_contacted.append(SERVER_ID)

    # 5.2 Processamento Remoto Concorrente (httpx.AsyncClient + asyncio.gather)
    if KNOWN_SERVERS:
        remote_responses = await fetch_remote_summaries(KNOWN_SERVERS, start_date, end_date, base)
        for resp in remote_responses:
            s_id = resp["server_id"]
            if resp["success"]:
                if not resp["skipped"] and resp["result"] is not None:
                    results_to_aggregate.append(resp["result"])
                    if s_id and s_id not in servers_contacted:
                        servers_contacted.append(s_id)
                elif resp["skipped"]:
                    # Servidor ativo, mas sem dados no período pesquisado
                    if s_id and s_id not in servers_contacted:
                        servers_contacted.append(s_id)
            else:
                if s_id and s_id not in failed_servers:
                    failed_servers.append(s_id)

    # 5.3 Lógica de Agregação Matemática dos Resultados
    total_pickups = 0
    merged_base_counts: Dict[str, int] = {}
    first_pickups: List[str] = []
    last_pickups: List[str] = []

    for res in results_to_aggregate:
        total_pickups += res.get("pickup_count", 0)
        
        # Somar contagens de bases
        for b_code, count in res.get("base_counts", {}).items():
            merged_base_counts[b_code] = merged_base_counts.get(b_code, 0) + count
            
        fp = res.get("first_pickup")
        if fp:
            first_pickups.append(fp)
            
        lp = res.get("last_pickup")
        if lp:
            last_pickups.append(lp)

    first_pickup = min(first_pickups) if first_pickups else None
    last_pickup = max(last_pickups) if last_pickups else None
    is_complete = len(failed_servers) == 0

    return {
        "coordinator": SERVER_ID,
        "scope": "distributed",
        "complete": is_complete,
        "servers_contacted": sorted(servers_contacted),
        "failed_servers": sorted(failed_servers),
        "query": {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "base": base
        },
        "result": {
            "pickup_count": total_pickups,
            "base_counts": merged_base_counts,
            "first_pickup": first_pickup,
            "last_pickup": last_pickup
        }
    }

# 6. Rotas de Mapa de Calor (Heatmap)
@app.get("/local/heatmap")
def local_heatmap(
    start_date: date = Query(..., description="Data inicial do período (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Data final do período (YYYY-MM-DD)"),
    base: Optional[str] = Query(None, description="Código da base TLC (ex: B02512) - Opcional")
):
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="A data inicial (start_date) não pode ser maior que a data final (end_date)."
        )
    points = data_loader.get_local_heatmap(start_date, end_date, base)
    return {
        "server_id": SERVER_ID,
        "scope": "local",
        "complete": True,
        "points": points
    }

@app.get("/heatmap")
async def distributed_heatmap(
    start_date: date = Query(..., description="Data inicial do período (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Data final do período (YYYY-MM-DD)"),
    base: Optional[str] = Query(None, description="Código da base TLC (ex: B02512) - Opcional")
):
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="A data inicial (start_date) não pode ser maior que a data final (end_date)."
        )

    merged_grid: Dict[tuple, int] = {}
    servers_contacted: List[str] = []

    # 6.1 Processamento Local
    local_overlaps = not (end_date < DATA_START or start_date > DATA_END)
    if local_overlaps:
        local_points = data_loader.get_local_heatmap(start_date, end_date, base)
        for p in local_points:
            key = (p[0], p[1])
            merged_grid[key] = merged_grid.get(key, 0) + p[2]
        servers_contacted.append(SERVER_ID)

    # 6.2 Processamento Remoto Concorrente
    if KNOWN_SERVERS:
        remote_resps = await fetch_remote_heatmaps(KNOWN_SERVERS, start_date, end_date, base)
        for resp in remote_resps:
            if resp.get("success"):
                s_id = resp.get("server_id")
                if s_id and s_id not in servers_contacted:
                    servers_contacted.append(s_id)
                for p in resp.get("points", []):
                    key = (p[0], p[1])
                    merged_grid[key] = merged_grid.get(key, 0) + p[2]

    final_points = [[lat, lon, count] for (lat, lon), count in merged_grid.items()]

    return {
        "coordinator": SERVER_ID,
        "scope": "distributed",
        "servers_contacted": sorted(servers_contacted),
        "points": final_points
    }
