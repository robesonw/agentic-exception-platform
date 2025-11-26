"""
FastAPI application entry point.
"""

from fastapi import FastAPI

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
    tools,
    ui_status,
)

app = FastAPI(
    title="Agentic Exception Processing Platform",
    description="Domain-Abstracted Agentic AI Platform for Multi-Tenant Exception Processing",
    version="0.1.0",
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
app.include_router(ui_status.router)  # Phase 2: UI Status
app.include_router(admin_domainpacks.router)  # Phase 2: Admin Domain Pack Management
app.include_router(admin_tenantpolicies.router)  # Phase 2: Admin Tenant Policy Pack Management
app.include_router(admin_tools.router)  # Phase 2: Admin Tool Management
app.include_router(dashboards.router)  # Phase 2: Advanced Dashboards


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

