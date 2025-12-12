"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import TenantRouterMiddleware
from src.infrastructure.db.session import close_engine, initialize_database

logger = logging.getLogger(__name__)
from src.api.routes import (
    admin,
    admin_domainpacks,
    admin_tenantpolicies,
    admin_tools,
    approvals,
    approval_ui,
    dashboards,
    exceptions,
    metrics,
    playbooks,
    run,
    router_config_view,
    router_copilot,
    router_explanations,
    router_guardrail_recommendations,
    router_nlq,
    router_operator,
    router_simulation,
    router_supervisor_dashboard,
    tools,
    ui_status,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup: Initialize database connection
    logger.info("Starting application...")
    db_initialized = await initialize_database()
    if not db_initialized:
        logger.warning(
            "Database initialization failed. Application will continue but database operations may fail."
        )
    
    yield
    
    # Shutdown: Close database connections
    logger.info("Shutting down application...")
    await close_engine()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Agentic Exception Processing Platform",
    description="Domain-Abstracted Agentic AI Platform for Multi-Tenant Exception Processing",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware (must be added before other middleware)
# This handles OPTIONS preflight requests from browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers (including X-API-KEY, X-Tenant-Id, etc.)
)

# Add tenant router middleware
app.add_middleware(TenantRouterMiddleware)

# Register route modules
app.include_router(exceptions.router)
app.include_router(run.router)
app.include_router(metrics.router)
app.include_router(admin.router)
app.include_router(tools.router)
app.include_router(approvals.router)  # Phase 2: Approval workflow
app.include_router(approval_ui.router)  # Phase 2: Approval UI
# IMPORTANT: Register router_operator BEFORE ui_status to ensure more specific routes match first
# ui_status now uses /ui/status/{tenant_id} to avoid conflict with router_operator's /ui/exceptions/{exception_id}
app.include_router(router_operator.router)  # Phase 3: Operator UI Backend APIs
app.include_router(ui_status.router)  # Phase 2: UI Status
app.include_router(admin_domainpacks.router)  # Phase 2: Admin Domain Pack Management
app.include_router(admin_tenantpolicies.router)  # Phase 2: Admin Tenant Policy Pack Management
app.include_router(admin_tools.router)  # Phase 2: Admin Tool Management
app.include_router(dashboards.router)  # Phase 2: Advanced Dashboards
app.include_router(router_nlq.router)  # Phase 3: Natural Language Query API
app.include_router(router_simulation.router)  # Phase 3: Re-Run and What-If Simulation API
app.include_router(router_supervisor_dashboard.router)  # Phase 3: Supervisor Dashboard Backend APIs
app.include_router(router_config_view.router)  # Phase 3: Configuration Viewing and Diffing APIs
app.include_router(router_explanations.router)  # Phase 3: Explanation API Endpoints
app.include_router(router_guardrail_recommendations.router)  # Phase 3: Guardrail Recommendation API (P3-10)
app.include_router(router_copilot.router)  # Phase 5: Copilot Chat API (P5-9)
app.include_router(playbooks.router)  # Phase 6: Playbook API (P6-24)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/db")
async def health_check_db():
    """
    Database health check endpoint.
    
    Returns:
        - 200 OK if database is reachable
        - 503 Service Unavailable if database is not reachable
    """
    from fastapi import status
    from fastapi.responses import JSONResponse
    
    from src.infrastructure.db.session import check_database_connection
    
    is_healthy = await check_database_connection(retries=1, initial_delay=0.5)
    
    if is_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "database": "connected"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected"},
        )


# TODO (LR-11): Expose Prometheus metrics endpoint
# If prometheus_client is available, mount /metrics endpoint
# Example:
#   try:
#       from prometheus_client import make_asgi_app
#       metrics_app = make_asgi_app()
#       app.mount("/metrics", metrics_app)
#   except ImportError:
#       logger.warning("prometheus_client not available, /metrics endpoint not mounted")
