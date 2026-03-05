"""核心服务模块 - 工作区管理器"""

import os
import json
import socket
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
import psutil
import requests

from copaw_app_manager.models.workspace import (
    WorkspaceMeta,
    WorkspaceRuntime,
    Workspace,
    WorkspaceStatus,
    WorkspacesMeta,
)


class WorkspaceManager:
    """工作区管理器 - 负责 CRUD 和生命周期管理"""

    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化工作区管理器

        Args:
            base_dir: 元数据存放目录，默认从环境变量读取或使用 ~/.copaw_app_manager
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(os.getenv(
                "COPAW_APP_MANAGER_DIR",
                Path.home() / ".copaw_app_manager"
            ))

        self.meta_file = self.base_dir / "workspaces.json"
        self.apps_dir = self.base_dir / "apps"

        # 运行时状态缓存（内存中，不持久化）
        self._runtime_cache: dict[str, WorkspaceRuntime] = {}

        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.apps_dir.mkdir(parents=True, exist_ok=True)

    # ========== 持久化 ==========
    def load(self) -> WorkspacesMeta:
        """从文件加载元数据（只加载持久化字段）"""
        if not self.meta_file.exists():
            return WorkspacesMeta()

        try:
            with open(self.meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WorkspacesMeta(**data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"加载元数据失败：{e}")
            return WorkspacesMeta()

    def save(self, meta: WorkspacesMeta):
        """保存元数据到文件（只保存持久化字段）"""
        meta.last_modified = datetime.now()
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(meta.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    def _save_workspace_meta(self, workspace_meta: WorkspaceMeta):
        """保存单个工作区元数据"""
        meta = self.load()
        for i, ws in enumerate(meta.workspaces):
            if ws.id == workspace_meta.id:
                meta.workspaces[i] = workspace_meta
                break
        else:
            meta.workspaces.append(workspace_meta)
        self.save(meta)

    def _get_workspace_meta(self, workspace_id: str) -> Optional[WorkspaceMeta]:
        """获取单个工作区元数据"""
        meta = self.load()
        for ws in meta.workspaces:
            if ws.id == workspace_id:
                return ws
        return None

    # ========== 运行时状态管理 ==========
    def _get_runtime(self, workspace_id: str) -> WorkspaceRuntime:
        """获取运行时状态"""
        return self._runtime_cache.get(workspace_id, WorkspaceRuntime())

    def _set_runtime(self, workspace_id: str, runtime: WorkspaceRuntime):
        """设置运行时状态"""
        self._runtime_cache[workspace_id] = runtime

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """
        获取完整的 APP 信息（包含运行时状态）

        Args:
            workspace_id: 工作区 ID

        Returns:
            完整的 Workspace 对象，不存在则返回 None
        """
        meta = self._get_workspace_meta(workspace_id)
        if not meta:
            return None

        runtime = self._get_runtime(workspace_id)
        return Workspace(meta=meta, runtime=runtime)

    def list_workspaces(self) -> list[Workspace]:
        """列出所有工作区（包含运行时状态）"""
        meta = self.load()
        workspaces = []
        for ws_meta in meta.workspaces:
            runtime = self._get_runtime(ws_meta.id)
            workspaces.append(Workspace(meta=ws_meta, runtime=runtime))
        return workspaces

    # ========== 端口管理 ==========
    def _is_port_in_use(self, port: int) -> bool:
        """检查端口是否被其他应用占用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('127.0.0.1', port)) == 0
        except Exception:
            return False

    def find_available_port(self, start_port: int = 8088) -> int:
        """
        找可用端口

        Args:
            start_port: 起始端口，默认 8088

        Returns:
            可用端口号
        """
        meta = self.load()
        allocated_ports = set(ws.port for ws in meta.workspaces)

        # 从最大已分配端口 +1 开始
        if allocated_ports:
            start_port = max(allocated_ports) + 1

        port = start_port
        while True:
            # 先排除已分配给其他 APP 的端口
            if port in allocated_ports:
                port += 1
                continue

            # 再检查是否被其他应用占用
            if not self._is_port_in_use(port):
                return port

            port += 1

    # ========== CRUD ==========
    def create_workspace(
        self,
        name: str,
        description: str = "",
        working_dir: Optional[str] = None,
        auto_start: bool = False
    ) -> Workspace:
        """
        创建新工作区

        Args:
            name: 工作区名称
            description: 描述
            working_dir: 工作目录（留空则自动创建）
            auto_start: 是否自动启动

        Returns:
            创建的工作区对象
        """
        # 生成 ID
        workspace_id = str(uuid.uuid4())

        # 自动分配端口
        port = self.find_available_port()

        # 自动生成工作目录（如果未指定）
        if not working_dir:
            working_dir = str(self.apps_dir / workspace_id)

        # 创建工作目录
        Path(working_dir).mkdir(parents=True, exist_ok=True)

        # ========== 关键：初始化工作目录 ==========
        # 设置环境变量，确保 copaw init 初始化到正确位置
        env = os.environ.copy()
        env["COPAW_WORKING_DIR"] = working_dir

        try:
            # 调用 copaw init --defaults --accept-security 自动初始化
            result = subprocess.run(
                ["copaw", "init", "--defaults", "--accept-security"],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,  # 超时 2 分钟
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )

            if result.returncode != 0:
                # 初始化失败，清理已创建的目录
                shutil.rmtree(working_dir, ignore_errors=True)
                raise RuntimeError(f"初始化工作区失败：{result.stderr}")

        except FileNotFoundError:
            # copaw 命令不存在，清理目录并报错
            shutil.rmtree(working_dir, ignore_errors=True)
            raise RuntimeError("copaw 命令不存在，请先安装 CoPaw")
        except subprocess.TimeoutExpired:
            shutil.rmtree(working_dir, ignore_errors=True)
            raise RuntimeError("初始化超时（2 分钟）")

        # 创建元数据
        workspace_meta = WorkspaceMeta(
            id=workspace_id,
            name=name,
            description=description,
            auto_start=auto_start,
            working_dir=working_dir,
            port=port,
        )

        # 保存元数据
        self._save_workspace_meta(workspace_meta)

        # 初始化运行时状态
        self._set_runtime(workspace_id, WorkspaceRuntime())

        return Workspace(meta=workspace_meta, runtime=WorkspaceRuntime())

    def update_workspace(self, workspace_id: str, **kwargs) -> Optional[Workspace]:
        """
        更新工作区信息

        Args:
            workspace_id: 工作区 ID
            **kwargs: 要更新的字段（只能是元数据字段）

        Returns:
            更新后的工作区，不存在则返回 None
        """
        meta = self._get_workspace_meta(workspace_id)
        if not meta:
            return None

        # 只更新元数据字段
        valid_fields = {"name", "description", "auto_start", "working_dir", "port"}
        for key, value in kwargs.items():
            if key in valid_fields and hasattr(meta, key):
                setattr(meta, key, value)

        self._save_workspace_meta(meta)
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str, delete_data: bool = False) -> bool:
        """
        删除工作区

        Args:
            workspace_id: 工作区 ID
            delete_data: 是否同时删除工作目录

        Returns:
            是否删除成功
        """
        meta = self.load()
        for i, ws in enumerate(meta.workspaces):
            if ws.id == workspace_id:
                # 如果正在运行，先停止
                runtime = self._get_runtime(workspace_id)
                if runtime.status == WorkspaceStatus.RUNNING:
                    self.stop_workspace(workspace_id)

                # 删除工作目录
                if delete_data and ws.working_dir:
                    try:
                        shutil.rmtree(ws.working_dir, ignore_errors=True)
                    except Exception as e:
                        print(f"删除工作目录失败：{e}")

                # 从元数据中移除
                meta.workspaces.pop(i)
                self.save(meta)

                # 清除运行时缓存
                self._runtime_cache.pop(workspace_id, None)
                return True

        return False

    # ========== 生命周期 ==========
    def start_workspace(self, workspace_id: str) -> dict:
        """
        启动工作区

        Args:
            workspace_id: 工作区 ID

        Returns:
            {"success": True, "url": "http://..."}

        Raises:
            FileNotFoundError: 工作目录不存在
            RuntimeError: 工作区未初始化
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise FileNotFoundError(f"工作区不存在：{workspace_id}")

        # ========== 启动前检查 ==========
        # 1. 检查工作目录是否存在
        if not Path(workspace.meta.working_dir).exists():
            raise FileNotFoundError(f"工作目录不存在：{workspace.meta.working_dir}")

        # 2. 检查配置文件是否存在（确保已初始化）
        config_file = Path(workspace.meta.working_dir) / "config.json"
        if not config_file.exists():
            raise RuntimeError(
                f"工作区未初始化，请先运行初始化：{workspace.meta.working_dir}\n"
                "或删除该工作区后重新创建"
            )

        # 3. 如果之前记录的 PID 进程还在，先清理
        if workspace.runtime.pid:
            try:
                proc = psutil.Process(workspace.runtime.pid)
                proc.terminate()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
            except psutil.TimeoutExpired:
                proc.kill()

        # ========== 启动进程 ==========
        env = os.environ.copy()
        env["COPAW_WORKING_DIR"] = workspace.meta.working_dir

        # 启动子进程（保留日志输出便于排查）
        proc = subprocess.Popen(
            ["copaw", "app", "--port", str(workspace.meta.port), "--host", "127.0.0.1"],
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )

        # 更新运行时状态（内存中）
        self._set_runtime(workspace_id, WorkspaceRuntime(
            status=WorkspaceStatus.RUNNING,
            pid=proc.pid,
        ))

        # 更新元数据（持久化）
        workspace.meta.last_started = datetime.now()
        self._save_workspace_meta(workspace.meta)

        # 等待服务启动（轮询检测）
        import time
        max_wait = 30  # 最多等待 30 秒
        start_time = time.time()
        service_ready = False

        while time.time() - start_time < max_wait:
            try:
                response = requests.get(
                    f"http://127.0.0.1:{workspace.meta.port}/api/version",
                    timeout=2
                )
                if response.status_code == 200:
                    service_ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        
        if not service_ready:
            # 服务未就绪，但进程已启动，返回警告
            print(f"警告：APP 启动后 {max_wait}秒内未就绪，但进程已在运行 (PID: {proc.pid})")

        return {"success": True, "url": f"http://127.0.0.1:{workspace.meta.port}"}

    def stop_workspace(self, workspace_id: str) -> Workspace:
        """
        停止工作区

        Args:
            workspace_id: 工作区 ID

        Returns:
            更新后的工作区
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise FileNotFoundError(f"工作区不存在：{workspace_id}")

        if workspace.runtime.pid:
            try:
                proc = psutil.Process(workspace.runtime.pid)
                proc.terminate()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
            except psutil.TimeoutExpired:
                proc.kill()

        # 重置运行时状态（内存中）
        self._set_runtime(workspace_id, WorkspaceRuntime(
            status=WorkspaceStatus.STOPPED,
            pid=None,
            is_healthy=None,
        ))

        return self.get_workspace(workspace_id)

    def stop_all_workspaces(self):
        """停止所有运行中的工作区"""
        for ws in self.list_workspaces():
            if ws.runtime.status == WorkspaceStatus.RUNNING:
                try:
                    self.stop_workspace(ws.id)
                except Exception as e:
                    print(f"停止 {ws.name} 失败：{e}")

    # ========== 心跳检测 ==========
    def check_workspace_health(self, workspace_id: str) -> bool:
        """
        检测工作区健康状态

        Args:
            workspace_id: 工作区 ID

        Returns:
            是否健康
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return False

        if workspace.runtime.status != WorkspaceStatus.RUNNING:
            runtime = self._get_runtime(workspace_id)
            runtime.is_healthy = None
            self._set_runtime(workspace_id, runtime)
            return False

        # 检查进程是否还存在
        if workspace.runtime.pid:
            try:
                proc = psutil.Process(workspace.runtime.pid)
                if not proc.is_running():
                    runtime = self._get_runtime(workspace_id)
                    runtime.is_healthy = False
                    self._set_runtime(workspace_id, runtime)
                    return False
            except psutil.NoSuchProcess:
                runtime = self._get_runtime(workspace_id)
                runtime.is_healthy = False
                self._set_runtime(workspace_id, runtime)
                return False

        # 调用 CoPaw 现有接口检测（使用 /api/version）
        try:
            response = requests.get(
                f"http://127.0.0.1:{workspace.meta.port}/api/version",
                timeout=3
            )
            is_healthy = response.status_code == 200
        except Exception:
            is_healthy = False

        # 更新运行时状态（内存中）
        runtime = self._get_runtime(workspace_id)
        runtime.is_healthy = is_healthy
        self._set_runtime(workspace_id, runtime)

        return is_healthy

    def check_all_workspaces_health(self):
        """检测所有工作区健康状态"""
        for ws in self.list_workspaces():
            if ws.runtime.status == WorkspaceStatus.RUNNING:
                try:
                    self.check_workspace_health(ws.id)
                except Exception as e:
                    print(f"检测 {ws.name} 健康状态失败：{e}")
