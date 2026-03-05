# 需求：copaw-app-manager quit 退出命令

## 📌 需求背景

目前 `copaw-app-manager start` 启动 Manager 后，只能通过 **Ctrl+C** 停止。

**问题**：未来 Manager 可能以后台守护进程（daemon）方式运行，此时没有终端窗口，无法使用 Ctrl+C 停止。

**目标**：提供一种命令行方式优雅停止 Manager。

---

## 📋 需求描述

### 1. 新增命令

```bash
copaw-app-manager quit
copaw-app-manager exit  # quit 的别名
```

### 2. 功能要求

| 功能 | 说明 |
|------|------|
| 停止运行中的 Manager | 向 Manager 进程发送终止信号 |
| 优雅停止 | 先停止所有运行中的 APP，再关闭 Manager |
| 清理锁文件 | 停止成功后删除 lock 文件 |

### 3. 锁文件机制

- **位置**：放在 Manager 的工作目录（base_dir）下
- **文件名**：`manager.lock`
- **内容**：
  ```json
  {
    "pid": 12345,
    "port": 8000,
    "started_at": "2026-01-01T10:00:00"
  }
  ```

### 4. 多实例支持

- **同一个工作目录**：只能运行一个 Manager 实例（通过锁文件限制）
- **不同工作目录**：可以运行多个 Manager 实例（互不影响）
- 工作目录由环境变量 `COPAW_APP_MANAGER_DIR` 或默认 `~/.copaw_app_manager` 决定

---

## 🛠️ 实现方案

### 1. 修改 start 命令

启动时创建锁文件：
```python
# 检查 lock 文件
lock_file = base_dir / "manager.lock"
if lock_file.exists():
    # 检查进程是否还在运行
    old_pid = json.loads(lock_file.read_text())["pid"]
    if is_process_running(old_pid):
        raise Exception("已有 Manager 在运行")
    else:
        # 清理过期锁文件
        lock_file.unlink()

# 写入当前进程信息
lock_file.write_text(json.dumps({
    "pid":    "port": os.getpid(),
 port,
    "started_at": datetime.now().isoformat()
}))
```

### 2. 新增 quit 命令

```python
@app.command("quit")
@app.command("exit", hidden=True)  # 别名
@click.option("--force", is_flag=True, help="强制杀死进程（忽略错误）")
def quit(force: bool):
    """停止正在运行的 Manager"""
    # 1. 读取 lock 文件
    # 2. 检查进程是否存在
    # 3. 优雅停止（SIGTERM）或强制杀死（SIGKILL）
    # 4. 清理 lock 文件
    # 5. 输出结果
```

### 3. 默认行为

- **默认行为**：退出时自动停止所有运行中的 APP
- `--force`：强制杀死 Manager 进程（跳过优雅停止流程）

### 3. 平台兼容性

- **Windows**：使用 `psutil` 杀死进程（SIGTERM 在 Windows 上处理不佳）
- **Linux/macOS**：可使用信号机制

---

## 🤔 待确认问题

| 问题 | 状态 | 说明 |
|------|------|------|
| 是否需要后台启动（--daemon）参数？ | ⏳ 暂不讨论 | 可后续添加 |
| 是否需要支持远程停止（HTTP API）？ | ⏳ 暂不讨论 | 可后续添加 |

---

## 📎 关联文件

- CLI 入口：`src/copaw_app_manager/cli/main.py`
- 服务管理器：`src/copaw_app_manager/service/manager.py`

---

*创建时间：2026-01-13*
*参与讨论：伙伴、颖宝*
