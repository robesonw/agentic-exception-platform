"""
Utility functions for pack management.
"""

import hashlib
import json
from typing import Any


def calculate_checksum(content: dict[str, Any] | str) -> str:
    """
    Calculate SHA-256 checksum for pack content.
    
    Args:
        content: Pack content as dict or JSON string
        
    Returns:
        Hexadecimal checksum string
    """
    if isinstance(content, dict):
        # Sort keys for consistent hashing
        json_str = json.dumps(content, sort_keys=True, separators=(',', ':'))
    else:
        json_str = content
    
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

