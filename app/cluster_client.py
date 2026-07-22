import asyncio
import httpx
from datetime import date, datetime
from typing import List, Dict, Any, Optional

async def fetch_node_metadata(client: httpx.AsyncClient, server_url: str) -> Optional[Dict[str, Any]]:
    """
    Consulta a rota GET /metadata de um servidor remoto.
    Retorna os metadados se for bem-sucedido ou None se falhar.
    """
    try:
        response = await client.get(f"{server_url.rstrip('/')}/metadata", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[ClusterClient] Erro ao buscar /metadata de {server_url}: {e}")
    return None

async def query_remote_node(
    client: httpx.AsyncClient,
    server_url: str,
    start_date: date,
    end_date: date,
    base: Optional[str]
) -> Dict[str, Any]:
    """
    Consulta o endpoint /local/summary de um nó remoto com otimização de metadados
    e tratamento de erros de rede (timeout, conexão recusada, erro HTTP).
    """
    server_url_clean = server_url.rstrip('/')
    
    # 1. Otimização: Tenta consultar os metadados do nó remoto para verificar sobreposição de datas
    metadata = await fetch_node_metadata(client, server_url_clean)
    
    server_id = None
    if metadata:
        server_id = metadata.get("server_id")
        owns = metadata.get("owns", {})
        try:
            node_start = datetime.strptime(owns.get("date_start"), "%Y-%m-%d").date()
            node_end = datetime.strptime(owns.get("date_end"), "%Y-%m-%d").date()
            
            # Se o período pesquisado NÃO sobrepõe o período do nó remoto, evitamos chamar /local/summary
            if end_date < node_start or start_date > node_end:
                return {
                    "server_id": server_id,
                    "server_url": server_url_clean,
                    "success": True,
                    "skipped": True,  # Nó não possui dados para esta faixa
                    "result": None
                }
        except Exception as e:
            print(f"[ClusterClient] Erro ao validar datas de {server_url_clean}: {e}")

    # Fallback dinâmico para ID do servidor baseado na URL (caso /metadata falhe antes da consulta)
    if not server_id:
        server_id = server_url_clean.replace("http://", "").replace("https://", "")

    # 2. Faz a chamada HTTP assíncrona para /local/summary do nó remoto
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }
    if base:
        params["base"] = base

    try:
        response = await client.get(
            f"{server_url_clean}/local/summary",
            params=params,
            timeout=3.0
        )
        if response.status_code == 200:
            data = response.json()
            returned_id = data.get("server_id", server_id)
            return {
                "server_id": returned_id,
                "server_url": server_url_clean,
                "success": True,
                "skipped": False,
                "result": data.get("result")
            }
        else:
            return {
                "server_id": server_id,
                "server_url": server_url_clean,
                "success": False,
                "skipped": False,
                "error": f"HTTP {response.status_code}"
            }
    except httpx.TimeoutException:
        print(f"[ClusterClient] Timeout ao consultar {server_url_clean}")
        return {
            "server_id": server_id,
            "server_url": server_url_clean,
            "success": False,
            "skipped": False,
            "error": "Timeout"
        }
    except (httpx.ConnectError, httpx.RequestError) as e:
        print(f"[ClusterClient] Falha de conexão ao consultar {server_url_clean}: {e}")
        return {
            "server_id": server_id,
            "server_url": server_url_clean,
            "success": False,
            "skipped": False,
            "error": f"ConnectionError ({type(e).__name__})"
        }
    except Exception as e:
        print(f"[ClusterClient] Erro inesperado ao consultar {server_url_clean}: {e}")
        return {
            "server_id": server_id,
            "server_url": server_url_clean,
            "success": False,
            "skipped": False,
            "error": str(e)
        }

async def fetch_remote_summaries(
    known_servers: List[str],
    start_date: date,
    end_date: date,
    base: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Dispara chamadas HTTP assíncronas concorrentes (paralelas) para todos os servidores conhecidos.
    """
    if not known_servers:
        return []

    async with httpx.AsyncClient() as client:
        tasks = [
            query_remote_node(client, server_url, start_date, end_date, base)
            for server_url in known_servers
        ]
        results = await asyncio.gather(*tasks)
        return list(results)
