#!/usr/bin/env python3
import time
import requests
import subprocess
import sys

BASE_URLS = {
    "servidor_01": "http://localhost:8001",
    "servidor_02": "http://localhost:8002",
    "servidor_03": "http://localhost:8003"
}

def print_banner(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def test_health_and_metadata():
    print_banner("1. TESTANDO HEALTHCHECK E METADATOS (SQLITE)")
    for name, url in BASE_URLS.items():
        try:
            r = requests.get(f"{url}/health", timeout=2.0)
            assert r.status_code == 200, f"Health de {name} falhou: {r.status_code}"
            print(f"✅ [{name}] /health OK -> {r.json()}")
            
            r_meta = requests.get(f"{url}/metadata", timeout=2.0)
            assert r_meta.status_code == 200
            print(f"   [{name}] /metadata -> Partição: {r_meta.json()['owns']}")
        except Exception as e:
            print(f"❌ Erro ao conectar em {name} ({url}): {e}")
            sys.exit(1)

def test_distributed_summary_success():
    print_banner("2. TESTANDO CONSULTA DISTRIBUÍDA COM BANCO SQLITE (CLUSTER 100% ATIVO)")
    url = "http://localhost:8001/summary?start_date=2014-04-01&end_date=2014-06-30"
    print(f"Enviando GET para {url}...")
    r = requests.get(url, timeout=10.0)
    assert r.status_code == 200, f"Erro na consulta distribuída: {r.status_code}"
    
    data = r.json()
    print(f"Coordenador: {data['coordinator']}")
    print(f"Escopo: {data['scope']}")
    print(f"Completo: {data['complete']}")
    print(f"Servidores Contactados: {data['servers_contacted']}")
    print(f"Servidores Com Falha: {data['failed_servers']}")
    print(f"Total de Corridas Agregadas (pickup_count): {data['result']['pickup_count']}")
    print(f"Contagem por Base TLC: {data['result']['base_counts']}")
    print(f"Primeiro Registro (first_pickup): {data['result']['first_pickup']}")
    print(f"Último Registro (last_pickup): {data['result']['last_pickup']}")
    
    assert data["complete"] is True, "Deveria estar completo quando todos nós estão ativos"
    assert len(data["failed_servers"]) == 0, "Nenhum servidor deveria ter falhado"
    assert len(data["servers_contacted"]) == 3, "Os 3 servidores deveriam ter sido contactados"
    print("\n✅ Consulta distribuída via SQLite com sucesso comprovado!")

def test_fault_tolerance():
    print_banner("3. TESTANDO TOLERÂNCIA A FALHAS (DERRUBANDO SERVIDOR 03 NA PORTA 8003)")
    
    print("Simulando queda do servidor_03...")
    subprocess.run(["fuser", "-k", "8003/tcp"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(1)
    
    url = "http://localhost:8001/summary?start_date=2014-04-01&end_date=2014-06-30"
    print(f"Enviando GET para {url} (com servidor_03 offline)...")
    r = requests.get(url, timeout=5.0)
    assert r.status_code == 200, f"Deveria retornar 200 com partial response, mas deu {r.status_code}"
    
    data = r.json()
    print(f"Completo: {data['complete']} (Esperado: False)")
    print(f"Servidores Contactados: {data['servers_contacted']}")
    print(f"Servidores Com Falha: {data['failed_servers']}")
    print(f"Total Parcial de Corridas Agregadas: {data['result']['pickup_count']}")
    
    assert data["complete"] is False, "complete deve ser False quando um servidor cai"
    assert any("8003" in s or "servidor_03" in s for s in data["failed_servers"]), "servidor_03/8003 deve estar em failed_servers"
    assert data["result"]["pickup_count"] > 0, "Deveria retornar contagem parcial dos servidores ativos"
    print("\n✅ Tolerância a falhas testada e aprovada com sucesso!")

if __name__ == '__main__':
    print("Iniciando bateria de testes do cluster SQLite...")
    test_health_and_metadata()
    test_distributed_summary_success()
    test_fault_tolerance()
