"""数据模型模块 - 定义工作区相关的 Pydantic 模型"""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid
from typing import Optional


class WorkspaceStatus(str, Enum):
    """工作区状态枚举"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class WorkspaceMeta(BaseModel):
    """
    需要持久化的 APP 元数据
    这些字段会保存到 workspaces.json
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    auto_start: bool = False
    working_dir: str
    port: int = 8088
    created_at: datetime = Field(default_factory=datetime.now)
    last_started: Optional[datetime] = None


class WorkspaceRuntime(BaseModel):
    """
    运行时状态，不持久化
    重启后重置为默认值
    """
    status: WorkspaceStatus = WorkspaceStatus.STOPPED
    pid: Optional[int] = None
    is_healthy: Optional[bool] = None


class Workspace(BaseModel):
    """
    完整的 APP 数据结构 = 元数据 + 运行时状态
    用于 API 响应和内部处理
    """
    meta: WorkspaceMeta
    runtime: WorkspaceRuntime = Field(default_factory=WorkspaceRuntime)

    # ========== 便捷访问属性（兼容旧代码）==========
    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def description(self) -> str:
        return self.meta.description

    @property
    def auto_start(self) -> bool:
        return self.meta.auto_start

    @property
    def working_dir(self) -> str:
        return self.meta.working_dir

    @property
    def port(self) -> int:
        return self.meta.port

    @property
    def created_at(self) -> datetime:
        return self.meta.created_at

    @property
    def last_started(self) -> Optional[datetime]:
        return self.meta.last_started

    @property
    def status(self) -> WorkspaceStatus:
        return self.runtime.status

    @property
    def pid(self) -> Optional[int]:
        return self.runtime.pid

    @property
    def is_healthy(self) -> Optional[bool]:
        return self.runtime.is_healthy


class WorkspacesMeta(BaseModel):
    """工作区元数据集合（只包含持久化字段）"""
    version: int = 1
    last_modified: datetime = Field(default_factory=datetime.now)
    workspaces: list[WorkspaceMeta] = []
