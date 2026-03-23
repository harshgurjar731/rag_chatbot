"""
Ingestion Pool Manager.

Spawns and monitors Ingestion Helper Processes.
"""

import os
import time
import socket
import subprocess
import signal
import sys
import threading
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import INGESTION_POOL_SIZE, INGESTION_POOL_PORT, REDIS_HOST

HOSTNAME = socket.gethostname()
processes = []

# Initialize FastAPI app
app = FastAPI(title="Ingestion Pool Manager")

# Configure CORS policies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify domains in production: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print(f"[+] Connected to Redis at {REDIS_HOST}")
except Exception as e:
    print(f"[!] Redis connection failed: {e}")
    redis_client = None



def spawn_worker():
    print(f"[*] Spawning Ingestion Worker...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() 

    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", "ingestion_worker.py"],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        return proc
    except Exception as e:
        print(f"[!] Failed to spawn worker: {e}")
        return None

def main():
    print(f"[*] Ingestion Pool Manager starting on {HOSTNAME} with capacity {INGESTION_POOL_SIZE}")
    
    # Spawn initial workers
    for _ in range(INGESTION_POOL_SIZE):
        p = spawn_worker()
        if p:
            processes.append(p)
    
    # Start worker monitoring in background thread
    def monitor():
        try:
            while True:
                # Monitor and restart dead workers
                for i in range(len(processes)):
                    if processes[i].poll() is not None:
                        print(f"[!] Worker {i} died. Restarting...")
                        processes[i] = spawn_worker()
                time.sleep(2)
        except KeyboardInterrupt:
            print("[*] Ingestion Pool stopping...")
            for p in processes:
                p.terminate()
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    
    # Start FastAPI server with CORS enabled
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=INGESTION_POOL_PORT,
        log_level="info"
    )

# API Endpoints with CORS + Redis support
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    redis_status = "connected" if redis_client else "disconnected"
    return {
        "status": "healthy",
        "hostname": HOSTNAME,
        "active_workers": len([p for p in processes if p.poll() is None]),
        "redis": redis_status
    }

@app.get("/status")
async def get_status():
    """Get ingestion pool status."""
    active_workers = [p for p in processes if p.poll() is None]
    return {
        "hostname": HOSTNAME,
        "total_workers": len(processes),
        "active_workers": len(active_workers),
        "capacity": INGESTION_POOL_SIZE,
        "status": "running"
    }

@app.get("/redis/queue-length")
async def get_queue_length(queue_name: str = "ingestion:inbox"):
    """Get Redis queue length."""
    if not redis_client:
        return {"error": "Redis not connected"}
    try:
        length = redis_client.llen(queue_name)
        return {"queue": queue_name, "length": length}
    except Exception as e:
        return {"error": str(e)}

@app.get("/redis/queue-peek")
async def peek_queue(queue_name: str = "ingestion:inbox", count: int = 5):
    """Peek at Redis queue items."""
    if not redis_client:
        return {"error": "Redis not connected"}
    try:
        items = redis_client.lrange(queue_name, 0, count - 1)
        return {"queue": queue_name, "items": items, "count": len(items)}
    except Exception as e:
        return {"error": str(e)}

@app.post("/redis/queue-clear")
async def clear_queue(queue_name: str = "ingestion:inbox"):
    """Clear Redis queue."""
    if not redis_client:
        return {"error": "Redis not connected"}
    try:
        redis_client.delete(queue_name)
        return {"message": f"Queue '{queue_name}' cleared"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    main()
