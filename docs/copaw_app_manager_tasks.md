# CoPaw APP Manager - 开发任务清单

> 文档版本：v0.2
> 创建日期：2026-03-02
> 更新日期：2026-03-03
> 依据：docs/copaw_app_manager_design.md

---

## 📦 一、项目初始化

### 1.1 项目骨架搭建

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T001 | 创建 `src/copaw_app_manager/` 目录结构 | - | P0 |
| T002 | 创建 `__init__.py`, `__main__.py` 入口文件 | T001 | P0 |
| T003 | 创建 `packages/copaw-app-manager/` 独立包目录 | - | P0 |
| T004 | 配置 `packages/copaw-app-manager/pyproject.toml` | T003 | P0 |

**目录结构：**
```
My-CoPaw/
├── packages/copaw-app-manager/    # 独立包目录
│   ├── pyproject.toml            # 独立的包配置
│   ├── README.md                 # 包说明
│   └── INSTALL.md                # 安装指南
├── src/copaw_app_manager/        # 源代码（两个包共用）
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── app/
│   │   ├── __init__.py
│   │   └── _app.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── workspace.py
│   ├── service/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── workspaces.py
│   │   └── app_ctrl.py
│   ├── static/
│   │   ├── style.css
│   │   └── app.js
│   └── templates/
│       └── index.html
```

### 1.2 安装配置（重要！）

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T005 | 配置 `pyproject.toml` 添加独立包依赖 | T004 | P0 |
| T006 | 配置 `[project.scripts]` 注册 `copaw-app-manager` 命令 | T005 | P0 |
| T007 | 验证 `pip install copaw-app-manager` 可以正常安装 | T006 | P0 |
| T007a | 验证 `copaw-app-manager start` 可以正常启动 | T007 | P0 |
| T007b | 验证安装后不影响系统原有的 `copaw` 命令 | T007 | P0 |

**packages/copaw-app-manager/pyproject.toml 配置示例：**
```toml
[project]
name = "copaw-app-manager"
version = "0.1.0"
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
package-dir = { "" = "../../src" }

[tool.setuptools.packages.find]
where = ["../../src"]
include = ["copaw_app_manager*"]

[project.scripts]
copaw-app-manager = "copaw_app_manager.cli.main:app"
```

**注意：**
- `copaw-app-manager` 是独立的包，不依赖 `copaw` 主包
- `copaw` 是可选依赖，只在需要创建/启动 APP 时才需要
- 确保 `copaw_app_manager` 的代码可以独立运行（不导入 `copaw` 模块）

---

## 🧩 二、核心模块

### 2.1 数据模型 (models/)

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T010 | 定义 `WorkspaceStatus` 枚举 | T001 | P0 |
| T011 | 定义 `Workspace` 数据模型（包含 auto_start 字段） | T010 | P0 |
| T012 | 定义 `WorkspacesMeta` 数据模型 | T011 | P0 |
| T013 | 实现 Pydantic 序列化配置（datetime, uuid） | T012 | P0 |

### 2.2 元数据持久化 (service/)

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T020 | 实现 `WorkspaceManager` 类骨架 | T012 | P0 |
| T020a | 读取/设置环境变量 `COPAW_APP_MANAGER_DIR` | T001 | P0 |
| T020b | 实现 `load()` 方法：从 JSON 文件加载元数据 | T020 | P0 |
| T020c | 实现 `save()` 方法：保存元数据到 JSON 文件 | T020b | P0 |
| T020d | 确保目录不存在时自动创建 | T020 | P0 |

### 2.3 端口管理 (service/)

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T021 | 实现 `is_port_in_use()` 端口检测函数 | - | P0 |
| T022 | 实现 `find_available_port()` 端口分配函数 | T020, T021 | P0 |
| T022a | 从元数据获取已分配端口，避免重复 | T022 | P0 |

---

## ⚙️ 三、核心业务逻辑

### 3.1 APP 生命周期管理 (service/)

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T030 | 实现 `create_workspace()` 创建 APP | T022 | P0 |
| T030a | 自动创建工作目录 | T030 | P0 |
| T030b | 调用 `copaw init` 初始化工作目录（如果已安装） | T030a | P0 |
| T030c | 处理初始化失败（清理目录、抛异常） | T030b | P0 |
| T030d | 支持未安装 CoPaw 时创建空工作区 | T030 | P0 |
| T031 | 实现 `start_workspace()` 启动 APP | T030 | P0 |
| T031a | 启动前检查：工作目录存在、config.json 存在 | T031 | P0 |
| T031b | 检查 CoPaw 是否安装 | T031a | P0 |
| T031c | 清理旧进程（PID 存在的情况） | T031b | P0 |
| T031d | 设置环境变量，通过 subprocess 启动 | T031c | P0 |
| T031e | 记录 PID，更新状态，返回 URL | T031d | P0 |
| T032 | 实现 `stop_workspace()` 停止 APP | T031 | P0 |
| T032a | 通过 PID 终止进程 | T032 | P0 |
| T032b | 处理超时强制 kill | T032a | P0 |
| T032c | 重置状态、清除 PID | T032b | P0 |
| T033 | 实现 `delete_workspace()` 删除 APP | T031 | P1 |
| T033a | 根据参数决定是否删除工作目录 | T033 | P1 |
| T034 | 实现 `list_workspaces()` 列出所有 APP | T020 | P0 |
| T035 | 实现 `get_workspace()` 获取单个 APP | T020 | P0 |
| T036 | 实现 `update_workspace()` 更新 APP 信息 | T035 | P1 |

### 3.2 心跳检测 (service/)

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T040 | 实现 `check_workspace_health()` 单个健康检测 | T031 | P1 |
| T040a | 调用 `/api/config` 接口检测 | T040 | P1 |
| T040b | 更新 `is_healthy` 状态 | T040a | P1 |
| T041 | 实现 `check_all_workspaces_health()` 批量检测 | T040 | P1 |
| T042 | 实现定时心跳任务（每 30 秒） | T041 | P1 |
| T042a | 作为后台任务运行，不阻塞主线程 | T042 | P1 |

---

## 🔌 四、API 接口 (routers/)

### 4.1 CRUD 接口

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T050 | GET `/api/workspaces` - 列出所有 APP | T034 | P0 |
| T051 | GET `/api/workspaces/{id}` - 获取单个 APP | T035 | P0 |
| T052 | POST `/api/workspaces` - 创建 APP | T030 | P0 |
| T053 | PUT `/api/workspaces/{id}` - 更新 APP | T036 | P1 |
| T054 | DELETE `/api/workspaces/{id}` - 删除 APP | T033 | P1 |

### 4.2 控制接口

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T060 | POST `/api/workspaces/{id}/start` - 启动 APP | T031 | P0 |
| T060a | 返回 URL 供前端跳转 | T060 | P0 |
| T061 | POST `/api/workspaces/{id}/stop` - 停止 APP | T032 | P0 |
| T062 | GET `/api/workspaces/{id}/health` - 健康检测 | T040 | P1 |
| T063 | GET `/api/workspaces/health` - 批量健康检测 | T041 | P1 |

---

## 🖥️ 五、Web 界面

### 5.1 前端基础

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T070 | 创建 `templates/index.html` 页面骨架 | - | P0 |
| T071 | 创建 `static/style.css` 样式（参考 CoPaw Console 风格） | T070 | P0 |
| T072 | 创建 `static/app.js` 基础交互 | T070 | P0 |

### 5.2 界面功能

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T073 | 实现 APP 列表渲染（从 API 获取） | T050, T072 | P0 |
| T074 | 实现状态指示器（运行中/健康/异常/停止） | T073 | P0 |
| T075 | 实现"新建 APP"对话框和表单 | T052, T072 | P0 |
| T076 | 实现"启动"按钮 + 跳转逻辑 | T060, T072 | P0 |
| T076a | 启动后轮询健康接口直到成功 | T076 | P0 |
| T076b | 启动失败显示错误提示 | T076a | P0 |
| T077 | 实现"停止"按钮 | T061, T072 | P0 |
| T078 | 实现"编辑"功能 | T053, T072 | P1 |
| T079 | 实现"删除"对话框 + 确认逻辑 | T054, T072 | P1 |
| T079a | 删除前确认是否删除工作目录 | T079 | P1 |
| T080 | 自动刷新列表（每 10 秒） | T073 | P1 |

---

## 🖱️ 六、CLI 命令 (cli/)

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T090 | 实现 `copaw_app_manager start` 命令 | T030, T031, T060 | P0 |
| T090a | 支持 `--port` 参数指定端口 | T090 | P0 |
| T090b | 支持 `--stop-apps` 参数 | T090 | P1 |
| T090c | 启动时自动启动 `auto_start=true` 的 APP | T090 | P1 |
| T091 | 实现 `copaw_app_manager list` 命令 | T034 | P1 |
| T092 | 实现 `copaw_app_manager create` 命令 | T030 | P1 |
| T093 | 实现 `copaw_app_manager start-app` 命令 | T031 | P1 |
| T094 | 实现 `copaw_app_manager stop-app` 命令 | T032 | P1 |
| T095 | 实现 `copaw_app_manager delete` 命令 | T033 | P1 |

---

## 🔒 七、Manager 停止逻辑

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T100 | 处理 SIGTERM / Ctrl+C 信号 | T090 | P1 |
| T101 | 根据 `--stop-apps` 参数决定是否停止所有 APP | T100 | P1 |
| T102 | 停止前保存元数据 | T101 | P1 |

---

## 🧪 八、测试与优化

| 任务 ID | 任务描述 | 依赖 | 优先级 |
|---------|----------|------|--------|
| T110 | 本地手动测试：创建、启动、停止、删除 | T030-T095 | P0 |
| T111 | 测试自动启动功能 | T090c | P1 |
| T112 | 测试心跳检测 | T040-T042 | P1 |
| T113 | 测试 Manager 停止时连带停止 APP | T100-T102 | P1 |
| T114 | 边界情况：端口被占用、进程异常退出 | T022, T031 | P1 |
| T115 | 性能优化：减少不必要的文件读写 | T020 | P2 |

---

## 📌 任务执行顺序建议

```
Phase 1: 核心骨架 (T001-T012, T070-T072)
    │
    ▼
Phase 2: 基础 CRUD + 启动停止 (T020-T032, T050-T061, T073-T077)
    │
    ▼
Phase 3: CLI 命令 (T090-T095)
    │
    ▼
Phase 4: 完善功能 (T033-T036, T040-T042, T078-T082, T100-T102)
    │
    ▼
Phase 5: 测试与优化 (T110-T115)
```

---

## ⚡ 技术依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | >=0.100 | Web 框架 |
| uvicorn | >=0.20 | ASGI 服务器 |
| pydantic | >=2.0 | 数据模型 |
| psutil | >=5.9 | 进程管理 |
| jinja2 | >=3.0 | 模板引擎 |
| aiofiles | >=23.0 | 异步文件操作 |
| python-dotenv | - | 环境变量（可选） |

---

## 📝 注意事项

1. **不要修改原 CoPaw 代码** - 所有改动都在 `src/copaw_app_manager/` 目录下
2. **环境变量隔离** - 启动 APP 时必须设置 `COPAW_WORKING_DIR`
3. **进程清理** - 启动前检查并清理旧进程，避免僵尸进程
4. **错误处理** - 创建 APP 失败时清理已创建的目录
5. **socket 检测端口** - 不要用 `connect_ex` 返回值直接判断，用 `== 0`
6. **独立安装** - `copaw-app-manager` 是独立包，不强制依赖 `copaw`

---

> 如有疑问，请先查阅 docs/copaw_app_manager_design.md 设计文档
