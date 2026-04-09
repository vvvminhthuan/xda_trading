import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_env_bool(key: str, default: bool = False) -> bool:
    """Convert string env to boolean"""
    return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')

def get_env_list(key: str, default: List[str] = None) -> List[str]:
    """Convert comma-separated string to list"""
    if default is None:
        default = []
    value = os.getenv(key, '')
    return [item.strip() for item in value.split(',')] if value else default

def get_env_float(key: str, default: float = 0.0) -> float:
    """Convert string env to float"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default  

def get_env_int(key: str, default: int = 0) -> int:
    """Convert string env to int"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default
    
