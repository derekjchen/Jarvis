# -*- coding: utf-8 -*-
"""API routes for graceful restart management."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .graceful_restart import (
    GracefulRestartManager,
    get_graceful_restart_manager,
    RestartState,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/restart", tags=["restart"])


class RestartRequest(BaseModel):
    """Request to trigger restart."""
    delay: Optional[int] = 3  # Seconds before restart
    force: Optional[bool] = False  # Force restart even with pending requests
    save_state: Optional[bool] = True  # Save state before restart


class RestartStatusResponse(BaseModel):
    """Restart status response."""
    state: str
    pending_requests: int
    saved_sessions: int
    saved_entities: int
    started_at: str = ""
    message: str = ""
    error: str = ""


class RestartPrepareResponse(BaseModel):
    """Response for prepare endpoint."""
    success: bool
    message: str
    status: RestartStatusResponse
    error: str = ""


class RestartSaveResponse(BaseModel):
    """Response for save endpoint."""
    success: bool
    saved_sessions: int
    saved_entities: int
    backup_file: str = ""
    errors: list[str] = []


class RestartExecuteResponse(BaseModel):
    """Response for execute endpoint."""
    success: bool
    message: str
    delay: int


class RestartFullResponse(BaseModel):
    """Response for full restart endpoint."""
    prepare: dict
    save: dict
    wait: dict
    restart: dict
    success: bool
    message: str = ""


class DataIntegrityResponse(BaseModel):
    """Response for data integrity check."""
    success: bool
    checks: dict
    user_data_dir: str


def get_graceful_manager(request: Request) -> GracefulRestartManager:
    """Get graceful restart manager from app state."""
    manager = getattr(request.app.state, "graceful_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Graceful restart manager not initialized"
        )
    return manager


@router.get("/status", response_model=RestartStatusResponse)
async def get_restart_status(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Get current restart status.
    
    Returns:
        Current restart state, pending request count, etc.
    """
    status = manager.get_status()
    return RestartStatusResponse(
        state=status.state.value,
        pending_requests=status.pending_requests,
        saved_sessions=status.saved_sessions,
        saved_entities=status.saved_entities,
        started_at=status.started_at,
        message=status.message,
        error=status.error,
    )


@router.post("/prepare", response_model=RestartPrepareResponse)
async def prepare_restart(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Prepare for restart - stop accepting new requests.
    
    This endpoint:
    1. Sets app state to restarting
    2. Notifies connected clients
    3. Returns current status
    
    Call this first before executing restart.
    """
    result = await manager.prepare_restart()
    status = manager.get_status()
    
    return RestartPrepareResponse(
        success=result["success"],
        message=result["message"],
        status=RestartStatusResponse(
            state=status.state.value,
            pending_requests=status.pending_requests,
            saved_sessions=status.saved_sessions,
            saved_entities=status.saved_entities,
            started_at=status.started_at,
            message=status.message,
            error=status.error,
        ),
        error=result.get("error", ""),
    )


@router.post("/save", response_model=RestartSaveResponse)
async def save_state(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Save all session states and memory data.
    
    This endpoint:
    1. Saves all active sessions
    2. Saves memory data
    3. Saves entity store
    4. Creates backup record
    
    Call after /prepare and before /execute.
    """
    result = await manager.save_all_state()
    
    return RestartSaveResponse(
        success=result["success"],
        saved_sessions=result["saved_sessions"],
        saved_entities=result["saved_entities"],
        backup_file=result.get("backup_file", ""),
        errors=result.get("errors", []),
    )


@router.post("/wait")
async def wait_for_pending(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Wait for pending requests to complete.
    
    Returns when all pending requests are done or timeout.
    """
    result = await manager.wait_for_pending_requests()
    return result


@router.post("/execute", response_model=RestartExecuteResponse)
async def execute_restart(
    request: RestartRequest,
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Execute the restart.
    
    This will:
    1. Schedule restart after delay seconds
    2. Run pre-restart callbacks
    3. Call os.execv to replace process
    
    The process will exit and restart with new code loaded.
    """
    result = await manager.execute_restart(delay=request.delay)
    
    return RestartExecuteResponse(
        success=result["success"],
        message=result["message"],
        delay=request.delay,
    )


@router.post("/full", response_model=RestartFullResponse)
async def full_restart(
    request: RestartRequest,
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Execute full graceful restart sequence.
    
    This runs all steps:
    1. Prepare (stop accepting new requests)
    2. Save all state
    3. Wait for pending requests
    4. Execute restart
    
    Use this for a complete graceful restart.
    """
    results = await manager.full_restart()
    
    success = all(
        r.get("success", False) for r in results.values() if isinstance(r, dict)
    )
    
    return RestartFullResponse(
        prepare=results.get("prepare", {}),
        save=results.get("save", {}),
        wait=results.get("wait", {}),
        restart=results.get("restart", {}),
        success=success,
        message="Full restart initiated" if success else "Restart failed",
    )


@router.get("/cancel")
async def cancel_restart(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Cancel a pending restart.
    
    Only works if restart is in preparing/saving/waiting state.
    Cannot cancel once executing.
    """
    status = manager.get_status()
    
    if status.state == RestartState.NORMAL:
        return {"success": False, "message": "No restart in progress"}
    
    if status.state == RestartState.RESTARTING:
        return {"success": False, "message": "Cannot cancel - restart already executing"}
    
    # Reset state
    manager._status.state = RestartState.NORMAL
    manager._status.message = ""
    manager._status.started_at = ""
    
    if manager._app:
        manager._app.state._restarting = False
    
    return {"success": True, "message": "Restart cancelled"}


@router.get("/integrity", response_model=DataIntegrityResponse)
async def check_data_integrity(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Verify user data integrity.
    
    Checks that all required files and directories exist.
    Run this after restart to verify data is intact.
    """
    result = manager.verify_data_integrity()
    
    return DataIntegrityResponse(
        success=result["success"],
        checks=result["checks"],
        user_data_dir=result["user_data_dir"],
    )


@router.get("/health")
async def restart_health_check(
    manager: GracefulRestartManager = Depends(get_graceful_manager),
):
    """Health check for restart capability.
    
    Returns:
        Status indicating if restart functionality is available.
    """
    status = manager.get_status()
    
    return {
        "healthy": status.state == RestartState.NORMAL,
        "state": status.state.value,
        "can_restart": status.state == RestartState.NORMAL,
        "pending_requests": status.pending_requests,
    }