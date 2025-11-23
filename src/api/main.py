"""
FastAPI application entry point.
"""

from fastapi import FastAPI

from src.api.middleware import TenantRouterMiddleware
from src.api.routes import admin, exceptions, metrics, run, tools

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

