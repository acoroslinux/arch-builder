from typing import Dict, Any

def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.
    Values from ``update`` overwrite values from ``base``.
    If both values are dictionaries, they are merged recursively.
    """
    for key, value in update.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base
