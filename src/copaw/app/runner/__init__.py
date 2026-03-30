# -*- coding: utf-8 -*-
"""Runner module with chat manager for coordinating repository."""
from .runner import AgentRunner
from .api import router
from .manager import ChatManager
from .models import (
    ChatSpec,
    ChatHistory,
    ChatsFile,
)
from .repo import (
    BaseChatRepository,
    JsonChatRepository,
)
from .graceful_restart import (
    GracefulRestartManager,
    get_graceful_restart_manager,
    RestartState,
    RestartStatus,
    RestartConfig,
)
from .restart_api import router as restart_router


__all__ = [
    # Core classes
    "AgentRunner",
    "ChatManager",
    # API
    "router",
    "restart_router",
    # Models
    "ChatSpec",
    "ChatHistory",
    "ChatsFile",
    # Chat Repository
    "BaseChatRepository",
    "JsonChatRepository",
    # Graceful Restart
    "GracefulRestartManager",
    "get_graceful_restart_manager",
    "RestartState",
    "RestartStatus",
    "RestartConfig",
]
