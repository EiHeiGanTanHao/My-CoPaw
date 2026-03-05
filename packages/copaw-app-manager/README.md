# CoPaw APP Manager

CoPaw APP Manager 是一个多工作区管理服务，支持同时运行多个 CoPaw APP 实例。

## 功能特性

- 🚀 多工作区管理：同时运行多个 CoPaw APP 实例
- 📋 工作区 CRUD：创建、启动、停止、删除工作区
- 🔍 状态监控：实时查看工作区运行状态和健康检查
- 🎯 自动启动：支持配置开机/启动时自动运行指定 APP
- 🌐 Web 管理界面：可视化管理所有工作区

## 安装

### 基础安装（仅管理器）

```bash
pip install copaw-app-manager
```

### 完整安装（包含 CoPaw 支持）

```bash
pip install copaw-app-manager[copaw]
```

## 使用方法

### 命令行

```bash
# 启动管理服务
copaw-app-manager start

# 列出所有 APP
copaw-app-manager list

# 创建新 APP
copaw-app-manager create --name my-app --description "我的应用"

# 启动指定 APP
copaw-app-manager start-app my-app

# 停止指定 APP
copaw-app-manager stop-app my-app

# 删除 APP
copaw-app-manager delete my-app
```

### Web 界面

启动服务后访问：http://127.0.0.1:8000

## 环境变量

- `COPAW_APP_MANAGER_DIR`: 元数据存放目录（默认：`~/.copaw_app_manager`）

## 依赖说明

- **基础依赖**: FastAPI, uvicorn, click, psutil, jinja2, requests, pydantic
- **可选依赖**: copaw（用于管理 CoPaw APP 实例）

## 独立使用

如果只需要管理服务而不需要运行 CoPaw APP，可以只安装基础版本：

```bash
pip install copaw-app-manager
```

如果需要管理 CoPaw APP 实例，请先安装 CoPaw：

```bash
pip install copaw
# 或
pip install copaw-app-manager[copaw]
```
