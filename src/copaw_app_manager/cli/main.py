"""CLI 模块 - 命令行入口"""

import sys
import signal
import click

from copaw_app_manager.service.manager import WorkspaceManager
from copaw_app_manager.models.workspace import WorkspaceStatus


@click.group()
@click.version_option(version="0.1.0", prog_name="copaw-app-manager")
def app():
    """CoPaw APP Manager - 多工作区管理服务"""
    pass


@app.command("start")
@click.option("--port", default=8000, help="管理界面端口（默认：8000）")
@click.option("--stop-apps", is_flag=True, help="停止 Manager 时连带停止所有 APP")
@click.option("--auto-start", is_flag=True, default=True, help="启动时自动启动 auto_start=true 的 APP")
def start(port: int, stop_apps: bool, auto_start: bool):
    """启动管理界面"""
    import uvicorn

    manager = WorkspaceManager()

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
        click.echo("已关闭 Manager")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    click.echo(f"启动 CoPaw APP Manager - http://127.0.0.1:{port}")
    click.echo(f"元数据目录：{manager.base_dir}")
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
    """列出所有 APP"""
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
    """创建新 APP"""
    manager = WorkspaceManager()

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
    except Exception as e:
        click.echo(f"创建失败：{e}", err=True)
        sys.exit(1)


@app.command("start-app")
@click.argument("name")
def start_app(name: str):
    """启动指定 APP"""
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
    """停止指定 APP"""
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
    """删除 APP"""
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


if __name__ == "__main__":
    app()
