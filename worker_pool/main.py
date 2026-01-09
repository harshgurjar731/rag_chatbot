import os
import time
import socket
import subprocess
import signal
import sys
import redis # Added redis import
from sqlalchemy.orm import Session
from services.db.models import init_db, Bot, BotStatus, WorkerPool
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

def get_db():
    return SessionLocal()

def update_pool_heartbeat(db: Session):
    pool = db.query(WorkerPool).filter(WorkerPool.id == HOSTNAME).first()
    if not pool:
        pool = WorkerPool(id=HOSTNAME, active_workers=len(processes))
        db.add(pool)
    else:
        pool.last_heartbeat = datetime.now(timezone.utc)
        pool.active_workers = len(processes)
    db.commit()

def stop_bot_process(bot_name):
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
    print(f"[*] Spawning worker for bot: {bot.bot_id}")
    env = os.environ.copy()
    env["BOT_NAME"] = bot.name
    env["BOT_ID"] = bot.bot_id
    env["DATASTORE_ID"] = bot.datastore_id
    # PYTHONPATH to include root so imports work
    env["PYTHONPATH"] = os.getcwd() 

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
            orphaned_bots = db.query(Bot).filter(Bot.pool_id == pool.id, Bot.status == BotStatus.ACTIVE).all()
            if orphaned_bots:
                print(f"[*] Releasing {len(orphaned_bots)} orphaned bots from {pool.id}")
                for bot in orphaned_bots:
                    bot.status = BotStatus.PENDING
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
    db = get_db()
    
    # Restore
    restore_active_bots(db)
    
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

if __name__ == "__main__":
    main()
