# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.
# Supports both vLLM and API endpoint (including OpenAI-compatible) providers
from typing import List, Dict, Any, Optional, Union, Tuple
import requests
import json
import time
import os
import logging
import asyncio
from pathlib import Path

from synthetic_data_kit.utils.config import load_config, get_openai_config, get_azure_openai_config, get_llm_provider

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import OpenAI, but handle case where it's not installed
try:
    from openai import OpenAI, AzureOpenAI
    from openai.types.chat import ChatCompletion
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. To use API endpoint provider, install with 'pip install openai>=1.0.0'")

class LLMClient:
    def __init__(self, 
                 config_path: Optional[Path] = None,
                 provider: Optional[str] = None,
                 api_base: Optional[str] = None, 
                 api_key: Optional[str] = None,
                 model_name: Optional[str] = None,
                 max_retries: Optional[int] = None,
                 retry_delay: Optional[float] = None):
        """Initialize an LLM client that supports multiple providers
        
        Args:
            config_path: Path to config file (if None, uses default)
            provider: Override provider from config ('vllm' or 'api-endpoint')
            api_base: Override API base URL from config
            api_key: Override API key for API endpoint (only needed for 'api-endpoint' provider)
            model_name: Override model name from config
            max_retries: Override max retries from config
            retry_delay: Override retry delay from config
        """
        # Load config
        self.config = load_config(config_path)
        
        # Determine provider (with CLI override taking precedence)
        self.provider = provider or get_llm_provider(self.config)
        
        if self.provider == 'api-endpoint':
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI package is not installed. Install with 'pip install openai>=1.0.0'")
            
            # Load API endpoint configuration
            api_endpoint_config = get_openai_config(self.config)
            
            # Set parameters, with CLI overrides taking precedence
            self.api_base = api_base or api_endpoint_config.get('api_base')
            
            # Check for environment variables
            api_endpoint_key = os.environ.get('API_ENDPOINT_KEY')
            print(f"API_ENDPOINT_KEY from environment: {'Found' if api_endpoint_key else 'Not found'}")
            
            # Set API key with priority: CLI arg > env var > config
            self.api_key = api_key or api_endpoint_key or api_endpoint_config.get('api_key')
            print(f"Using API key: {'From CLI' if api_key else 'From env var' if api_endpoint_key else 'From config' if api_endpoint_config.get('api_key') else 'None'}")
            
            if not self.api_key and not self.api_base:  # Only require API key for official API
                raise ValueError("API key is required for API endpoint provider. Set in config or API_ENDPOINT_KEY env var.")
            
            self.model = model_name or api_endpoint_config.get('model')
            self.max_retries = max_retries or api_endpoint_config.get('max_retries')
            self.retry_delay = retry_delay or api_endpoint_config.get('retry_delay')
            self.sleep_time = api_endpoint_config.get('sleep_time',0.5)
            
            # Initialize OpenAI client
            self._init_openai_client()
        elif self.provider == 'azure-openai':
            # Load Azure OpenAI configuration
            azure_config = get_azure_openai_config(self.config)
            
            # Set parameters
            self.api_key = azure_config.get('api_key')
            self.api_base = azure_config.get('azure_endpoint')
            self.api_version = azure_config.get('api_version')
            self.model = azure_config.get('deployment_name')
            self.max_retries = azure_config.get('max_retries')
            self.retry_delay = azure_config.get('retry_delay')
            self.sleep_time = azure_config.get('sleep_time', 0.5)
            
            # Initialize Azure OpenAI client
            self._init_azure_openai_client()
            # Initialize Azure OpenAI client
            self._init_azure_openai_client()
        else:
            raise ValueError(f"Unknown provider: {self.provider}. Supported: 'api-endpoint', 'azure-openai'")
    
    def _init_openai_client(self):
        """Initialize OpenAI client with appropriate configuration"""
        client_kwargs = {}
        
        # Add API key if provided
        if self.api_key:
            # Print first few characters of the API key for debugging
            #print(f"Using API key (first 10 chars): {self.api_key[:10]}...")
            client_kwargs['api_key'] = self.api_key
        else:
            print("No API key found!")
        
        # Add base URL if provided (for OpenAI-compatible APIs)
        if self.api_base:
            print(f"Using API base URL: {self.api_base}")
            client_kwargs['base_url'] = self.api_base
        
        self.openai_client = OpenAI(**client_kwargs)
    

    

    
    def _init_azure_openai_client(self):
        """Initialize Azure OpenAI client"""
        if not self.api_key or not self.api_base or not self.model:
            print("WARNING: Azure OpenAI credentials incomplete. Please check config.yaml.")
            
        client_kwargs = {
            'api_key': self.api_key,
            'azure_endpoint': self.api_base,
            'api_version': self.api_version
        }
        
        print(f"Initializing Azure OpenAI client with endpoint: {self.api_base}")
        self.openai_client = AzureOpenAI(**client_kwargs)

    def chat_completion(self, 
                      messages: List[Dict[str, str]], 
                      temperature: float = None, 
                      max_tokens: int = None,
                      top_p: float = None) -> str:
        """Generate a chat completion using the selected provider
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (higher = more random)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            
        Returns:
            String containing the generated text
        """
        # Get defaults from config if not provided
        generation_config = self.config.get('generation', {})
        temperature = temperature if temperature is not None else generation_config.get('temperature', 0.1)
        max_tokens = max_tokens if max_tokens is not None else generation_config.get('max_tokens', 4096)
        top_p = top_p if top_p is not None else generation_config.get('top_p', 0.95)
        
        verbose = os.environ.get('SDK_VERBOSE', 'false').lower() == 'true'
        
        verbose = os.environ.get('SDK_VERBOSE', 'false').lower() == 'true'
        
        if self.provider == 'api-endpoint' or self.provider == 'azure-openai':
            return self._openai_chat_completion(messages, temperature, max_tokens, top_p, verbose)
        else:
             raise ValueError(f"Unknown provider: {self.provider}")
    
    def _openai_chat_completion(self, 
                              messages: List[Dict[str, str]],
                              temperature: float,
                              max_tokens: int,
                              top_p: float,
                              verbose: bool) -> str:
        """Generate a chat completion using the OpenAI API or compatible APIs"""
        debug_mode = os.environ.get('SDK_DEBUG', 'false').lower() == 'true'
        if verbose:
            logger.info(f"Sending request to {self.provider} model {self.model}...")
            
        for attempt in range(self.max_retries):
            try:
                # Create the completion request
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                )
                
                if verbose:
                    logger.info(f"Received response from {self.provider}")
                
                # Log the full response in debug mode
                if debug_mode:
                    if hasattr(response, 'model_dump'):
                        logger.debug(f"Full response: {response.model_dump()}")
                    else:
                        logger.debug(f"Response type: {type(response)}")
                        logger.debug(f"Response attributes: {dir(response)}")
                
                # Method 1: Try standard OpenAI API response format
                try:
                    if hasattr(response, 'choices') and response.choices is not None and len(response.choices) > 0:
                        choice = response.choices[0]
                        if hasattr(choice, 'message') and choice.message is not None:
                            if hasattr(choice.message, 'content') and choice.message.content is not None:
                                return choice.message.content
                except Exception as e:
                    if verbose:
                        logger.info(f"Standard format extraction failed: {e}, trying alternative formats...")
                
                # Method 2: Llama API format
                try:
                    if hasattr(response, 'completion_message') and response.completion_message is not None:
                        completion = response.completion_message
                        # Handle dictionary case
                        if isinstance(completion, dict) and 'content' in completion:
                            content = completion['content']
                            # Different Llama API response formats
                            if isinstance(content, dict) and 'text' in content:
                                return content['text']
                            elif isinstance(content, str):
                                return content
                except Exception as e:
                    if verbose:
                        logger.info(f"Llama API format extraction failed: {e}, trying dictionary access...")
                
                # Method 3: Try dictionary access for both formats
                try:
                    # Convert to dictionary if possible
                    response_dict = None
                    if hasattr(response, 'model_dump'):
                        response_dict = response.model_dump()
                    elif hasattr(response, 'dict'):
                        response_dict = response.dict()
                    elif hasattr(response, '__dict__'):
                        response_dict = response.__dict__
                    elif isinstance(response, dict):
                        response_dict = response
                    
                    if response_dict is not None:
                        # Try Llama API format
                        if 'completion_message' in response_dict and response_dict['completion_message'] is not None:
                            comp = response_dict['completion_message']
                            if isinstance(comp, dict) and 'content' in comp:
                                content = comp['content']
                                if isinstance(content, dict) and 'text' in content:
                                    return content['text']
                                elif isinstance(content, str):
                                    return content
                        
                        # Try OpenAI format
                        if 'choices' in response_dict and response_dict['choices'] is not None and len(response_dict['choices']) > 0:
                            choice = response_dict['choices'][0]
                            if isinstance(choice, dict) and 'message' in choice:
                                message = choice['message']
                                if isinstance(message, dict) and 'content' in message and message['content'] is not None:
                                    return message['content']
                except Exception as e:
                    if verbose:
                        logger.info(f"Dictionary access failed: {e}")
                
                # Last resort: Try to print the full response for debugging
                if verbose or debug_mode:
                    logger.error("Could not extract content from response using any known method")
                    logger.error(f"Response: {response}")
                    if isinstance(response, dict):
                        for k, v in response.items():
                            logger.error(f"Key: {k}, Value type: {type(v)}, Value: {v}")
                    # Try to find any content-like fields
                    all_attrs = dir(response)
                    content_fields = [attr for attr in all_attrs if 'content' in attr.lower() or 'text' in attr.lower() or 'message' in attr.lower()]
                    for field in content_fields:
                        try:
                            logger.error(f"Potential content field '{field}': {getattr(response, field, 'N/A')}")
                        except:
                            pass
                
                raise ValueError(f"Could not extract content from response using any known method")
                
            except Exception as e:
                if verbose:
                    logger.error(f"{self.provider} API error (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                
                if attempt == self.max_retries - 1:
                    raise Exception(f"Failed to get {self.provider} completion after {self.max_retries} attempts: {str(e)}")
                
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
    

    
    def batch_completion(self, 
                       message_batches: List[List[Dict[str, str]]], 
                       temperature: float = None, 
                       max_tokens: int = None,
                       top_p: float = None,
                       batch_size: int = None) -> List[str]:
        """Process multiple message sets in batches
        
        Instead of sending requests one at a time, this method processes
        multiple prompts in batches to maximize throughput.
        """
        # Get defaults from config if not provided
        generation_config = self.config.get('generation', {})
        temperature = temperature if temperature is not None else generation_config.get('temperature', 0.1)
        max_tokens = max_tokens if max_tokens is not None else generation_config.get('max_tokens', 4096)
        top_p = top_p if top_p is not None else generation_config.get('top_p', 0.95)
        batch_size = batch_size if batch_size is not None else generation_config.get('batch_size', 32)
        
        verbose = os.environ.get('SDK_VERBOSE', 'false').lower() == 'true'
        
        verbose = os.environ.get('SDK_VERBOSE', 'false').lower() == 'true'
        
        if self.provider == 'api-endpoint' or self.provider == 'azure-openai':
            return self._openai_batch_completion(message_batches, temperature, max_tokens, top_p, batch_size, verbose)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _process_message_async(self, 
                                    messages: List[Dict[str, str]], 
                                    temperature: float,
                                    max_tokens: int,
                                    top_p: float,
                                    verbose: bool,
                                    debug_mode: bool):
        """Process a single message set asynchronously using the OpenAI API"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("The 'openai' package is required for this functionality. Please install it using 'pip install openai>=1.0.0'.")
        
        # Initialize the async OpenAI client
        client_kwargs = {}
        if self.api_key:
            client_kwargs['api_key'] = self.api_key
        if self.api_base:
            client_kwargs['base_url'] = self.api_base
            
        if self.provider == 'azure-openai':
            from openai import AsyncAzureOpenAI
            client_kwargs = {
                'api_key': self.api_key,
                'azure_endpoint': self.api_base,
                'api_version': self.api_version
            }
            async_client = AsyncAzureOpenAI(**client_kwargs)
        else:
            async_client = AsyncOpenAI(**client_kwargs)
        
        for attempt in range(self.max_retries):
            try:
                # Asynchronously call the API
                response = await async_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                )
                
                if verbose:
                    logger.info(f"Received response from {self.provider}")
                
                # Log the full response in debug mode
                if debug_mode:
                    if hasattr(response, 'model_dump'):
                        logger.debug(f"Full response: {response.model_dump()}")
                    else:
                        logger.debug(f"Response type: {type(response)}")
                        logger.debug(f"Response attributes: {dir(response)}")
                
                content = None
                
                # Method 1: Try standard OpenAI API response format
                try:
                    if hasattr(response, 'choices') and response.choices is not None and len(response.choices) > 0:
                        choice = response.choices[0]
                        if hasattr(choice, 'message') and choice.message is not None:
                            if hasattr(choice.message, 'content') and choice.message.content is not None:
                                content = choice.message.content
                except Exception as e:
                    if verbose:
                        logger.info(f"Standard format extraction failed: {e}, trying alternative formats...")
                
                # Method 2: Llama API format
                if content is None:
                    try:
                        if hasattr(response, 'completion_message') and response.completion_message is not None:
                            completion = response.completion_message
                            # Handle dictionary case
                            if isinstance(completion, dict) and 'content' in completion:
                                content_obj = completion['content']
                                # Different Llama API response formats
                                if isinstance(content_obj, dict) and 'text' in content_obj:
                                    content = content_obj['text']
                                elif isinstance(content_obj, str):
                                    content = content_obj
                    except Exception as e:
                        if verbose:
                            logger.info(f"Llama API format extraction failed: {e}, trying dictionary access...")
                
                # Method 3: Try dictionary access for both formats
                if content is None:
                    try:
                        # Convert to dictionary if possible
                        response_dict = None
                        if hasattr(response, 'model_dump'):
                            response_dict = response.model_dump()
                        elif hasattr(response, 'dict'):
                            response_dict = response.dict()
                        elif hasattr(response, '__dict__'):
                            response_dict = response.__dict__
                        elif isinstance(response, dict):
                            response_dict = response
                        
                        if response_dict is not None:
                            # Try Llama API format
                            if 'completion_message' in response_dict and response_dict['completion_message'] is not None:
                                comp = response_dict['completion_message']
                                if isinstance(comp, dict) and 'content' in comp:
                                    content_obj = comp['content']
                                    if isinstance(content_obj, dict) and 'text' in content_obj:
                                        content = content_obj['text']
                                    elif isinstance(content_obj, str):
                                        content = content_obj
                            
                            # Try OpenAI format
                            if content is None and 'choices' in response_dict and response_dict['choices'] and len(response_dict['choices']) > 0:
                                choice = response_dict['choices'][0]
                                if isinstance(choice, dict) and 'message' in choice:
                                    message = choice['message']
                                    if isinstance(message, dict) and 'content' in message and message['content'] is not None:
                                        content = message['content']
                    except Exception as e:
                        if verbose:
                            logger.info(f"Dictionary access failed: {e}")
                
                # If content is still None, print detailed debug info
                if content is None:
                    if verbose or debug_mode:
                        logger.error("Could not extract content from response using any known method")
                        logger.error(f"Response: {response}")
                        if isinstance(response, dict):
                            for k, v in response.items():
                                logger.error(f"Key: {k}, Value type: {type(v)}, Value: {v}")
                        # Try to find any content-like fields
                        all_attrs = dir(response)
                        content_fields = [attr for attr in all_attrs if 'content' in attr.lower() or 'text' in attr.lower() or 'message' in attr.lower()]
                        for field in content_fields:
                            try:
                                logger.error(f"Potential content field '{field}': {getattr(response, field, 'N/A')}")
                            except:
                                pass
                    
                    raise ValueError(f"Could not extract content from response using any known method")
                
                return content
                
            except Exception as e:
                if verbose:
                    logger.error(f"{self.provider} API error (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                
                if attempt == self.max_retries - 1:
                    return f"ERROR: {str(e)}"
                
                await asyncio.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
    
    def _openai_batch_completion(self,
                                message_batches: List[List[Dict[str, str]]],
                                temperature: float,
                                max_tokens: int,
                                top_p: float,
                                batch_size: int,
                                verbose: bool) -> List[str]:
        """Process multiple message sets using the OpenAI API or compatible APIs asynchronously"""
        debug_mode = os.environ.get('SDK_DEBUG', 'false').lower() == 'true'
        results = []
        
        # Process message batches in chunks to avoid overloading the API
        for i in range(0, len(message_batches), batch_size):
            batch_chunk = message_batches[i:i+batch_size]
            if verbose:
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(message_batches) + batch_size - 1) // batch_size} with {len(batch_chunk)} requests")
            
            # Import asyncio here to avoid issues if not available
            try:
                import asyncio
            except ImportError:
                raise ImportError("The 'asyncio' package is required for batch processing. Please ensure you're using Python 3.7+.")
            
            # Define async batch processing function
            async def process_batch():
                tasks = []
                for messages in batch_chunk:
                    task = self._process_message_async(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        verbose=verbose,
                        debug_mode=debug_mode
                    )
                    tasks.append(task)
                
                # Process all messages in the batch concurrently
                return await asyncio.gather(*tasks)
            
            # Run the async batch processing
            batch_results = asyncio.run(process_batch())
            results.extend(batch_results)
            
            # Small delay between batches to avoid rate limits
            if i + batch_size < len(message_batches):
                time.sleep(self.sleep_time)
        
        return results
    

    
    @classmethod
    def from_config(cls, config_path: Path) -> 'LLMClient':
        """Create a client from configuration file"""
        return cls(config_path=config_path)
