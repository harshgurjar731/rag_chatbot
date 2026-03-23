"""
Video Processing Pool Manager.

Spawns and monitors Video Worker Processes.
Follows the same architecture as ingestion_pool/main.py.
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
from config import VIDEO_POOL_SIZE, VIDEO_POOL_PORT, REDIS_HOST

HOSTNAME = socket.gethostname()
processes = []

# Initialize FastAPI app
app = FastAPI(title="Video Processing Pool Manager")

# Configure CORS policies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    print(f"[*] Spawning Video Worker...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", "video_worker.py"],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        return proc
    except Exception as e:
        print(f"[!] Failed to spawn video worker: {e}")
        return None

def main():
    print(f"[*] Video Processing Pool Manager starting on {HOSTNAME} with capacity {VIDEO_POOL_SIZE}")

    # Spawn initial workers
    for _ in range(VIDEO_POOL_SIZE):
        p = spawn_worker()
        if p:
            processes.append(p)

    # Start worker monitoring in background thread
    def monitor():
        try:
            while True:
                for i in range(len(processes)):
                    if processes[i].poll() is not None:
                        print(f"[!] Video Worker {i} died. Restarting...")
                        processes[i] = spawn_worker()
                time.sleep(2)
        except KeyboardInterrupt:
            print("[*] Video Processing Pool stopping...")
            for p in processes:
                p.terminate()

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    # Start FastAPI server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=VIDEO_POOL_PORT,
        log_level="info"
    )

# API Endpoints
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
    """Get video processing pool status."""
    active_workers = [p for p in processes if p.poll() is None]
    return {
        "hostname": HOSTNAME,
        "total_workers": len(processes),
        "active_workers": len(active_workers),
        "capacity": VIDEO_POOL_SIZE,
        "status": "running"
    }

@app.get("/redis/queue-length")
async def get_queue_length(queue_name: str = "video_processing:inbox"):
    """Get Redis queue length."""
    if not redis_client:
        return {"error": "Redis not connected"}
    try:
        length = redis_client.llen(queue_name)
        return {"queue": queue_name, "length": length}
    except Exception as e:
        return {"error": str(e)}

@app.get("/redis/queue-peek")
async def peek_queue(queue_name: str = "video_processing:inbox", count: int = 5):
    """Peek at Redis queue items."""
    if not redis_client:
        return {"error": "Redis not connected"}
    try:
        items = redis_client.lrange(queue_name, 0, count - 1)
        return {"queue": queue_name, "items": items, "count": len(items)}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    main()
