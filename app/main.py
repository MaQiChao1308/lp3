from contextlib import asynccontextmanager
from datetime import date
from fastapi import FastAPI, HTTPException, Query
from app.config import SERVER_ID
from app.data_loader import data_loader

# 1. Configuração do ciclo de vida (Lifespan)
# O código antes do 'yield' roda assim que o servidor liga.
# O código depois do 'yield' roda quando o servidor é desligado.
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

# 3. Rota de Healthcheck: para verificar se a API está no ar
@app.get("/health")
def health():
    return {"status": "ok", "server_id": SERVER_ID}

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
        "result": resultado
    }
