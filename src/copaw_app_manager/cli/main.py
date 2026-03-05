"""CLI 模块 - 命令行入口"""

import sys
import signal
import click
import psutil

from copaw_app_manager.service.manager import WorkspaceManager, check_copaw_installed
from copaw_app_manager.models.workspace import WorkspaceStatus



@click.group()
@click.version_option(version="0.1.0", prog_name="copaw-app-manager")
def app():
    """
    CoPaw APP Manager - 多工作区管理服务
    
    支持同时运行多个 CoPaw APP 实例，提供 Web 管理界面和命令行工具。
    
    安装说明:
      - 仅管理服务：pip install copaw-app-manager
      - 完整功能（含 CoPaw）：pip install copaw-app-manager copaw
    
    快速开始:
      copaw-app-manager start          # 启动 Web 管理界面
      copaw-app-manager create --name my-app  # 创建新 APP
      copaw-app-manager list           # 列出所有 APP
    """
    pass


@app.command("start")
@click.option("--port", default=8000, help="管理界面端口（默认：8000）")
@click.option("--stop-apps", is_flag=True, help="停止 Manager 时连带停止所有 APP")
@click.option("--auto-start", is_flag=True, default=True, help="启动时自动启动 auto_start=true 的 APP")
def start(port: int, stop_apps: bool, auto_start: bool):
    """
    启动管理界面（Web 服务）

    启动后可访问：http://127.0.0.1:{port}

    注意:
      - 如果已安装 CoPaw，会自动启动 auto_start=true 的 APP
      - 未安装 CoPaw 时，只能管理，无法创建/启动 APP

    示例:
      copaw-app-manager start              # 默认端口 8000
      copaw-app-manager start --port 9000  # 指定端口
    """
    import uvicorn

    manager = WorkspaceManager()

    # 获取锁（检查是否已有 Manager 在运行）
    try:
        manager._acquire_lock(port)
    except RuntimeError as e:
        click.echo(f"启动失败：{e}", err=True)
        sys.exit(1)

    # 自动启动 auto_start=true 的 APP
    if auto_start:
        meta = manager.load()
        for ws_meta in meta.workspaces:
            if ws_meta.auto_start:
                try:
                    manager.start_workspace(ws_meta.id)
                    click.echo(f"[OK] 自动启动：{ws_meta.name} (端口：{ws_meta.port})")
                except Exception as e:
                    click.echo(f"[FAIL] 自动启动失败：{ws_meta.name} - {e}")

    # 处理 Ctrl+C 信号
    def signal_handler(sig, frame):
        click.echo("\n正在关闭 Manager...")
        if stop_apps:
            click.echo("正在停止所有运行中的 APP...")
            manager.stop_all_workspaces()
        manager._release_lock()
        click.echo("已关闭 Manager")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    click.echo(f"启动 CoPaw APP Manager - http://127.0.0.1:{port}")
    click.echo(f"元数据目录：{manager.base_dir}")
    if not check_copaw_installed():
        click.echo("提示：CoPaw 未安装，无法创建/启动 APP。安装：pip install copaw")
    click.echo("按 Ctrl+C 停止")

    # 启动 FastAPI 应用
    uvicorn.run(
        "copaw_app_manager.app._app:app",
        host="127.0.0.1",
        port=port,
        reload=False
    )


@app.command("list")
def list_workspaces():
    """
    列出所有 APP
    
    显示所有工作区的名称、状态、端口和工作目录。
    
    示例:
      copaw-app-manager list
    """
    manager = WorkspaceManager()
    workspaces = manager.list_workspaces()

    if not workspaces:
        click.echo("暂无 APP")
        return

    click.echo(f"\n{'名称':<20} {'状态':<12} {'端口':<8} {'工作目录'}")
    click.echo("-" * 80)

    for ws in workspaces:
        # Windows 兼容性：使用简单文本代替 emoji
        if ws.status == WorkspaceStatus.RUNNING:
            status = "运行中" if ws.is_healthy else "运行中 (异常)"
        else:
            status = "已停止"

        try:
            click.echo(f"{ws.name:<20} {status:<12} {ws.port:<8} {ws.working_dir}")
        except UnicodeEncodeError:
            # 处理编码问题
            click.echo(f"{ws.name:<20} {status:<12} {ws.port:<8} (路径过长)")

    click.echo()


@app.command("create")
@click.option("--name", required=True, help="APP 名称")
@click.option("--description", default="", help="描述")
@click.option("--working-dir", default=None, help="工作目录（留空则自动创建）")
@click.option("--auto-start", "auto_start_flag", is_flag=True, help="启动时自动运行")
def create(name: str, description: str, working_dir: str, auto_start_flag: bool):
    """
    创建新 APP
    
    注意：创建 APP 后会生成工作目录。如需启动 APP，请先安装 CoPaw:
      pip install copaw
    
    示例:
      copaw-app-manager create --name my-app --description "我的助手"
      copaw-app-manager create --name prod --auto-start  # 自动启动
    """
    manager = WorkspaceManager()

    # 检查是否安装了 CoPaw
    if not check_copaw_installed():
        click.echo("⚠️  警告：CoPaw 未安装")
        click.echo("   创建工作区后需要安装 CoPaw 才能启动 APP")
        click.echo("   安装命令：pip install copaw")
        click.echo()

    try:
        ws = manager.create_workspace(
            name=name,
            description=description,
            working_dir=working_dir if working_dir else None,
            auto_start=auto_start_flag
        )
        click.echo(f"已创建成功：{ws.name}")
        click.echo(f"   ID: {ws.id}")
        click.echo(f"   端口：{ws.port}")
        click.echo(f"   工作目录：{ws.working_dir}")
        if not check_copaw_installed():
            click.echo("   提示：请安装 CoPaw 后启动 APP")
    except Exception as e:
        click.echo(f"创建失败：{e}", err=True)
        sys.exit(1)


@app.command("start-app")
@click.argument("name")
def start_app(name: str):
    """
    启动指定 APP
    
    注意：需要先安装 CoPaw 才能启动 APP:
      pip install copaw
    
    示例:
      copaw-app-manager start-app my-app
      copaw-app-manager start-app assistant-1
    """
    manager = WorkspaceManager()

    # 查找 APP
    workspace = None
    for ws in manager.list_workspaces():
        if ws.name == name or ws.id == name:
            workspace = ws
            break

    if not workspace:
        click.echo(f"找不到 APP: {name}", err=True)
        sys.exit(1)

    try:
        result = manager.start_workspace(workspace.id)
        click.echo(f"已启动：{workspace.name}")
        click.echo(f"   URL: {result['url']}")
    except Exception as e:
        click.echo(f"启动失败：{e}", err=True)
        sys.exit(1)


@app.command("stop-app")
@click.argument("name")
def stop_app(name: str):
    """
    停止指定 APP
    
    示例:
      copaw-app-manager stop-app my-app
      copaw-app-manager stop-app assistant-1
    """
    manager = WorkspaceManager()

    # 查找 APP
    workspace = None
    for ws in manager.list_workspaces():
        if ws.name == name or ws.id == name:
            workspace = ws
            break

    if not workspace:
        click.echo(f"找不到 APP: {name}", err=True)
        sys.exit(1)

    try:
        manager.stop_workspace(workspace.id)
        click.echo(f"已停止：{workspace.name}")
    except Exception as e:
        click.echo(f"停止失败：{e}", err=True)
        sys.exit(1)


@app.command("delete")
@click.argument("name")
@click.option("--force", is_flag=True, help="强制删除工作目录")
@click.option("--yes", is_flag=True, help="跳过确认")
def delete(name: str, force: bool, yes: bool):
    """
    删除 APP
    
    注意:
      - 默认只删除元数据，保留工作目录
      - 使用 --force 同时删除工作目录
    
    示例:
      copaw-app-manager delete my-app
      copaw-app-manager delete my-app --force  # 删除工作目录
      copaw-app-manager delete my-app --yes    # 跳过确认
    """
    manager = WorkspaceManager()

    # 查找 APP
    workspace = None
    for ws in manager.list_workspaces():
        if ws.name == name or ws.id == name:
            workspace = ws
            break

    if not workspace:
        click.echo(f"找不到 APP: {name}", err=True)
        sys.exit(1)

    # 确认删除
    if not yes:
        if force:
            click.echo(f"将删除 APP 及其工作目录：{workspace.working_dir}")
        else:
            click.echo(f"将删除 APP（保留工作目录）：{workspace.name}")
        confirm = click.confirm("确认删除？")
        if not confirm:
            click.echo("已取消")
            return

    try:
        success = manager.delete_workspace(workspace.id, delete_data=force)
        if success:
            click.echo(f"已删除：{workspace.name}")
        else:
            click.echo("删除失败", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"删除失败：{e}", err=True)
        sys.exit(1)


@app.command("quit")
@click.option("--force", is_flag=True, help="强制杀死 Manager 进程（跳过优雅停止流程）")
def quit_cmd(force: bool):
    """
    停止运行中的 Manager

    默认先停止所有运行中的 APP，然后关闭 Manager。
    使用 --force 强制杀死 Manager 进程。

    示例:
      copaw-app-manager quit           # 优雅停止
      copaw-app-manager quit --force   # 强制杀死
    """
    manager = WorkspaceManager()

    # 读取锁文件
    lock_data = manager._read_lock()
    if not lock_data:
        click.echo("没有 Manager 在运行")
        return

    pid = lock_data.get("pid")
    port = lock_data.get("port")

    if not pid:
        click.echo("锁文件损坏，无法获取 PID")
        # 清理损坏的锁文件
        manager._release_lock()
        return

    # 检查进程是否存在
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        click.echo(f"Manager 进程不存在（PID: {pid}），清理锁文件")
        manager._release_lock()
        return

    if force:
        # 强制杀死进程
        try:
            proc.kill()
            proc.wait(timeout=5)
            click.echo(f"已强制杀死 Manager 进程（PID: {pid}, 端口：{port}）")
        except psutil.TimeoutExpired:
            click.echo(f"警告：进程（PID: {pid}）未在超时时间内退出", err=True)
        except Exception as e:
            click.echo(f"杀死进程失败：{e}", err=True)
            sys.exit(1)
    else:
        # 优雅停止：先停止所有 APP
        click.echo("正在停止所有运行中的 APP...")
        try:
            manager.stop_all_workspaces()
        except Exception as e:
            click.echo(f"停止 APP 时出错：{e}", err=True)

        # 终止 Manager 进程
        try:
            proc.terminate()
            proc.wait(timeout=5)
            click.echo(f"已停止 Manager 进程（PID: {pid}, 端口：{port}）")
        except psutil.TimeoutExpired:
            # 优雅终止超时，强制杀死
            click.echo("优雅停止超时，强制杀死进程...")
            try:
                proc.kill()
                proc.wait(timeout=5)
                click.echo(f"已强制杀死 Manager 进程（PID: {pid}, 端口：{port}）")
            except Exception as e:
                click.echo(f"杀死进程失败：{e}", err=True)
                sys.exit(1)
        except Exception as e:
            click.echo(f"停止进程失败：{e}", err=True)
            sys.exit(1)

    # 清理锁文件
    manager._release_lock()


@app.command("exit", hidden=True)
@click.option("--force", is_flag=True, help="强制杀死 Manager 进程（跳过优雅停止流程）")
def exit_cmd(force: bool):
    """
    quit 命令的别名

    停止运行中的 Manager。
    """
    # 重用 quit_cmd 的逻辑
    import sys as _sys
    # 调用 quit_cmd 函数并传递参数
    try:
        # 使用 click 的上下文来调用
        ctx = click.get_current_context(silent=True)
        if ctx:
            # 在 click 上下文中，转发调用
            quit_cmd.callback(force=force)
        else:
            # 不在 click 上下文中，直接调用
            quit_cmd.callback(force=force)
    except SystemExit:
        # 忽略 SystemExit，让 click 处理
        pass


if __name__ == "__main__":
    app()
