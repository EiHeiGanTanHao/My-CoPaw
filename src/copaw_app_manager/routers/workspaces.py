"""API 路由 - 工作区 CRUD"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from copaw_app_manager.service.manager import WorkspaceManager
from copaw_app_manager.models.workspace import Workspace, WorkspaceStatus


router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

# 全局 manager 实例
_manager: Optional[WorkspaceManager] = None


def get_manager() -> WorkspaceManager:
    """获取或创建 manager 实例"""
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager


# ========== 请求/响应模型 ==========
class CreateWorkspaceRequest(BaseModel):
    """创建工作区请求"""
    name: str
    description: str = ""
    working_dir: Optional[str] = None
    auto_start: bool = False


class UpdateWorkspaceRequest(BaseModel):
    """更新工作区请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    auto_start: Optional[bool] = None


class WorkspaceListResponse(BaseModel):
    """工作区列表响应"""
    workspaces: list[Workspace]


class WorkspaceResponse(BaseModel):
    """单个工作区响应"""
    workspace: Workspace


class StartResponse(BaseModel):
    """启动响应"""
    success: bool
    url: str


class StopResponse(BaseModel):
    """停止响应"""
    success: bool


class HealthResponse(BaseModel):
    """健康状态响应"""
    workspace_id: str
    name: str
    is_healthy: Optional[bool] = None


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool


# ========== API 端点 ==========
@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces():
    """列出所有工作区（自动检测状态）"""
    manager = get_manager()
    workspaces = manager.list_workspaces()
    return WorkspaceListResponse(workspaces=workspaces)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str):
    """获取单个工作区"""
    manager = get_manager()
    workspace = manager.get_workspace(workspace_id)

    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    return WorkspaceResponse(workspace=workspace)


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest):
    """创建工作区"""
    manager = get_manager()

    try:
        workspace = manager.create_workspace(
            name=request.name,
            description=request.description,
            working_dir=request.working_dir,
            auto_start=request.auto_start
        )
        return WorkspaceResponse(workspace=workspace)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest):
    """更新工作区"""
    manager = get_manager()

    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    workspace = manager.update_workspace(workspace_id, **update_data)

    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    return WorkspaceResponse(workspace=workspace)


@router.delete("/{workspace_id}", response_model=DeleteResponse)
async def delete_workspace(
    workspace_id: str,
    delete_data: bool = Query(default=False, description="是否同时删除工作目录")
):
    """删除工作区"""
    manager = get_manager()

    workspace = manager.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    success = manager.delete_workspace(workspace_id, delete_data=delete_data)

    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return DeleteResponse(success=True)


@router.post("/{workspace_id}/start", response_model=StartResponse)
async def start_workspace(workspace_id: str):
    """启动工作区"""
    manager = get_manager()

    workspace = manager.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    try:
        result = manager.start_workspace(workspace_id)
        return StartResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workspace_id}/stop", response_model=StopResponse)
async def stop_workspace(workspace_id: str):
    """停止工作区"""
    manager = get_manager()

    workspace = manager.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    try:
        manager.stop_workspace(workspace_id)
        return StopResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/health", response_model=HealthResponse)
async def check_workspace_health(workspace_id: str):
    """检测单个工作区健康状态"""
    manager = get_manager()

    workspace = manager.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    is_healthy = manager.check_workspace_health(workspace_id)
    return HealthResponse(
        workspace_id=workspace_id,
        name=workspace.meta.name,
        is_healthy=is_healthy
    )


@router.get("/health", response_model=list[HealthResponse])
async def check_all_workspaces_health():
    """批量检测所有工作区健康状态"""
    manager = get_manager()
    manager.check_all_workspaces_health()
    workspaces = manager.list_workspaces()

    return [
        HealthResponse(
            workspace_id=ws.id,
            name=ws.name,
            is_healthy=ws.is_healthy
        )
        for ws in workspaces
    ]
