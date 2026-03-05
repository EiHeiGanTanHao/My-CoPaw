"""FastAPI 应用 - 主入口"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from copaw_app_manager.routers import workspaces

# 创建应用
app = FastAPI(
    title="CoPaw APP Manager",
    description="多工作区管理服务",
    version="0.1.0"
)

# 获取静态文件和模板目录
static_dir = Path(__file__).parent.parent / "static"
templates_dir = Path(__file__).parent.parent / "templates"

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 设置模板
templates = Jinja2Templates(directory=str(templates_dir))

# 注册路由
app.include_router(workspaces.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """管理界面首页"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Manager 健康检查"""
    return {"status": "healthy"}
