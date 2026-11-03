"""Desktop Vision & Coordinate Computer Control Services.
"""

from typing import Any, Dict, List, Optional

from tools.desktop.vision.executor import (
    execute_atomic_action,
    execute_batch_actions,
)
from tools.desktop.vision.screen import ScreenManager


async def computer(
    action: str,
    coordinate: Optional[List[int | float]] = None,
    text: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Execute an atomic desktop action matching Anthropic Computer Use protocol."""
    return await execute_atomic_action(action=action, coordinate=coordinate, text=text, **kwargs)


async def computer_actions(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute compound sequence of computer actions with automatic post-execution visual telemetry."""
    return await execute_batch_actions(actions)


async def desktop_inspect(max_dimension: int = 1280, quality: int = 75) -> Any:
    """Capture screen frame and return downsampled image blocks for AI vision inspection."""
    import asyncio
    screen_mgr = ScreenManager.get_instance()
    return await asyncio.to_thread(screen_mgr.capture_screenshot, max_dimension=max_dimension, quality=quality)


__all__ = [
    "computer",
    "computer_actions",
    "desktop_inspect",
    "ScreenManager",
    "execute_atomic_action",
    "execute_batch_actions",
]
