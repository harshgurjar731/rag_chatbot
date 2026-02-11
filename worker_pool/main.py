"""
Worker Pool Main Service

This module is the entry point for the worker pool service. It manages the lifecycle
of bot processes, including spawning, monitoring, and cleaning up worker processes.
It uses Redis for heartbeats and PostgreSQL for state management.
"""

import os
import time
import socket
import subprocess
import signal
import sys
import redis
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from sqlalchemy.orm import Session
from db.models import init_db, Bot, BotStatus, WorkerPool
import psutil
from datetime import datetime, timedelta, timezone

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
WORKER_POOL_SIZE = int(os.getenv("WORKER_POOL_SIZE", "5"))
HOSTNAME = socket.gethostname()

print(f"[*] Worker Pool Service starting on {HOSTNAME} with capacity {WORKER_POOL_SIZE}")

# Database Setup
SessionLocal = init_db()

# Active Processes: {bot_name: Popen}
processes = {}

# Redis Client for cleanup
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# Initialize FastAPI app
app = FastAPI(title="Worker Pool Manager")

# Configure CORS policies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify domains in production: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    """Create a new database session."""
    return SessionLocal()

def update_pool_heartbeat(db: Session):
    """
    Update the heartbeat for this worker pool in the database.
    
    Creates a new WorkerPool record if one doesn't exist for this host.
    
    Args:
        db (Session): Database session.
    """
    pool = db.query(WorkerPool).filter(WorkerPool.id == HOSTNAME).first()
    if not pool:
        pool = WorkerPool(id=HOSTNAME, active_workers=len(processes))
        db.add(pool)
    else:
        pool.last_heartbeat = datetime.now(timezone.utc)
        pool.active_workers = len(processes)
    db.commit()

def stop_bot_process(bot_name):
    """
    Stop and clean up a bot process.
    
    Terminates the process, cleans up Redis heartbeat keys, and removes from the processes dict.
    
    Args:
        bot_name (str): The name/ID of the bot to stop.
    """
    if bot_name in processes:
        print(f"[*] Stopping process for {bot_name}")
        proc = processes[bot_name]
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        
        # Cleanup Redis heartbeat immediately to prevent UI race conditions
        try:
            r.delete(f"bot:{bot_name}:heartbeat")
        except Exception as e:
            print(f"[!] Error cleaning up redis key for {bot_name}: {e}")

        del processes[bot_name]

def spawn_bot_process(bot):
    """
    Spawn a new worker process for a bot.
    
    Sets up the environment variables and spawns `worker_wrapper.py`.
    
    Args:
        bot (Bot): The bot database record.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    print(f"[*] Spawning worker for bot: {bot.bot_id}")
    env = os.environ.copy()
    env["BOT_NAME"] = bot.bot_name
    env["BOT_ID"] = bot.bot_id
    env["DATASTORE_ID"] = str(bot.datastore_id)
    # PYTHONPATH to include root so imports work
    env["PYTHONPATH"] = os.getcwd() 
    
    # Explicitly set project name for Phoenix/OTEL
    env["OTEL_PROJECT_NAME"] = bot.bot_name
    env["PHOENIX_PROJECT_NAME"] = bot.bot_name 

    try:
        # Run worker_wrapper.py
        # Assuming we are running from root /app
        proc = subprocess.Popen(
            ["python", "-u", "worker_wrapper.py"],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        processes[bot.bot_id] = proc
        return True
    except Exception as e:
        print(f"[!] Failed to spawn worker for {bot.bot_id}: {e}")
        return False

def check_process_health(db: Session):
    """
    Check active processes for health and restart if dead.
    
    Args:
        db (Session): Database session.
    """
    # Check for dead processes
    dead_bots = []
    for bot_id, proc in processes.items():
        if proc.poll() is not None:
            print(f"[!] Worker for {bot_id} died unexpectedly (Refresh to recover)")
            dead_bots.append(bot_id)
    
    for bot_id in dead_bots:
        # Auto-recover: restart
        print(f"[*] Attempting to recover {bot_id}")
        bot = db.query(Bot).filter(Bot.bot_id == bot_id).first()
        if bot:
            stop_bot_process(bot_id) # Clean up dict
            spawn_bot_process(bot)
        else:
            # Bot deleted from DB?
            del processes[bot_id]

def claim_pending_bots(db: Session):
    """
    Claim pending bots from the database and spawn them if capacity permits.
    
    Args:
        db (Session): Database session.
    """
    # Check if we have capacity
    if len(processes) >= WORKER_POOL_SIZE:
        return

    slots_available = WORKER_POOL_SIZE - len(processes)
    
    # Atomic claim (simplified for valid SQL in Postgres)
    # Get PENDING bots
    # We use a simple strategy: fetch pending, try to update. 
    # For robust production, SELECT ... FOR UPDATE SKIP LOCKED is better.
    
    try:
        # Find bots that are PENDING 
        # Use SKIP LOCKED to prevent race conditions significantly better
        pending_bots = db.query(Bot).filter(Bot.status == BotStatus.PENDING).limit(slots_available).with_for_update(skip_locked=True).all()
        
        for bot in pending_bots:
            # Try to lock/claim
            bot.status = BotStatus.ACTIVE
            bot.pool_id = HOSTNAME
            bot.updated_at = datetime.now(timezone.utc)
            db.commit() # Commit active status
            
            # Spawn
            if spawn_bot_process(bot):
                pass
            else:
                # Failed to spawn, revert
                bot.status = BotStatus.ERROR
                db.commit()
                
    except Exception as e:
        db.rollback()
        print(f"[!] Error claiming bots: {e}")

def restore_active_bots(db: Session):
    """
    On startup, find bots that were assigned to this pool (or are ACTIVE but have no running process).
    Use case: System restart.
    
    Args:
        db (Session): Database session.
    """
    # 1. Bots assigned to THIS pool that are marked ACTIVE
    my_bots = db.query(Bot).filter(Bot.pool_id == HOSTNAME, Bot.status == BotStatus.ACTIVE).all()
    print(f"[*] Found {len(my_bots)} active bots assigned to this pool from previous session.")
    
    for bot in my_bots:
        if len(processes) < WORKER_POOL_SIZE:
            spawn_bot_process(bot)
        else:
            print(f"[!] Cannot restore {bot.bot_id}, pool full!")

    # 2. Also consider "orphaned" bots? 
    # Complex. For now, we assume if pool_id matches, we restore.

def release_orphaned_bots(db: Session):
    """
    Find worker pools that haven't sent a heartbeat in > 10 seconds.
    Release their bots (set to PENDING) so they can be picked up by active pools.
    
    Args:
        db (Session): Database session.
    """
    # 10 seconds timeout (heartbeat is every 2s, so this is 5 misses)
    timeout = datetime.now(timezone.utc) - timedelta(seconds=10)
    
    try:
        dead_pools = db.query(WorkerPool).filter(WorkerPool.last_heartbeat < timeout).all()
        
        for pool in dead_pools:
            if pool.id == HOSTNAME:
                continue # monitoring self is done via heartbeat, but technically self shouldn't be dead if running this.
                
            print(f"[*] Detected dead worker pool: {pool.id} (Last heard: {pool.last_heartbeat})")
            
            # Release bots
            # Release bots
            # Fetch ALL bots assigned to this pool, not just ACTIVE ones.
            # If we don't clear pool_id for STOPPED/ERROR bots, we get FK violation on pool delete.
            orphaned_bots = db.query(Bot).filter(Bot.pool_id == pool.id).all()
            
            if orphaned_bots:
                print(f"[*] Releasing {len(orphaned_bots)} orphaned bots from {pool.id}")
                for bot in orphaned_bots:
                    # If it was active, it needs to be restarted elsewhere -> PENDING
                    if bot.status == BotStatus.ACTIVE:
                        bot.status = BotStatus.PENDING
                    
                    # Always clear the pool_id so we can delete the pool record
                    bot.pool_id = None
            
            # Remove the dead pool record
            db.delete(pool)
            db.commit()
            
    except Exception as e:
        print(f"[!] Error releasing orphaned bots: {e}")
        db.rollback()

def reconcile_active_processes(db: Session):
    """
    Check running processes against DB.
    Kill processes for bots that are DELETED (missing from DB) or STOPPED.
    
    Args:
        db (Session): Database session.
    """
    active_names = list(processes.keys())
    if not active_names:
        return

    try:
        # Fetch current state of these bots from DB
        bots_in_db = db.query(Bot).filter(Bot.bot_id.in_(active_names)).all()
        bots_in_db_map = {b.bot_id: b for b in bots_in_db}
        
        for bot_id in active_names:
            # Case 1: Bot deleted from DB
            if bot_id not in bots_in_db_map:
                print(f"[*] Found process for deleted bot: {bot_id}. Terminating.")
                stop_bot_process(bot_id)
                continue
            
            # Case 2: Bot is STOPPED
            bot = bots_in_db_map[bot_id]
            if bot.status == BotStatus.STOPPED:
                print(f"[*] Found process for stopped bot: {bot_id}. Terminating.")
                stop_bot_process(bot_id)
                
    except Exception as e:
        print(f"[!] Error reconciling processes: {e}")

def main():
    """
    Main loop for the worker pool service.
    """
    db = get_db()
    
    # Ensure pool exists in DB before we try to claim anything (prevents FK violation)
    update_pool_heartbeat(db)

    # Restore
    restore_active_bots(db)
    
    # Start worker pool monitoring in background thread
    def monitor_pool():
        try:
            while True:
                check_process_health(db)
                release_orphaned_bots(db)
                claim_pending_bots(db)
                update_pool_heartbeat(db)
                reconcile_active_processes(db)
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("[*] Worker Pool stopping...")
            for name in list(processes.keys()):
                stop_bot_process(name)
    
    monitor_thread = threading.Thread(target=monitor_pool, daemon=True)
    monitor_thread.start()
    
    # Start FastAPI server with CORS enabled
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )

# API Endpoints with CORS support
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    redis_status = "connected"
    try:
        r.ping()
    except:
        redis_status = "disconnected"
    
    return {
        "status": "healthy",
        "hostname": HOSTNAME,
        "active_bots": len(processes),
        "redis": redis_status
    }

@app.get("/status")
async def get_status():
    """Get worker pool status."""
    return {
        "hostname": HOSTNAME,
        "total_workers": len(processes),
        "active_workers": len(processes),
        "capacity": WORKER_POOL_SIZE,
        "status": "running",
        "bots": list(processes.keys())
    }

@app.get("/bots")
async def list_bots():
    """List active bot processes."""
    db = get_db()
    try:
        bots = db.query(Bot).filter(Bot.pool_id == HOSTNAME, Bot.status == BotStatus.ACTIVE).all()
        bot_list = [
            {
                "bot_id": bot.bot_id,
                "bot_name": bot.bot_name,
                "status": bot.status.value,
                "datastore_id": bot.datastore_id,
                "running": bot.bot_id in processes
            }
            for bot in bots
        ]
        return {"bots": bot_list, "total": len(bot_list)}
    finally:
        db.close()

@app.get("/redis/keys")
async def get_redis_keys(pattern: str = "bot:*"):
    """Get Redis keys matching pattern."""
    try:
        keys = r.keys(pattern)
        return {"pattern": pattern, "keys": keys, "count": len(keys)}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    main()
