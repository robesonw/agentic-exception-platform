"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import TenantRouterMiddleware
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

app = FastAPI(
    title="Agentic Exception Processing Platform",
    description="Domain-Abstracted Agentic AI Platform for Multi-Tenant Exception Processing",
    version="0.1.0",
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# TODO (LR-11): Expose Prometheus metrics endpoint
# If prometheus_client is available, mount /metrics endpoint
# Example:
#   try:
#       from prometheus_client import make_asgi_app
#       metrics_app = make_asgi_app()
#       app.mount("/metrics", metrics_app)
#   except ImportError:
#       logger.warning("prometheus_client not available, /metrics endpoint not mounted")
