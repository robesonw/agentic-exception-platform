"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logging.getLogger(__name__).info(f"Loaded .env file from {env_path}")
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

from src.api.middleware import TenantRouterMiddleware
from src.infrastructure.db.session import close_engine, initialize_database

logger = logging.getLogger(__name__)
from src.api.routes import (
    admin,
    admin_domainpacks,
    admin_tenantpolicies,
    admin_tools,
    alerts,
    approvals,
    approval_ui,
    audit,
    audit_reports,
    config_governance,
    dashboards,
    exceptions,
    metrics,
    ops,
    ops_dashboard,
    playbooks,
    rate_limits,
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
    usage,
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
app.include_router(audit.router)  # Phase 9: Audit Trail API (P9-25)
app.include_router(ops.router)  # Phase 10: Operations API (DLQ monitoring)
app.include_router(alerts.router)  # Phase 10: Alerting API (P10-6, P10-9)
app.include_router(config_governance.router)  # Phase 10: Config Change Governance (P10-10)
app.include_router(audit_reports.router)  # Phase 10: Audit Reports API (P10-11 to P10-14)
app.include_router(rate_limits.router)  # Phase 10: Rate Limits Admin API (P10-15 to P10-17)
app.include_router(rate_limits.usage_router)  # Phase 10: Rate Limits Usage API (P10-15 to P10-17)
app.include_router(usage.router)  # Phase 10: Usage Metering API (P10-18 to P10-20)
app.include_router(ops_dashboard.router)  # Phase 10: Ops Dashboard API (P10-21 to P10-28)


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


# Phase 9 P9-20: Expose Prometheus metrics endpoint
try:
    from prometheus_client import make_asgi_app
    from src.observability.prometheus_metrics import get_metrics
    
    # Create ASGI app for Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    logger.info("Prometheus metrics endpoint mounted at /metrics")
except ImportError:
    # Fallback: create a simple endpoint that returns our custom metrics
    from fastapi import Response
    from src.observability.prometheus_metrics import get_metrics
    
    @app.get("/metrics")
    async def get_metrics_endpoint() -> Response:
        """Get Prometheus metrics."""
        metrics = get_metrics()
        metrics_text = metrics.get_metrics()
        return Response(content=metrics_text, media_type="text/plain")
    
    logger.warning("prometheus_client not available, using custom /metrics endpoint")
