"""
registry.py — AgenticBusinessEmpire Autonomous Handler Registry
Implements decorator-based command discovery.
"""
import logging
from typing import Callable, Any, Dict, Optional
from functools import wraps

logger = logging.getLogger("agenticbusinessempire.kernel.registry")

class HandlerRegistry:
    _handlers: Dict[str, Callable] = {}

    @classmethod
    def register(cls, command_name: str):
        """Decorator to register a function as a handler for a specific command."""
        def decorator(func: Callable):
            cls._handlers[command_name] = func
            logger.info("[Registry] Registered handler for: %s", command_name)
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @classmethod
    def get_handler(cls, command_name: str) -> Optional[Callable]:
        return cls._handlers.get(command_name)

    @classmethod
    def list_commands(cls) -> list[str]:
        return list(cls._handlers.keys())

# Shared singleton instance
registry = HandlerRegistry()
