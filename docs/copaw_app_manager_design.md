# CoPaw APP Manager - 需求与设计文档

## 📋 一、需求背景

### 1.1 现状问题

当前 CoPaw 是**单实例模式**：
- 所有配置、记忆、技能都存储在 `~/.copaw` 目录
- 用户需要手动管理多个工作区时，不够便捷
- 需要为不同用途（工作、个人、测试等）创建独立环境时，操作繁琐

### 1.2 需求目标

开发一个独立的 **APP Manager 服务**，实现：
1. **多工作区管理** — 轻松创建、启动、停止、删除多个 CoPaw 实例
2. **统一管理界面** — 通过 Web 界面管理所有 APP
3. **隔离存储** — 每个 APP 有独立的工作目录、端口配置
4. **零侵入** — 不修改原 CoPaw 代码，避免与上游更新冲突

---

## 🎯 二、功能需求

### 2.1 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 创建 APP | 指定名称、工作目录（自动分配端口），创建新 APP | P0 |
| 列出 APP | 显示所有 APP 及其状态（运行中/已停止） | P0 |
| 启动 APP | 启动指定 APP 的 CoPaw 服务，启动成功后自动跳转 | P0 |
| 停止 APP | 停止指定 APP 的 CoPaw 服务 | P0 |
| 删除 APP | 删除 APP 元数据 + 工作目录（需用户确认） | P1 |
| 心跳检测 | 定时检测所有 APP 的健康状态 | P1 |
| Manager 停止 | 可选是否连带停止所有运行中的 APP | P1 |

### 2.2 管理界面功能

- 显示 APP 列表，每行显示：名称、状态、端口、工作目录
- 操作按钮：启动（跳转）、停止、编辑、删除
- 心跳状态指示器（绿色=正常，红色=异常）
- 点击启动后跳转到对应端口的 CoPaw 控制台（新标签页）

### 2.3 命令行功能

```bash
# 启动管理界面
copaw_app_manager start                    # 默认端口 8000
copaw_app_manager start --port 9000        # 指定管理界面端口
copaw_app_manager start --stop-apps        # 停止时连带停止所有 APP

# 列出所有 APP
copaw_app_manager list

# 创建 APP
copaw_app_manager create --name my-project                                    # 自动生成工作目录
copaw_app_manager create --name my-project --working-dir D:/my/copaw         # 指定工作目录
copaw_app_manager create --name my-project --description "测试用" --auto-start  # 带描述、自动启动

# 启动/停止/删除
copaw_app_manager start-app work
copaw_app_manager stop-app work
copaw_app_manager delete work              # 默认不删除工作目录
copaw_app_manager delete work --force      # 强制删除工作目录
```

---

## 🏗️ 三、技术设计

### 3.1 项目结构

```
src/
├── copaw_app_manager/        # 新增目录
│   ├── __init__.py
│   ├── __main__.py          # python -m copaw_app_manager
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py          # CLI 入口
│   ├── app/
│   │   ├── __init__.py
│   │   └── _app.py          # FastAPI 主应用
│   ├── models/
│   │   ├── __init__.py
│   │   └── workspace.py     # Pydantic 数据模型
│   ├── service/
│   │   ├── __init__.py
│   │   └── manager.py      # 核心管理逻辑
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── workspaces.py   # CRUD API
│   │   └── app_ctrl.py    # 启动/停止 API
│   ├── static/
│   │   ├── style.css
│   │   └── app.js
│   └── templates/
│       └── index.html
```

### 3.2 元数据结构

#### 工作区元数据文件

```json
// 默认位置: ~/.copaw_app_manager/workspaces.json
// 注意：只保存需要持久化的字段，status/pid/is_healthy 不保存
{
    "version": 1,
    "last_modified": "2026-03-02T10:00:00Z",
    "workspaces": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "工作区A",
            "description": "主要用于日常办公",
            "auto_start": true,
            "working_dir": "D:/AI/copaw-projects/work-a",
            "port": 8088,
            "created_at": "2026-01-01T08:00:00Z",
            "last_started": "2026-03-02T10:30:00Z"
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "个人项目",
            "description": "个人学习测试用",
            "auto_start": false,
            "working_dir": "C:/Users/用户/.copaw_app_manager/apps/550e8400-e29b-41d4-a716-446655440001",
            "port": 8089,
            "created_at": "2026-01-15T08:00:00Z",
            "last_started": null
        }
    ]
}
```

#### 数据模型

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

class WorkspaceStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

# ========== 需要持久化的字段 ==========
class WorkspaceMeta(BaseModel):
    """需要持久化的 APP 元数据"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 随机 UUID
    name: str                                           # 名称（必填）
    description: str = ""                               # 描述（可选）
    auto_start: bool = False                             # 是否自动启动
    working_dir: str                                    # 工作目录
    port: int = 8088                                    # 端口
    created_at: datetime = Field(default_factory=datetime.now)
    last_started: Optional[datetime] = None            # 上次启动时间

# ========== 运行时状态（不持久化） ==========
class WorkspaceRuntime(BaseModel):
    """运行时状态，不持久化，重启后重置"""
    status: WorkspaceStatus = WorkspaceStatus.STOPPED
    pid: Optional[int] = None
    is_healthy: Optional[bool] = None

class Workspace(BaseModel):
    """完整的 APP 数据结构 = 元数据 + 运行时状态"""
    meta: WorkspaceMeta
    runtime: WorkspaceRuntime = Field(default_factory=WorkspaceRuntime)
```

### 元数据文件（只保存需要持久化的部分）

```json
// 默认位置: ~/.copaw_app_manager/workspaces.json
{
    "version": 1,
    "last_modified": "2026-03-02T10:00:00Z",
    "workspaces": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "工作区A",
            "description": "主要用于日常办公",
            "auto_start": true,
            "working_dir": "D:/AI/copaw-projects/work-a",
            "port": 8088,
            "created_at": "2026-01-01T08:00:00Z",
            "last_started": "2026-03-02T10:30:00Z"
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "个人项目",
            "description": "个人学习测试用",
            "auto_start": false,
            "working_dir": "C:/Users/用户/.copaw_app_manager/apps/550e8400-e29b-41d4-a716-446655440001",
            "port": 8089,
            "created_at": "2026-01-15T08:00:00Z",
            "last_started": null
        }
    ]
}
```

### 运行时状态管理

```python
class WorkspaceManager:
    """工作区管理器"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.meta_file = base_dir / "workspaces.json"
        # 运行时状态存储在内存中
        self._runtime_cache: dict[str, WorkspaceRuntime] = {}
    
    def get_workspace(self, workspace_id: str) -> Workspace:
        """获取完整的 APP 信息（包含运行时状态）"""
        meta = self._get_workspace_meta(workspace_id)
        runtime = self._runtime_cache.get(workspace_id, WorkspaceRuntime())
        return Workspace(meta=meta, runtime=runtime)
    
    def start_workspace(self, workspace_id: str) -> dict:
        """启动工作区"""
        ws = self.get_workspace(workspace_id)
        # ... 启动逻辑 ...
        
        # 更新运行时状态（内存中）
        self._runtime_cache[workspace_id] = WorkspaceRuntime(
            status=WorkspaceStatus.RUNNING,
            pid=proc.pid,
        )
        
        return {"success": True, "url": f"http://127.0.0.1:{ws.meta.port}"}
    
    def stop_workspace(self, workspace_id: str):
        """停止工作区"""
        # ... 停止逻辑 ...
        
        # 重置运行时状态
        self._runtime_cache[workspace_id] = WorkspaceRuntime(
            status=WorkspaceStatus.STOPPED,
            pid=None,
            is_healthy=None,
        )
    
    def load(self) -> WorkspacesMeta:
        """从文件加载元数据（不包含运行时状态）"""
        # 只加载持久化的元数据
        pass
    
    def save(self, meta: WorkspacesMeta):
        """保存元数据到文件（不保存运行时状态）"""
        # 只保存持久化的元数据
        pass
```

### 3.3 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `COPAW_APP_MANAGER_DIR` | `~/.copaw_app_manager` | Manager 元数据存放目录 |
| `COPAW_APP_MANAGER_PORT` | `8000` | 管理界面端口 |

### 3.4 工作目录规则

- **用户指定**：创建 APP 时，用户可手动指定工作目录
- **默认路径**：如果用户未指定，使用 `{COPAW_APP_MANAGER_DIR}/apps/{app_id}/` 格式
  - 示例：`~/.copaw_app_manager/apps/550e8400-e29b-41d4-a716-446655440000/`
- **自动创建**：如果默认目录不存在，运行时自动创建

### 3.5 跨平台启动说明

**Windows 平台注意事项**：由于 CoPaw 本身在 Windows 上使用 cmd 存在问题，APP Manager 在 Windows 上统一使用 PowerShell 启动所有 copaw 命令：

```python
if sys.platform == "win32":
    # 使用 PowerShell 启动
    subprocess.run(["powershell", "-Command", "copaw init ..."])
    subprocess.Popen(["powershell", "-Command", f"copaw app --port {port}"])
else:
    # Linux/Mac 直接执行
    subprocess.run(["copaw", "init", ...])
    subprocess.Popen(["copaw", "app", ...])
```

### 3.6 端口分配规则

- **Manager 端口**：默认 8000，可通过命令行 `--port` 指定
- **APP 端口**：
  1. 创建 APP 时，从元数据中记录的最大端口 +1 开始尝试
  2. 检查该端口是否在元数据中被其他 APP 占用
  3. 检查该端口是否被其他应用占用（通过 socket 连接检测）
  4. 如果都被占用，继续尝试下一个端口
  5. 端口一旦确定，记录到元数据，后续启动都使用这个端口

```python
import socket

def is_port_in_use(port: int) -> bool:
    """检测端口是否被其他应用占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def find_available_port(self, start_port: int = 8088) -> int:
    """找可用端口"""
    # 获取元数据中已分配的端口
    meta = self.load()
    allocated_ports = set(ws.port for ws in meta.workspaces)
    
    # 取最大端口 +1 作为起点，如果没有则用默认值
    if allocated_ports:
        start_port = max(allocated_ports) + 1
    
    port = start_port
    while True:
        # 先排除已分配给其他 APP 的端口
        if port not in allocated_ports:
            # 再检查是否被其他应用占用
            if not is_port_in_use(port):
                return port
        port += 1
```

### 3.5 核心服务逻辑

```python
class WorkspaceManager:
    """工作区管理器"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.meta_file = base_dir / "workspaces.json"
    
    # ========== 端口分配 ==========
    def find_available_port(self, start_port: int = 8088) -> int:
        """从指定端口开始，找第一个可用端口"""
        port = start_port
        while True:
            if not self._is_port_in_use(port):
                return port
            port += 1
    
    def _is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        # 使用 socket 检测
        pass
    
    # ========== CRUD ==========
    def create_workspace(
        self,
        name: str,
        description: str = "",
        working_dir: str = None,
        auto_start: bool = False
    ) -> Workspace:
        """创建新工作区"""
        # 生成 ID
        workspace_id = str(uuid.uuid4())
        
        # 自动分配端口
        port = self.find_available_port()
        
        # 自动生成工作目录（如果未指定）
        if not working_dir:
            working_dir = str(self.base_dir / "apps" / workspace_id)
        
        # 创建工作目录
        Path(working_dir).mkdir(parents=True, exist_ok=True)
        
        # ========== 关键：初始化工作目录 ==========
        # 设置环境变量，确保 copaw init 初始化到正确位置
        env = os.environ.copy()
        env["COPAW_WORKING_DIR"] = working_dir
        
        # Windows: 使用 PowerShell 启动（避免 cmd 的兼容性问题）
        # 注意：env 需要正确传递到子进程
        if sys.platform == "win32":
            # PowerShell 中设置环境变量并执行命令
            cmd = f"$env:COPAW_WORKING_DIR='{working_dir}'; copaw init --defaults --accept-security"
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                env=env,  # 确保环境变量传递
                capture_output=True,
                text=True,
                timeout=120,  # 超时 2 分钟
            )
        else:
            result = subprocess.run(
                ["copaw", "init", "--defaults", "--accept-security"],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,  # 超时 2 分钟
            )
        
        if result.returncode != 0:
            # 初始化失败，清理已创建的目录
            shutil.rmtree(working_dir, ignore_errors=True)
            raise RuntimeError(f"初始化工作区失败: {result.stderr}")
        
        workspace = Workspace(
            id=workspace_id,
            name=name,
            description=description,
            auto_start=auto_start,
            working_dir=working_dir,
            port=port,
        )
        
        # 保存
        meta = self.load()
        meta.workspaces.append(workspace)
        self.save(meta)
        
        return workspace
    
    # ========== 生命周期 ==========
    def start_workspace(self, workspace_id: str) -> dict:
        """启动工作区"""
        ws = self.get_workspace(workspace_id)
        
        # ========== 启动前检查 ==========
        # 1. 检查工作目录是否存在
        if not Path(ws.meta.working_dir).exists():
            raise FileNotFoundError(f"工作目录不存在: {ws.meta.working_dir}")
        
        # 2. 检查配置文件是否存在（确保已初始化）
        config_file = Path(ws.meta.working_dir) / "config.json"
        if not config_file.exists():
            raise RuntimeError(
                f"工作区未初始化，请先运行初始化: {ws.meta.working_dir}\n"
                "或删除该工作区后重新创建"
            )
        
        # 3. 如果之前记录的 PID 进程还在，先清理
        if ws.runtime.pid:
            try:
                proc = psutil.Process(ws.runtime.pid)
                proc.terminate()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
            except psutil.TimeoutExpired:
                proc.kill()
        
        # ========== 启动进程 ==========
        env = os.environ.copy()
        env["COPAW_WORKING_DIR"] = ws.meta.working_dir
        
        # Windows: 使用 PowerShell 启动（避免 cmd 的兼容性问题）
        # 注意：需要正确传递环境变量
        if sys.platform == "win32":
            cmd = f"$env:COPAW_WORKING_DIR='{ws.meta.working_dir}'; copaw app --port {ws.meta.port} --host 127.0.0.1"
            proc = subprocess.Popen(
                ["powershell", "-Command", cmd],
                env=env,  # 确保环境变量传递
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                shell=False,
            )
        else:
            proc = subprocess.Popen(
                ["copaw", "app", "--port", str(ws.meta.port), "--host", "127.0.0.1"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        
        # 更新运行时状态（内存中）
        self._runtime_cache[workspace_id] = WorkspaceRuntime(
            status=WorkspaceStatus.RUNNING,
            pid=proc.pid,
        )
        
        # 更新元数据（持久化）
        ws.meta.last_started = datetime.now()
        self._save_workspace_meta(ws.meta)
        
        return {"success": True, "url": f"http://127.0.0.1:{ws.meta.port}"}
    
    def stop_workspace(self, workspace_id: str):
        """停止工作区"""
        ws = self.get_workspace(workspace_id)
        
        if ws.runtime.pid:
            try:
                proc = psutil.Process(ws.runtime.pid)
                proc.terminate()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
            except psutil.TimeoutExpired:
                proc.kill()
        
        # 重置运行时状态（内存中）
        self._runtime_cache[workspace_id] = WorkspaceRuntime(
            status=WorkspaceStatus.STOPPED,
            pid=None,
            is_healthy=None,
        )
    
    def stop_all_workspaces(self):
        """停止所有运行中的工作区"""
        for ws in self.list_workspaces():
            if ws.status == WorkspaceStatus.RUNNING:
                self.stop_workspace(ws.id)
    
    # ========== 心跳检测 ==========
    def check_workspace_health(self, workspace_id: str) -> bool:
        """检测工作区健康状态"""
        ws = self.get_workspace(workspace_id)
        
        if ws.runtime.status != WorkspaceStatus.RUNNING:
            self._runtime_cache[workspace_id].is_healthy = None
            return False
        
        # 调用 CoPaw 现有接口检测（优先 /api/version）
        try:
            import requests
            response = requests.get(
                f"http://127.0.0.1:{ws.meta.port}/api/version",
                timeout=3
            )
            is_healthy = response.status_code == 200
        except:
            is_healthy = False
        
        # 更新运行时状态（内存中）
        self._runtime_cache[workspace_id].is_healthy = is_healthy
        return is_healthy
    
    def check_all_workspaces_health(self):
        """检测所有工作区健康状态"""
        for ws in self.list_workspaces():
            if ws.runtime.status == WorkspaceStatus.RUNNING:
                self.check_workspace_health(ws.id)
    
    # ========== 持久化 ==========
    def load(self) -> WorkspacesMeta:
        """从文件加载元数据"""
        pass
    
    def save(self, meta: WorkspacesMeta):
        """保存元数据到文件"""
        pass
```

### 3.6 心跳检测机制

- **检测间隔**：每 30 秒检测一次
- **检测方式**：调用 CoPaw 的 `/api/version` 接口（现有接口，返回 200 即正常，无需认证）
- **状态存储**：运行时状态存储在内存中，不持久化
- **状态更新**：
  - 健康：`is_healthy = True`（绿色）
  - 异常：`is_healthy = False`（红色）
  - 未运行：`is_healthy = None`（灰色）
- **进程存活检查**：同时检查 PID 对应进程是否还存在
- **注意**：Manager 重启后，所有 APP 的运行时状态会重置为默认（stopped）

### 3.7 API 设计

#### 列表

```
GET /api/workspaces

Response:
{
    "workspaces": [
        {
            // === 持久化字段 ===
            "id": "...",
            "name": "工作区A",
            "description": "描述",
            "auto_start": true,
            "port": 8088,
            "working_dir": "D:/path",
            "created_at": "...",
            "last_started": "...",
            // === 运行时字段（内存中，重启后重置）===
            "status": "running",
            "pid": 12345,
            "is_healthy": true
        }
    ]
}
```

#### 创建

```
POST /api/workspaces
Body: { 
    "name": "新工作区",
    "description": "描述内容",
    "working_dir": "D:/path",      // 可选，留空自动创建
    "auto_start": false            // 可选，是否自动启动
}

Response: { "workspace": {...} }
```

#### 启动（轮询检测）

```
POST /api/workspaces/{id}/start
Response: { "success": true, "url": "http://127.0.0.1:8088" }

# 前端轮询: 每 1 秒检测 /api/workspaces/{id}/health 直到成功
```

#### 停止

```
POST /api/workspaces/{id}/stop
Response: { "success": true }
```

#### 删除（确认）

```
DELETE /api/workspaces/{id}?delete_data=true
Response: { "success": true }
```

#### 健康状态

```
GET /api/workspaces/{id}/health
Response: { "is_healthy": true }

GET /api/workspaces/health  # 批量检测
Response: { "workspaces": [...] }
```

---

## 🎨 四、界面设计

### 4.1 整体风格

参考现有 CoPaw Console 的设计风格：
- 简洁的卡片式布局
- 统一的配色方案（蓝/灰/白）
- 响应式设计
- 完全独立，不依赖现有前端代码

### 4.2 界面原型

```
┌─────────────────────────────────────────────────────────────────────┐
│  🐾 CoPaw APP Manager                              [端口: 8000]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ➕ 新建 APP                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  🚀 自动启动  📦 工作区A              ● 运行中  [健康]     │    │
│  │     描述: 主要用于日常办公                                   │    │
│  │     端口: 8088  │  目录: D:/copaw-projects/work-a          │    │
│  │     [▶️ 停止]  [✏️ 编辑]  [🗑️ 删除]                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  📦 个人项目            ○ 已停止                               │    │
│  │     描述: 个人学习测试用                                      │    │
│  │     端口: 8089  │  目录: ~/.copaw_app_manager/apps/xxx      │    │
│  │     [▶️ 启动]  [✏️ 编辑]  [🗑️ 删除]                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  📦 测试环境            ● 运行中  [异常]                       │    │
│  │     端口: 8090  │  目录: D:/copaw-projects/test             │    │
│  │     [▶️ 停止]  [✏️ 编辑]  [🗑️ 删除]                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 新建 APP 对话框

```
┌────────────────────────────────────────┐
│         创建新 APP                      │
├────────────────────────────────────────┤
│  名称:                                 │
│  [________________________] *          │
│                                        │
│  描述:                                 │
│  [________________________]           │
│                                        │
│  工作目录:                             │
│  [________________________] [浏览]     │
│  (留空则自动创建在 apps/ 目录)        │
│                                        │
│  端口: (自动分配 8088)                 │
│                                        │
│  ☑ 启动时自动运行                     │
│                                        │
│     [取消]  [创建]                     │
└────────────────────────────────────────┘
```

### 4.4 删除确认对话框

```
┌────────────────────────────────────────┐
│         确认删除                        │
├────────────────────────────────────────┤
│  确定要删除 "工作区A" 吗？             │
│                                        │
│  ⚠️ 这将同时删除工作目录中的所有文件！  │
│  目录: D:/copaw-projects/work-a       │
│                                        │
│     [取消]  [确认删除]                 │
└────────────────────────────────────────┘
```

### 4.5 状态指示

| 状态 | 图标 | 说明 |
|------|------|------|
| 运行中 + 健康 | 🟢 绿色圆点 + "健康" | 进程正常，接口响应正常 |
| 运行中 + 异常 | 🔴 红色圆点 + "异常" | 进程存在但接口无响应 |
| 运行中 + 检测中 | 🟡 黄色圆点 + "检测中" | 正在检测健康状态 |
| 已停止 | ⚪ 灰色圆点 | 进程已停止 |

---

## 🚀 五、启动流程

### 5.1 创建 APP 流程

```
1. 生成 UUID
2. 分配端口 (8088+)
3. 创建工作目录
4. 设置 COPAW_WORKING_DIR
5. 执行 copaw init --defaults --accept-security 初始化工作目录
   - 生成 config.json
   - 生成 HEARTBEAT.md、AGENTS.md 等文件
6. 保存元数据到 workspaces.json
```

**注意**：如果 copaw init 失败，会清理已创建的目录并抛出异常。

### 5.2 Manager 启动时自动启动 APP

启动 Manager 时，遍历所有 `auto_start=true` 的 APP 并尝试启动：

```python
def start_manager(port: int = 8000, stop_apps_on_exit: bool = False):
    """启动 Manager"""
    manager = WorkspaceManager()
    meta = manager.load()
    
    # 遍历所有 auto_start=true 的 APP 并启动
    for ws in meta.workspaces:
        if ws.auto_start:
            try:
                manager.start_workspace(ws.id)
                print(f"自动启动: {ws.name} (端口: {ws.port})")
            except Exception as e:
                print(f"自动启动失败: {ws.name} - {e}")
    
    # 启动 Manager Web 服务
    uvicorn.run("copaw_app_manager.app._app:app", host="127.0.0.1", port=port)
```

**处理异常**：如果某个 APP 启动失败，记录日志并继续启动其他 APP，不影响 Manager 本身启动。

### 5.3 启动 APP 流程

```
1. 检查工作目录是否存在 → 不存在报错
2. 检查 config.json 是否存在（确保已初始化）→ 不存在报错
3. 如果之前的 PID 进程还存在，先清理
4. 设置 COPAW_WORKING_DIR 环境变量
5. 用 subprocess 启动 copaw app --port {port}
6. 记录 PID
7. 更新状态为 RUNNING
8. 返回 URL
```

### 5.3 启动跳转逻辑

1. 用户点击"启动"
2. 后台启动 CoPaw 进程
3. 返回 `{"success": true, "url": "http://127.0.0.1:8088"}`
4. 前端在新标签页打开 URL
5. 同时前端轮询 `/api/workspaces/{id}/health`，直到返回 200
6. 轮询成功或超时（30秒）后结束

### 5.2 Manager 停止流程

```bash
copaw_app_manager start --stop-apps  # 启动时带 --stop-apps
```

当 Manager 进程收到终止信号（SIGTERM / Ctrl+C）：
1. 如果带 `--stop-apps` 参数：遍历所有运行中的 APP，调用 `stop_workspace()`
2. 保存元数据
3. 退出进程

---

## ⚠️ 六、边界情况处理

### 6.1 端口冲突

- 创建时自动跳过已有端口
- 启动失败时返回具体错误信息

### 6.2 进程异常退出

- 心跳检测会发现并更新状态
- 进程退出但 PID 记录还在，下次启动前清理

### 6.3 工作目录不存在

- 启动前检查工作目录是否存在
- 不存在则报错

### 6.4 并发操作

- 加锁防止同时启动/停止同一个 APP

---

## 📝 七、开发计划

### Phase 1：MVP（最小可行产品）

- [ ] 项目骨架搭建
- [ ] 元数据模型和持久化
- [ ] 端口分配逻辑
- [ ] CLI 命令实现
- [ ] 启动/停止核心逻辑
- [ ] 简单 Web 界面（列表 + 启动/停止）

### Phase 2：完善功能

- [ ] 创建 APP 表单
- [ ] 删除功能（确认对话框）
- [ ] 心跳检测机制
- [ ] 启动跳转 + 轮询检测
- [ ] Manager 停止时连带停止 APP

---

## 📝 七、安装与使用

### 7.1 安装方式

#### 方式 A：独立安装（推荐）

`copaw-app-manager` 是一个**独立的包**，可以单独安装和使用：

```bash
# 只安装 APP Manager（不安装 CoPaw）
pip install copaw-app-manager

# 验证安装
copaw-app-manager --version
copaw-app-manager start
```

**适用场景：**
- 只需要管理界面，不需要运行 CoPaw APP
- 已经有 CoPaw 实例在运行
- 想要轻量级安装

**注意：** 如果未安装 CoPaw，创建/启动 APP 时会提示需要先安装 CoPaw。

#### 方式 B：完整安装（含 CoPaw 支持）

如果需要创建和启动 CoPaw APP 实例：

```bash
# 先安装 Manager
pip install copaw-app-manager

# 再安装 CoPaw
pip install copaw
```

或者从源码安装：

```bash
# 从源码安装完整版本
cd My-CoPaw
pip install -e .              # 安装 CoPaw
pip install -e packages/copaw-app-manager  # 安装 Manager
```

#### 方式 C：开发模式

```bash
# 安装 Manager 开发版本
pip install -e packages/copaw-app-manager[dev]

# 直接运行（无需安装）
python -m copaw_app_manager start
```

### 7.2 包结构说明

```
My-CoPaw/
├── packages/copaw-app-manager/   # 独立的包目录
│   ├── pyproject.toml           # 独立的包配置
│   ├── README.md                # 包说明
│   └── INSTALL.md               # 安装指南
└── src/copaw_app_manager/       # 源代码（两个包共用）
```

**关键点：**
- `copaw-app-manager` 是独立的 PyPI 包
- 源代码在 `src/copaw_app_manager/`，与主项目共用
- 通过 `package-dir` 配置指向源码目录

### 7.3 pyproject.toml 配置

#### 主项目 (pyproject.toml)

```toml
[project]
name = "copaw"
# ... CoPaw 配置 ...

[tool.uv]
dev-dependencies = [...]

# 不再包含 copaw-app-manager 作为子包
```

#### APP Manager (packages/copaw-app-manager/pyproject.toml)

```toml
[project]
name = "copaw-app-manager"
version = "0.1.0"
description = "CoPaw APP Manager - 多工作区管理服务"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.40.0",
    "click>=8.0.0",
    "psutil>=5.9.0",
    "jinja2>=3.0.0",
    "requests>=2.28.0",
    "pydantic>=2.0.0",
]

[tool.setuptools]
# 指向共用的源代码目录
package-dir = { "" = "../../src" }

[tool.setuptools.packages.find]
where = ["../../src"]
include = ["copaw_app_manager*"]

[project.scripts]
copaw-app-manager = "copaw_app_manager.cli.main:app"
```

### 7.4 工作目录隔离

| 安装方式 | CoPaw 工作目录 | APP Manager 目录 |
|----------|---------------|------------------|
| 系统 copaw | `~/.copaw` | - |
| 独立安装 copaw | `~/.copaw` (或自定义) | `~/.copaw_app_manager` |
| app-manager | - | `~/.copaw_app_manager` |

**注意：** APP Manager 创建的 APP 工作目录默认在 `{COPAW_APP_MANAGER_DIR}/apps/{app_id}/`，与系统 copaw 完全隔离，不会相互影响。

### 7.5 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `COPAW_APP_MANAGER_DIR` | `~/.copaw_app_manager` | Manager 元数据存放目录 |
| `COPAW_WORKING_DIR` | - | CoPaw 工作目录（由 Manager 自动设置） |

---

## 📌 附录：CoPaw 现有接口（健康检测用）

经过分析，可用于健康检测的现有接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/version` | GET | 获取版本，无需认证，最简单 ✅ 推荐 |
| `/api/config` | GET | 获取配置，需认证但响应快 |
| `/health` | GET | 如果存在的话 |

**推荐使用**：`/api/version` - 最简单且无需认证

---

> 📌 文档版本：v0.2  
> 📅 更新日期：2026-03-02  
> 👤 撰写：颖宝
