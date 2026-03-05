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


def _get_copaw_cmd() -> tuple[Optional[str], str]:
    """
    获取 copaw 命令的完整路径和执行方式

    Returns:
        (命令路径，执行方式) 元组
        - 执行方式："direct" 直接执行 .exe
                   "powershell" 通过 PowerShell 执行 .ps1
                   "shell" 通过 shell 执行命令字符串
    """
    copaw_path = shutil.which("copaw")
    if not copaw_path:
        return None, "direct"

    if sys.platform == "win32":
        # 1. 优先查找 copaw.ps1 脚本
        copaw_ps1 = Path(copaw_path).with_suffix('.ps1')
        if copaw_ps1.exists():
            return str(copaw_ps1), "powershell"

        # 2. 检查 .copaw/bin 目录下是否有 .ps1 文件
        if 'copaw' in str(copaw_path).lower():
            copaw_bin_dir = Path(copaw_path).parent
            copaw_ps1 = copaw_bin_dir / "copaw.ps1"
            if copaw_ps1.exists():
                return str(copaw_ps1), "powershell"

        # 3. 查找 copaw.exe，避免使用 .cmd 包装器
        copaw_exe = Path(copaw_path).with_suffix('.exe')
        if copaw_exe.exists():
            return str(copaw_exe), "shell"

        # 4. 尝试从 .cmd 路径推导出实际的 .exe 路径
        if 'copaw' in str(copaw_path).lower():
            # 典型路径：C:\Users\xxx\.copaw\bin\copaw.cmd
            # 实际 exe：C:\Users\xxx\.copaw\venv\Scripts\copaw.exe
            copaw_home = Path(copaw_path).parent.parent
            copaw_exe = copaw_home / "venv" / "Scripts" / "copaw.exe"
            if copaw_exe.exists():
                return str(copaw_exe), "shell"

        # 5. 最后才使用 .cmd 文件
        return copaw_path, "shell"

    return copaw_path, "direct"


def _run_copaw_command(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """
    运行 copaw 命令（处理 Windows 上的 .ps1/.cmd 文件）

    Args:
        args: 命令参数列表（不包含 "copaw"）
        **kwargs: 传递给 subprocess.run 的其他参数

    Returns:
        subprocess.CompletedProcess 对象
    """
    copaw_cmd, exec_mode = _get_copaw_cmd()
    if not copaw_cmd:
        raise FileNotFoundError("CoPaw 未安装或不在 PATH 中")

    # 在 Windows 上，需要根据执行方式处理
    if sys.platform == "win32":
        import shlex

        if exec_mode == "powershell":
            # 使用 PowerShell 执行 .ps1 脚本
            # 格式：powershell.exe -ExecutionPolicy Bypass -File xxx.ps1 arg1 arg2
            ps_args = " ".join(shlex.quote(arg) for arg in args)
            # 添加 -OutputFormat Text 和 -InputFormat None 以确保正确的文本输出
            cmd_str = f'powershell.exe -ExecutionPolicy Bypass -OutputFormat Text -InputFormat None -File "{copaw_cmd}" {ps_args}'
            kwargs["shell"] = True
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            # 设置 UTF-8 编码以处理 PowerShell 输出
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"
            return subprocess.run(cmd_str, **kwargs)

        elif exec_mode == "shell":
            # 使用 shell 执行命令字符串（适用于 .exe 或 .cmd）
            cmd_str = copaw_cmd + " " + " ".join(shlex.quote(arg) for arg in args)
            kwargs["shell"] = True
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            return subprocess.run(cmd_str, **kwargs)

        else:
            # 直接执行（非 Windows 或不需要特殊处理）
            cmd = [copaw_cmd] + args
            return subprocess.run(cmd, **kwargs)
    else:
        cmd = [copaw_cmd] + args
        return subprocess.run(cmd, **kwargs)


def check_copaw_installed() -> bool:
    """
    检查是否安装了 CoPaw

    Returns:
        bool: 是否安装了 CoPaw
    """
    try:
        result = _run_copaw_command(
            ["--help"],
            capture_output=True,
            text=True,
            timeout=10,  # Windows 上首次执行可能需要加载环境，给 10 秒超时
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


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
        self._lock_file = self.base_dir / "manager.lock"

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

    # ========== 锁文件管理 ==========
    def _acquire_lock(self, port: int) -> None:
        """
        获取锁文件

        Args:
            port: Manager 端口

        Raises:
            RuntimeError: 如果已有 Manager 在运行
        """
        if self._lock_file.exists():
            try:
                with open(self._lock_file, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                pid = lock_data.get("pid")
                if pid:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        raise RuntimeError(
                            f"已有 Manager 在运行（PID: {pid}, 端口：{lock_data.get('port')}）\n"
                            f"如需停止，请运行：copaw-app-manager quit"
                        )
            except psutil.NoSuchProcess:
                # 进程不存在，清理旧锁文件
                self._release_lock()
            except json.JSONDecodeError:
                # 锁文件损坏，清理
                self._release_lock()

        # 写入锁文件
        self._write_lock(port)

    def _write_lock(self, port: int) -> None:
        """
        写入锁文件

        Args:
            port: Manager 端口
        """
        lock_data = {
            "pid": os.getpid(),
            "port": port,
            "started_at": datetime.now().isoformat()
        }
        with open(self._lock_file, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, ensure_ascii=False, indent=2)

    def _release_lock(self) -> None:
        """删除锁文件"""
        if self._lock_file.exists():
            try:
                self._lock_file.unlink()
            except Exception as e:
                print(f"删除锁文件失败：{e}")

    def _read_lock(self) -> Optional[dict]:
        """
        读取锁文件

        Returns:
            锁文件数据，不存在则返回 None
        """
        if not self._lock_file.exists():
            return None
        try:
            with open(self._lock_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
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
        
        # 并发检测所有端口状态
        def check_port(ws_meta):
            port_responding = False
            try:
                response = requests.get(
                    f"http://127.0.0.1:{ws_meta.port}/api/version",
                    timeout=0.5
                )
                port_responding = response.status_code == 200
            except Exception:
                pass
            return ws_meta.id, port_responding
        
        # 并发检测所有工作区端口
        from concurrent.futures import ThreadPoolExecutor
        port_status = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(check_port, meta.workspaces)
            for ws_id, status in results:
                port_status[ws_id] = status
        
        # 构建工作区列表
        workspaces = []
        for ws_meta in meta.workspaces:
            runtime = self._get_runtime(ws_meta.id)
            port_responding = port_status.get(ws_meta.id, False)
            
            # 根据端口响应更新运行时状态
            if port_responding:
                if runtime.status != WorkspaceStatus.RUNNING:
                    runtime = WorkspaceRuntime(
                        status=WorkspaceStatus.RUNNING,
                        pid=None,
                        is_healthy=True
                    )
                    self._set_runtime(ws_meta.id, runtime)
            else:
                if runtime.status == WorkspaceStatus.RUNNING:
                    runtime = WorkspaceRuntime(
                        status=WorkspaceStatus.STOPPED,
                        pid=None,
                        is_healthy=None
                    )
                    self._set_runtime(ws_meta.id, runtime)
            
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

    def _kill_process_by_port(self, port: int):
        """
        根据端口号查找并杀死占用该端口的进程

        Args:
            port: 端口号
        """
        try:
            # 遍历所有网络连接，查找占用指定端口的进程
            for conn in psutil.net_connections(kind='tcp'):
                # 检查本地端口是否匹配
                if conn.laddr.port == port:
                    if conn.pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            proc.terminate()
                            proc.wait(timeout=5)
                        except psutil.NoSuchProcess:
                            pass
                        except psutil.TimeoutExpired:
                            proc.kill()
                        except psutil.AccessDenied:
                            # 没有权限访问该进程，尝试用系统命令
                            self._kill_process_by_port_cmd(port)
        except psutil.AccessDenied:
            # 没有权限获取网络连接，使用系统命令
            self._kill_process_by_port_cmd(port)
        except Exception as e:
            print(f"根据端口查找进程失败：{e}")
            self._kill_process_by_port_cmd(port)

    def _kill_process_by_port_cmd(self, port: int):
        """
        使用系统命令根据端口杀进程（备用方案）

        Args:
            port: 端口号
        """
        if sys.platform == "win32":
            try:
                # Windows: 使用 netstat 找到 PID，然后 taskkill
                result = subprocess.run(
                    f'netstat -ano | findstr :{port}',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if 'LISTENING' in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                try:
                                    subprocess.run(
                                        f'taskkill /F /PID {pid}',
                                        shell=True,
                                        capture_output=True
                                    )
                                except Exception:
                                    pass
            except Exception as e:
                print(f"Windows 上根据端口杀进程失败：{e}")
        else:
            # Linux/Mac: 使用 lsof 或 fuser
            try:
                result = subprocess.run(
                    f'lsof -ti :{port}',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    for pid in result.stdout.strip().split('\n'):
                        if pid:
                            try:
                                subprocess.run(['kill', '-9', pid])
                            except Exception:
                                pass
            except Exception as e:
                print(f"Unix 上根据端口杀进程失败：{e}")

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

        # ========== 初始化工作目录 ==========
        # 检查是否安装了 CoPaw
        copaw_installed = check_copaw_installed()

        if copaw_installed:
            # 设置环境变量，确保 copaw init 初始化到正确位置
            env = os.environ.copy()
            env["COPAW_WORKING_DIR"] = working_dir

            try:
                # 调用 copaw init --defaults --accept-security 自动初始化
                result = _run_copaw_command(
                    ["init", "--defaults", "--accept-security"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,  # 超时 2 分钟
                )

                if result.returncode != 0:
                    # 初始化失败，清理已创建的目录
                    shutil.rmtree(working_dir, ignore_errors=True)
                    raise RuntimeError(f"初始化工作区失败：{result.stderr}")

            except subprocess.TimeoutExpired:
                shutil.rmtree(working_dir, ignore_errors=True)
                raise RuntimeError("初始化超时（2 分钟）")
        else:
            # CoPaw 未安装，创建空的工作区配置
            # 用户可以在之后手动初始化或安装 CoPaw
            config_file = Path(working_dir) / "config.json"
            config_file.write_text('{"initialized": false, "note": "请先安装 CoPaw: pip install copaw"}', encoding='utf-8')

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
            RuntimeError: 工作区未初始化或 CoPaw 未安装
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

        # 3. 检查是否安装了 CoPaw
        if not check_copaw_installed():
            raise RuntimeError(
                "CoPaw 未安装，无法启动 APP。\n"
                "请先安装 CoPaw: pip install copaw\n"
                "或安装完整版本：pip install copaw-app-manager[copaw]"
            )

        # 4. 如果之前记录的 PID 进程还在，先清理
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

        # 获取 copaw 命令路径和执行方式
        copaw_cmd, exec_mode = _get_copaw_cmd()
        if not copaw_cmd:
            raise RuntimeError("CoPaw 未安装或不在 PATH 中")

        # Windows 上需要根据执行方式构建命令
        if sys.platform == "win32":
            import shlex
            app_args = "app --port " + str(workspace.meta.port) + " --host 127.0.0.1"

            if exec_mode == "powershell":
                # 使用 PowerShell 执行 .ps1 脚本
                cmd_str = f'powershell.exe -ExecutionPolicy Bypass -File "{copaw_cmd}" {app_args}'
                proc = subprocess.Popen(
                    cmd_str,
                    env=env,
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                # 使用 shell 执行命令字符串（适用于 .exe 或 .cmd）
                cmd_str = copaw_cmd + " " + app_args
                proc = subprocess.Popen(
                    cmd_str,
                    env=env,
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
        else:
            proc = subprocess.Popen(
                [copaw_cmd, "app", "--port", str(workspace.meta.port), "--host", "127.0.0.1"],
                env=env,
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

        # 1. 根据 PID 杀进程
        if workspace.runtime.pid:
            try:
                proc = psutil.Process(workspace.runtime.pid)
                proc.terminate()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
            except psutil.TimeoutExpired:
                proc.kill()

        # 2. 根据端口查找并杀死进程（防止 PID 失效或端口不一致）
        if workspace.meta.port:
            self._kill_process_by_port(workspace.meta.port)

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

        # 如果内存中不是运行状态，尝试检测端口是否有服务响应
        if workspace.runtime.status != WorkspaceStatus.RUNNING:
            try:
                response = requests.get(
                    f"http://127.0.0.1:{workspace.meta.port}/api/version",
                    timeout=1
                )
                if response.status_code == 200:
                    # 端口有响应，更新为运行状态
                    runtime = WorkspaceRuntime(
                        status=WorkspaceStatus.RUNNING,
                        pid=None,
                        is_healthy=True
                    )
                    self._set_runtime(workspace_id, runtime)
                    return True
            except Exception:
                pass
            # 端口无响应，保持停止状态
            runtime = self._get_runtime(workspace_id)
            runtime.is_healthy = None
            self._set_runtime(workspace_id, runtime)
            return False

        # 检查进程是否还存在
        if workspace.runtime.pid:
            try:
                proc = psutil.Process(workspace.runtime.pid)
                if not proc.is_running():
                    # 进程不存在，检查端口是否有其他进程
                    try:
                        response = requests.get(
                            f"http://127.0.0.1:{workspace.meta.port}/api/version",
                            timeout=1
                        )
                        if response.status_code == 200:
                            is_healthy = True
                        else:
                            is_healthy = False
                    except Exception:
                        is_healthy = False
                    
                    runtime = self._get_runtime(workspace_id)
                    runtime.is_healthy = is_healthy
                    if not is_healthy:
                        runtime.status = WorkspaceStatus.STOPPED
                        runtime.pid = None
                    self._set_runtime(workspace_id, runtime)
                    return is_healthy
            except psutil.NoSuchProcess:
                # 进程不存在，检查端口
                pass

        # 调用 CoPaw 现有接口检测（使用 /api/version）
        try:
            response = requests.get(
                f"http://127.0.0.1:{workspace.meta.port}/api/version",
                timeout=1
            )
            is_healthy = response.status_code == 200
        except Exception:
            is_healthy = False

        # 更新运行时状态（内存中）
        runtime = self._get_runtime(workspace_id)
        runtime.is_healthy = is_healthy
        if not is_healthy:
            runtime.status = WorkspaceStatus.STOPPED
            runtime.pid = None
        self._set_runtime(workspace_id, runtime)

        return is_healthy

    def check_all_workspaces_health(self):
        """检测所有工作区健康状态"""
        for ws in self.list_workspaces():
            # 检测所有工作区，无论状态如何
            try:
                self.check_workspace_health(ws.id)
            except Exception as e:
                print(f"检测 {ws.name} 健康状态失败：{e}")
