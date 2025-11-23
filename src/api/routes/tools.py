"""
Tool invocation API routes.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/{tenant_id}/{tool_name}")
async def invoke_tool(tenant_id: str, tool_name: str):
    """
    Invoke a registered tool.
    POST /tools/{tenantId}/{toolName}
    """
    # TODO: Implement tool invocation
    pass

