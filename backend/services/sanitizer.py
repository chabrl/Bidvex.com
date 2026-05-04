"""
BidVex — NoSQL Injection Sanitizer
====================================
Prevents MongoDB operator injection via user-supplied search/filter input.

Use:
    from services.sanitizer import sanitize_string, sanitize_dict
    safe_search = sanitize_string(request.query_params.get("q", ""))
"""
import re
from typing import Any, Dict, List

# Operators commonly used in NoSQL injection attacks
MONGO_INJECTION_PATTERNS = [
    r'\$where', r'\$ne', r'\$gt', r'\$lt', r'\$gte', r'\$lte',
    r'\$in', r'\$nin', r'\$or', r'\$and', r'\$not', r'\$regex',
    r'\$expr', r'\$jsonSchema', r'\$text', r'\$mod', r'\$function',
    r'\$accumulator',
]

_INJECTION_RE = re.compile("|".join(MONGO_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_string(value: Any) -> str:
    """Strip null bytes and reject Mongo operator injection in a single string."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value

    # Remove null bytes
    value = value.replace('\x00', '')

    if _INJECTION_RE.search(value):
        raise ValueError("Invalid input detected")

    return value.strip()


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize all string values in a dict.

    Rejects any top-level field name starting with '$' (Mongo operator).
    """
    if not isinstance(data, dict):
        return data

    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and key.startswith('$'):
            raise ValueError(f"Invalid field name: {key}")
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = sanitize_list(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_list(values: List[Any]) -> List[Any]:
    """Sanitize each element of a list."""
    out: List[Any] = []
    for v in values:
        if isinstance(v, str):
            out.append(sanitize_string(v))
        elif isinstance(v, dict):
            out.append(sanitize_dict(v))
        elif isinstance(v, list):
            out.append(sanitize_list(v))
        else:
            out.append(v)
    return out


def safe_regex(pattern: str) -> str:
    """Escape user input destined for a MongoDB $regex query."""
    if pattern is None:
        return ""
    pattern = sanitize_string(pattern)
    return re.escape(pattern)
