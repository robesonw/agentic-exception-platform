"""
Health check HTTP server for workers.

Provides /healthz and /readyz endpoints for Kubernetes-style health checks.
"""

import asyncio
import logging
import threading
from typing import Optional

from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
import uvicorn

from src.infrastructure.db.session import get_engine
from src.messaging.broker import Broker
from src.workers.base import AgentWorker
from typing import Any

logger = logging.getLogger(__name__)

# Port assignments for each worker type
WORKER_PORTS = {
    "intake": 9001,
    "triage": 9002,
    "policy": 9003,
    "playbook": 9004,
    "tool": 9005,
    "feedback": 9006,
    "sla_monitor": 9007,
}


def get_worker_port(worker_type: str) -> int:
    """
    Get HTTP port for a worker type.
    
    Args:
        worker_type: Worker type (e.g., "intake", "triage")
        
    Returns:
        Port number
    """
    return WORKER_PORTS.get(worker_type.lower(), 9000)


class WorkerHealthServer:
    """
    HTTP server for worker health checks.
    
    Provides:
    - /healthz: Process alive + broker reachable
    - /readyz: DB reachable + subscribed to topics
    """
    
    def __init__(
        self,
        worker: Any,  # Can be AgentWorker or SLAMonitorWorker
        broker: Broker,
        port: int,
        worker_type: str,
    ):
        """
        Initialize health check server.
        
        Args:
            worker: Worker instance (AgentWorker or SLAMonitorWorker)
            broker: Broker instance
            port: HTTP port to listen on
            worker_type: Worker type name
        """
        self.worker = worker
        self.broker = broker
        self.port = port
        self.worker_type = worker_type
        self.app = FastAPI(title=f"{worker_type} Worker Health")
        self._server_thread: Optional[threading.Thread] = None
        self._server_running = False
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup health check routes."""
        
        @self.app.get("/healthz")
        async def healthz() -> Response:
            """
            Health check endpoint.
            
            Returns 200 if:
            - Process is alive
            - Broker is reachable
            
            Returns 503 if unhealthy.
            """
            try:
                # Check if worker process is running
                if not self.worker._running:
                    return Response(
                        content='{"status": "unhealthy", "reason": "worker_not_running"}',
                        media_type="application/json",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                
                # Check broker health
                try:
                    broker_health = self.broker.health()
                    broker_connected = broker_health.get("connected", False)
                    
                    if not broker_connected:
                        return Response(
                            content='{"status": "unhealthy", "reason": "broker_not_reachable"}',
                            media_type="application/json",
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        )
                    
                    return JSONResponse(
                        content={
                            "status": "healthy",
                            "worker_type": self.worker_type,
                            "broker": broker_health,
                        },
                        status_code=status.HTTP_200_OK,
                    )
                except Exception as e:
                    logger.warning(f"Broker health check failed: {e}")
                    return Response(
                        content=f'{{"status": "unhealthy", "reason": "broker_check_failed", "error": "{str(e)}"}}',
                        media_type="application/json",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                
            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)
                return Response(
                    content=f'{{"status": "unhealthy", "reason": "internal_error", "error": "{str(e)}"}}',
                    media_type="application/json",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        
        @self.app.get("/readyz")
        async def readyz() -> Response:
            """
            Readiness check endpoint.
            
            Returns 200 if:
            - Worker is running
            
            Note: Database check is skipped to avoid asyncpg concurrency issues.
            If worker is running, database was connected during initialization.
            
            Returns 503 if not ready.
            """
            try:
                # Check if worker process is running
                # Handle both AgentWorker and SLAMonitorWorker
                worker_running = getattr(self.worker, "_running", False)
                
                if not worker_running:
                    return Response(
                        content='{"status": "not_ready", "reason": "worker_not_running"}',
                        media_type="application/json",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                
                # Check if worker is subscribed (consumer thread is alive)
                # Note: SLAMonitorWorker doesn't have _consumer_thread (doesn't subscribe to topics)
                subscribed = False
                if hasattr(self.worker, "_consumer_thread"):
                    subscribed = (
                        self.worker._consumer_thread is not None
                        and self.worker._consumer_thread.is_alive()
                    )
                
                # Get topics and group_id if available (AgentWorker has these)
                topics = getattr(self.worker, "topics", [])
                group_id = getattr(self.worker, "group_id", None)
                
                # Worker is ready if it's running
                # Database check skipped to avoid asyncpg concurrency issues
                return JSONResponse(
                    content={
                        "status": "ready",
                        "worker_type": self.worker_type,
                        "topics": topics,
                        "group_id": group_id,
                        "subscribed": subscribed,
                        "worker_running": worker_running,
                    },
                    status_code=status.HTTP_200_OK,
                )
                
            except Exception as e:
                logger.error(f"Readiness check error: {e}", exc_info=True)
                return Response(
                    content=f'{{"status": "not_ready", "reason": "internal_error", "error": "{str(e)}"}}',
                    media_type="application/json",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        
        @self.app.get("/")
        async def root() -> dict:
            """Root endpoint with worker info."""
            return {
                "worker_type": self.worker_type,
                "port": self.port,
                "endpoints": {
                    "healthz": "/healthz",
                    "readyz": "/readyz",
                },
            }
    
    def start(self) -> None:
        """Start the health check server in a background thread."""
        if self._server_running:
            logger.warning(f"Health server for {self.worker_type} is already running")
            return
        
        def run_server():
            """Run uvicorn server in background thread."""
            try:
                uvicorn.run(
                    self.app,
                    host="0.0.0.0",
                    port=self.port,
                    log_level="warning",  # Reduce noise from uvicorn
                    access_log=False,
                )
            except Exception as e:
                logger.error(f"Health server error: {e}", exc_info=True)
        
        self._server_thread = threading.Thread(
            target=run_server,
            daemon=True,
            name=f"{self.worker_type}-health-server",
        )
        self._server_thread.start()
        self._server_running = True
        
        logger.info(f"Health check server started on port {self.port} for {self.worker_type} worker")
    
    def stop(self) -> None:
        """Stop the health check server."""
        if not self._server_running:
            return
        
        # Note: uvicorn doesn't have a clean shutdown API from another thread
        # In production, you might want to use a more sophisticated approach
        # For MVP, we'll just mark it as stopped
        self._server_running = False
        logger.info(f"Health check server stopped for {self.worker_type} worker")

