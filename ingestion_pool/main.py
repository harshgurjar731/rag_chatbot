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
from config import INGESTION_POOL_SIZE

HOSTNAME = socket.gethostname()
processes = []

def spawn_worker():
    print(f"[*] Spawning Ingestion Worker...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() 

    try:
        proc = subprocess.Popen(
            ["python", "-u", "ingestion_worker.py"],
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
            
    try:
        while True:
            # Monitor and restart
            for i in range(len(processes)):
                if processes[i].poll() is not None:
                    print(f"[!] Worker {i} died. Restarting...")
                    processes[i] = spawn_worker()
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("[*] Ingestion Pool stopping...")
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    main()
