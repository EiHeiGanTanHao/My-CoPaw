# CoPaw APP Manager 安装指南

## 独立安装（推荐）

如果你只需要管理多个 CoPaw APP 实例，而不需要安装完整的 CoPaw 包：

### 从 PyPI 安装（发布后）

```bash
pip install copaw-app-manager
```

### 从源码安装（开发）

```bash
# 克隆仓库
git clone https://github.com/your-org/My-CoPaw.git
cd My-CoPaw

# 安装 copaw-app-manager（不安装 copaw 主包）
pip install -e packages/copaw-app-manager
```

### 安装依赖

基础安装会自动安装以下依赖：
- FastAPI >= 0.100.0
- uvicorn >= 0.40.0
- click >= 8.0.0
- psutil >= 5.9.0
- jinja2 >= 3.0.0
- requests >= 2.28.0
- pydantic >= 2.0.0

## 完整安装（包含 CoPaw 支持）

如果你需要创建和启动 CoPaw APP 实例，需要额外安装 CoPaw：

```bash
# 先安装 copaw-app-manager
pip install copaw-app-manager

# 再安装 copaw
pip install copaw
```

或者从源码安装：

```bash
cd My-CoPaw

# 安装主 copaw 包（会自动包含 copaw-app-manager）
pip install -e .
```

## 验证安装

```bash
# 检查版本
copaw-app-manager --version

# 查看帮助
copaw-app-manager --help

# 启动管理服务
copaw-app-manager start
```

## 使用说明

### 基本命令

```bash
# 启动管理服务（Web 界面）
copaw-app-manager start

# 列出所有 APP
copaw-app-manager list

# 创建新 APP
copaw-app-manager create --name my-app --description "我的应用"

# 启动 APP
copaw-app-manager start-app my-app

# 停止 APP
copaw-app-manager stop-app my-app

# 删除 APP
copaw-app-manager delete my-app
```

### Web 界面

启动服务后访问：http://127.0.0.1:8000

## 独立使用场景

### 场景 1：只管理服务，不运行 CoPaw

如果你已经有 CoPaw 实例在运行，只需要一个管理界面：

```bash
pip install copaw-app-manager
copaw-app-manager start
```

### 场景 2：完整使用（管理 + 运行 CoPaw APP）

如果你想创建和管理多个 CoPaw APP 实例：

```bash
# 安装完整版本
pip install copaw-app-manager
pip install copaw

# 创建新 APP
copaw-app-manager create --name assistant-1

# 启动 APP
copaw-app-manager start-app assistant-1
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `COPAW_APP_MANAGER_DIR` | 元数据存放目录 | `~/.copaw_app_manager` |

## 常见问题

### Q: 安装后提示找不到 `copaw` 命令？

A: 这是正常的。`copaw-app-manager` 可以独立安装，只有在你需要创建或启动 CoPaw APP 时才需要安装 `copaw`。

### Q: 如何卸载？

```bash
pip uninstall copaw-app-manager
```

### Q: 如何升级到最新版本？

```bash
pip install --upgrade copaw-app-manager
```

## 开发

```bash
# 安装开发依赖
pip install -e packages/copaw-app-manager[dev]

# 运行测试
pytest packages/copaw-app-manager/tests/
```

## 许可证

与主项目相同。
