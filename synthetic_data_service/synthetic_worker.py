"""
Synthetic Data Worker Process.

This script runs as a standalone worker process managed by the synthetic data service.
It listens for data generation/curation jobs on Redis (synthetic_data:inbox), 
processes them using synthetic-data-kit, and manages the lifecycle of generation tasks.
"""

import os
import redis
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='[*] %(message)s')
logger = logging.getLogger("SyntheticWorker")

# synthetic-data-kit imports
from synthetic_data_kit.core.create import process_file
from synthetic_data_kit.core.curate import curate_qa_pairs
from synthetic_data_kit.utils.config import load_config

# Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
INBOX_KEY = "synthetic_data:inbox"
DEFAULT_CONFIG_PATH = Path("/app/synthetic-data-kit/configs/config.yaml")

# Redis Connection
try:
    r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    logger.info(f"Connected to Redis at {REDIS_HOST}")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    exit(1)

async def handle_generate_qa(job_data: dict):
    input_file = job_data.get("input_file")
    output_dir = job_data.get("output_dir", "/app/data/generated")
    num_pairs = job_data.get("num_pairs")
    
    logger.info(f"Starting QA Generation for {input_file}")
    
    try:
        output_path = await asyncio.to_thread(
            process_file,
            file_path=input_file,
            output_dir=output_dir,
            config_path=DEFAULT_CONFIG_PATH,
            content_type="qa",
            num_pairs=num_pairs,
            verbose=True
        )
        logger.info(f"QA Generation complete! Output: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"QA Generation failed: {e}")
        raise e

async def handle_generate_summary(job_data: dict):
    input_file = job_data.get("input_file")
    output_dir = job_data.get("output_dir", "/app/data/generated")
    
    logger.info(f"Starting Summary Generation for {input_file}")
    
    try:
        output_path = await asyncio.to_thread(
            process_file,
            file_path=input_file,
            output_dir=output_dir,
            config_path=DEFAULT_CONFIG_PATH,
            content_type="summary",
            verbose=True
        )
        logger.info(f"Summary Generation complete! Output: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Summary Generation failed: {e}")
        raise e

async def handle_generate_cot(job_data: dict):
    input_file = job_data.get("input_file")
    output_dir = job_data.get("output_dir", "/app/data/generated")
    num_pairs = job_data.get("num_pairs")
    
    logger.info(f"Starting CoT Generation for {input_file}")
    
    try:
        output_path = await asyncio.to_thread(
            process_file,
            file_path=input_file,
            output_dir=output_dir,
            config_path=DEFAULT_CONFIG_PATH,
            content_type="cot",
            num_pairs=num_pairs,
            verbose=True
        )
        logger.info(f"CoT Generation complete! Output: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"CoT Generation failed: {e}")
        raise e

async def handle_curate_qa(job_data: dict):
    input_file = job_data.get("input_file")
    output_path = job_data.get("output_path") # Optional specific file path
    output_dir = job_data.get("output_dir", "/app/data/curated") # Fallback dir
    threshold = job_data.get("threshold", 7.0)
    
    logger.info(f"Starting QA Curation for {input_file} with threshold {threshold}")

    if not output_path:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_path = os.path.join(output_dir, f"{base_name}_cleaned.json")

    try:
        final_path = await asyncio.to_thread(
            curate_qa_pairs,
            input_path=input_file,
            output_path=output_path,
            threshold=threshold,
            config_path=DEFAULT_CONFIG_PATH,
            verbose=True
        )
        logger.info(f"Curation complete! Output: {final_path}")
        return final_path
    except Exception as e:
        logger.error(f"Curation failed: {e}")
        raise e

async def message_loop():
    logger.info(f"Synthetic Worker listening on {INBOX_KEY}")
    
    while True:
        try:
            # Blocking pop from Redis list
            result = r.blpop(INBOX_KEY, timeout=1)
            
            if result:
                _, message_json = result
                job_data = json.loads(message_json)
                job_type = job_data.get("job_type")
                
                logger.info(f"Received job: {job_type}")
                
                try:
                    if job_type == "generate_qa":
                        await handle_generate_qa(job_data)
                    elif job_type == "generate_summary":
                        await handle_generate_summary(job_data)
                    elif job_type == "generate_cot":
                        await handle_generate_cot(job_data)
                    elif job_type == "curate_qa":
                        await handle_curate_qa(job_data)
                    else:
                        logger.warning(f"Unknown job type: {job_type}")
                except Exception as e:
                    logger.error(f"Job processing failed: {e}")
                    # Could implement dlq or retry logic here
                    
            else:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(message_loop())
