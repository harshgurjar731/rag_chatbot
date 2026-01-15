"""
Bot Utilities Module

This module provides shared utility functions for bot name handling and validation.
It includes functions to sanitize bot names for Docker usage, generate container names,
and validate user-provided bot names against system constraints.
"""

import re
from typing import Tuple


def sanitize_bot_name(bot_name: str) -> str:
    """
    Sanitize a bot name for use as Docker network alias/hostname.
    
    Converts to lowercase and replaces spaces and special characters with hyphens.
    Docker network aliases must be valid DNS names.
    
    Args:
        bot_name (str): Original bot name (may contain spaces, mixed case).
        
    Returns:
        str: Sanitized name suitable for Docker network alias (lowercase, no spaces).
        
    Examples:
        "Bot 1" -> "bot-1"
        "Sales Bot" -> "sales-bot"
        "My_Bot@123" -> "my-bot-123"
    """
    # Convert to lowercase
    name = bot_name.lower()
    # Replace spaces and underscores with hyphens
    name = name.replace(' ', '-').replace('_', '-')
    # Remove any characters that aren't alphanumeric or hyphens
    name = re.sub(r'[^a-z0-9-]', '', name)
    # Remove consecutive hyphens
    name = re.sub(r'-+', '-', name)
    # Remove leading/trailing hyphens
    name = name.strip('-')
    return name


def get_container_name(bot_name: str) -> str:
    """
    Generate Docker container name from bot name.
    
    Args:
        bot_name (str): Name of the bot.
        
    Returns:
        str: Docker-compatible container name with 'bot_' prefix.
    """
    sanitized = bot_name.replace(' ', '_')
    return f"bot_{sanitized}"


def validate_bot_name(bot_name: str) -> Tuple[bool, str]:
    """
    Validate a bot name for use in the system.
    
    Checks if the name is not empty, within length limits, and results in a valid
    alphanumeric identifier after sanitization.
    
    Args:
        bot_name (str): Name to validate.
        
    Returns:
        Tuple[bool, str]: A tuple containing:
            - is_valid (bool): True if the name is valid, False otherwise.
            - message (str): A message explaining the validation result.
    """
    if not bot_name or not bot_name.strip():
        return False, "Bot name cannot be empty"
    
    if len(bot_name) > 50:
        return False, "Bot name must be 50 characters or less"
    
    # Check if sanitization would result in empty string
    sanitized = sanitize_bot_name(bot_name)
    if not sanitized:
        return False, "Bot name must contain at least one alphanumeric character"
    
    return True, "Valid"
