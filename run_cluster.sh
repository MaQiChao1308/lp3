#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
LOG_DIR="$DIR/.logs"
PID_FILE="$DIR/.cluster.pid"

mkdir -p "$LOG_DIR"

start_cluster() {
    if [ -f "$PID_FILE" ]; then
        echo "Cluster já parece estar rodando (arquivo $PID_FILE existe). Utilize '$0 stop' primeiro ou '$0 status'."
        return 1
    fi

    echo "=========================================="
    echo "Iniciando Cluster de 3 Nós com SQLite..."
    echo "=========================================="

    # Garante que os datasets CSV existem
    python3 "$DIR/generate_mock_data.py"

    # Inicializa bancos SQLite para cada nó se não existirem
    echo "Inicializando banco SQLite do Servidor 01 (Abril)..."
    DATA_FILE_PATH=data/uber-raw-data-apr14.csv DATABASE_PATH=data/uber-apr14.db python3 -m app.init_db

    echo "Inicializando banco SQLite do Servidor 02 (Maio)..."
    DATA_FILE_PATH=data/uber-raw-data-may14.csv DATABASE_PATH=data/uber-may14.db python3 -m app.init_db

    echo "Inicializando banco SQLite do Servidor 03 (Junho)..."
    DATA_FILE_PATH=data/uber-raw-data-jun14.csv DATABASE_PATH=data/uber-jun14.db python3 -m app.init_db

    # Nó 1: Abril 2014 (Porta 8001)
    setsid env SERVER_ID=servidor_01 PORT=8001 DATA_START=2014-04-01 DATA_END=2014-04-30 \
    DATA_FILE_PATH=data/uber-raw-data-apr14.csv DATABASE_PATH=data/uber-apr14.db \
    KNOWN_SERVERS="http://localhost:8002,http://localhost:8003" \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > "$LOG_DIR/servidor_01.log" 2>&1 &
    PID1=$!

    # Nó 2: Maio 2014 (Porta 8002)
    setsid env SERVER_ID=servidor_02 PORT=8002 DATA_START=2014-05-01 DATA_END=2014-05-31 \
    DATA_FILE_PATH=data/uber-raw-data-may14.csv DATABASE_PATH=data/uber-may14.db \
    KNOWN_SERVERS="http://localhost:8001,http://localhost:8003" \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > "$LOG_DIR/servidor_02.log" 2>&1 &
    PID2=$!

    # Nó 3: Junho 2014 (Porta 8003)
    setsid env SERVER_ID=servidor_03 PORT=8003 DATA_START=2014-06-01 DATA_END=2014-06-30 \
    DATA_FILE_PATH=data/uber-raw-data-jun14.csv DATABASE_PATH=data/uber-jun14.db \
    KNOWN_SERVERS="http://localhost:8001,http://localhost:8002" \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 > "$LOG_DIR/servidor_03.log" 2>&1 &
    PID3=$!

    echo "$PID1 $PID2 $PID3" > "$PID_FILE"

    sleep 3
    echo "Servidor 01 (PID: $PID1) na porta 8001 -> Abril/2014 (SQLite: data/uber-apr14.db)"
    echo "Servidor 02 (PID: $PID2) na porta 8002 -> Maio/2014 (SQLite: data/uber-may14.db)"
    echo "Servidor 03 (PID: $PID3) na porta 8003 -> Junho/2014 (SQLite: data/uber-jun14.db)"
    echo "=========================================="
    echo "Cluster com SQLite iniciado! Logs salvos em $LOG_DIR/"
}

stop_cluster() {
    echo "Finalizando o cluster..."
    if [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
    fi
    fuser -k 8001/tcp 2>/dev/null
    fuser -k 8002/tcp 2>/dev/null
    fuser -k 8003/tcp 2>/dev/null
    echo "Cluster finalizado."
}

status_cluster() {
    echo "=== Status do Cluster ==="
    for port in 8001 8002 8003; do
        if curl -s "http://localhost:$port/health" > /dev/null; then
            echo "Porta $port: ONLINE"
        else
            echo "Porta $port: OFFLINE"
        fi
    done
}

case "$1" in
    start)
        start_cluster
        ;;
    stop)
        stop_cluster
        ;;
    restart)
        stop_cluster
        sleep 1
        start_cluster
        ;;
    status)
        status_cluster
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
