/**
 * CoPaw APP Manager - 前端交互
 */

// API 基础路径
const API_BASE = '/api/workspaces';

// 获取并显示版本号
async function loadVersion() {
    try {
        const response = await fetch('/openapi.json');
        const data = await response.json();
        const version = data.info?.version || '';
        if (version) {
            document.getElementById('app-version').textContent = ` | v${version}`;
        }
    } catch (e) {
        console.error('获取版本失败:', e);
    }
}

// 工具函数
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// 复制路径到剪贴板
async function copyPath(element) {
    try {
        const path = element.getAttribute('data-path');
        await navigator.clipboard.writeText(path);
        showToast('路径已复制到剪贴板');
    } catch (error) {
        showToast('复制失败', 'error');
    }
}

function formatPort(port) {
    return port || '-';
}

function formatPath(path) {
    if (!path) return '-';
    // 缩短过长的路径
    if (path.length > 50) {
        return '...' + path.slice(-47);
    }
    return path;
}

// 获取状态样式
function getStatusClass(status) {
    switch (status) {
        case 'running': return 'status-running';
        case 'error': return 'status-error';
        default: return 'status-stopped';
    }
}

function getStatusDotClass(status, isHealthy) {
    if (status !== 'running') return 'stopped';
    if (isHealthy === null) return 'checking';
    return isHealthy ? 'running' : 'error';
}

function getStatusText(status) {
    switch (status) {
        case 'running': return '运行中';
        case 'error': return '异常';
        default: return '已停止';
    }
}

function getHealthBadge(isHealthy, status) {
    if (status !== 'running') {
        return '<span class="health-badge health-unknown">-</span>';
    }
    if (isHealthy === null) {
        return '<span class="health-badge health-unknown">检测中</span>';
    }
    if (isHealthy) {
        return '<span class="health-badge health-healthy">健康</span>';
    }
    return '<span class="health-badge health-unhealthy">异常</span>';
}

// 加载工作区列表
async function loadWorkspaces() {
    try {
        const response = await fetch(API_BASE);
        const data = await response.json();
        renderWorkspaces(data.workspaces);
    } catch (error) {
        console.error('加载失败:', error);
        showToast('加载工作区列表失败', 'error');
    }
}

// 渲染工作区列表
function renderWorkspaces(workspaces) {
    const container = document.getElementById('workspace-list');

    if (workspaces.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <div class="empty-state-text">暂无 APP</div>
                <button class="btn btn-primary" onclick="showCreateModal()">
                    ➕ 创建第一个 APP
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="workspace-grid">
            ${workspaces.map(ws => `
                <div class="card" data-id="${ws.meta.id}">
                    <div class="card-header">
                        <div class="card-title">
                            <span>${escapeHtml(ws.meta.name)}</span>
                            <span class="status ${getStatusClass(ws.runtime.status)}">
                                <span class="status-dot ${getStatusDotClass(ws.runtime.status, ws.runtime.is_healthy)}"></span>
                                ${getStatusText(ws.runtime.status)}
                            </span>
                        </div>
                    </div>
                    <div class="card-body">
                        ${ws.meta.description ? `<p>${escapeHtml(ws.meta.description)}</p>` : ''}
                        <div class="info-row">
                            <span>📌 端口：${formatPort(ws.meta.port)}</span>
                            <span>${getHealthBadge(ws.runtime.is_healthy, ws.runtime.status)}</span>
                            ${ws.meta.auto_start ? '<span class="auto-start-badge">🚀 自启动</span>' : ''}
                        </div>
                        <div class="info-row">
                            <span class="path-cell" data-path="${ws.meta.working_dir}" onclick="copyPath(this)" title="点击复制路径">📁 ${formatPath(ws.meta.working_dir)}</span>
                        </div>
                    </div>
                    <div class="card-footer">
                        ${ws.runtime.status === 'running'
                            ? `<button class="btn btn-primary btn-sm" onclick="window.open('http://127.0.0.1:${ws.meta.port}', '_blank')">🔗 访问</button>
                               <button class="btn btn-danger btn-sm" onclick="stopWorkspace('${ws.meta.id}')">⏹️ 停止</button>`
                            : `<button class="btn btn-success btn-sm" onclick="startWorkspace('${ws.meta.id}')">▶️ 启动</button>
                               <button class="btn btn-secondary btn-sm" onclick="editWorkspace('${ws.meta.id}')">✏️ 编辑</button>
                               <button class="btn btn-danger btn-sm" onclick="deleteWorkspace('${ws.meta.id}', '${escapeHtml(ws.meta.name)}')">🗑️ 删除</button>`
                        }
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// 创建 APP
async function createWorkspace(data) {
    const submitBtn = document.querySelector('#create-form button[type="submit"]');
    const originalText = submitBtn.textContent;
    
    try {
        // 设置 loading 状态
        submitBtn.disabled = true;
        submitBtn.textContent = '创建中...';
        
        const response = await fetch(API_BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '创建失败');
        }

        showToast('创建成功');
        hideCreateModal();
        loadWorkspaces();
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    } finally {
        // 恢复按钮状态
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// 启动 APP
async function startWorkspace(id) {
    try {
        const response = await fetch(`${API_BASE}/${id}/start`, { method: 'POST' });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '启动失败');
        }

        const data = await response.json();

        // 轮询健康状态，健康后再打开窗口（避免浏览器拦截弹出窗口）
        pollHealth(id, data.url);

        showToast('启动成功，等待APP就绪...');
        loadWorkspaces();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// 轮询健康状态
async function pollHealth(id, url, maxAttempts = 30) {
    let attempts = 0;

    const check = async () => {
        attempts++;
        if (attempts > maxAttempts) {
            showToast('启动超时，请手动检查', 'error');
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/${id}/health`);
            const data = await response.json();

            if (data.is_healthy === true) {
                // 健康检测成功，打开新窗口
                window.open(url, '_blank');
                showToast('APP 已就绪');
                return;
            }

            setTimeout(check, 1000);
        } catch (error) {
            setTimeout(check, 1000);
        }
    };

    check();
}

// 停止 APP
async function stopWorkspace(id) {
    try {
        const response = await fetch(`${API_BASE}/${id}/stop`, { method: 'POST' });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '停止失败');
        }

        showToast('已停止');
        loadWorkspaces();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// 删除 APP
async function deleteWorkspace(id, name) {
    // 第一步：确认删除应用
    if (!confirm(`确定要删除 "${name}" 吗？\n\n⚠️ 此操作不可恢复！`)) {
        return;
    }

    // 第二步：确认是否删除工作目录
    const deleteData = confirm(
        `是否同时删除工作目录中的所有文件？\n\n✅ 点击"确定"删除工作目录\n❌ 点击"取消"仅删除应用配置`
    );

    try {
        const response = await fetch(`${API_BASE}/${id}?delete_data=${deleteData}`, { 
            method: 'DELETE' 
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '删除失败');
        }

        showToast('已删除');
        loadWorkspaces();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// 编辑 APP
async function editWorkspace(id) {
    // 获取当前工作区信息
    try {
        const response = await fetch(`${API_BASE}/${id}`);
        const data = await response.json();
        const ws = data.workspace;

        // 显示编辑对话框
        showEditModal(ws);
    } catch (error) {
        showToast('获取工作区信息失败', 'error');
    }
}

// 显示编辑对话框
function showEditModal(workspace) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'edit-modal';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h2 class="modal-title">编辑 APP</h2>
            </div>
            <form id="edit-form">
                <div class="form-group">
                    <label class="form-label" for="edit-name">名称 *</label>
                    <input
                        type="text"
                        id="edit-name"
                        class="form-input"
                        value="${escapeHtml(workspace.meta.name)}"
                        required
                    >
                </div>
                <div class="form-group">
                    <label class="form-label" for="edit-description">描述</label>
                    <input
                        type="text"
                        id="edit-description"
                        class="form-input"
                        value="${escapeHtml(workspace.meta.description || '')}"
                    >
                </div>
                <div class="form-checkbox">
                    <input type="checkbox" id="edit-auto-start" ${workspace.meta.auto_start ? 'checked' : ''}>
                    <label for="edit-auto-start">启动 Manager 时自动运行</label>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="hideEditModal()">取消</button>
                    <button type="submit" class="btn btn-primary">保存</button>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // 显示弹窗
    modal.style.display = 'flex';

    // 表单提交
    document.getElementById('edit-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const data = {
            name: document.getElementById('edit-name').value.trim(),
            description: document.getElementById('edit-description').value.trim(),
            auto_start: document.getElementById('edit-auto-start').checked
        };

        if (!data.name) {
            showToast('名称不能为空', 'error');
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/${workspace.meta.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '更新失败');
            }

            showToast('更新成功');
            hideEditModal();
            loadWorkspaces();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });

    // 点击遮罩关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            hideEditModal();
        }
    });
}

function hideEditModal() {
    const modal = document.getElementById('edit-modal');
    if (modal) {
        modal.remove();
    }
}

// 模态框控制
function showCreateModal() {
    document.getElementById('create-modal').style.display = 'flex';
}

function hideCreateModal() {
    document.getElementById('create-modal').style.display = 'none';
    document.getElementById('create-form').reset();
}

// 表单提交
document.getElementById('create-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const data = {
        name: document.getElementById('ws-name').value.trim(),
        description: document.getElementById('ws-description').value.trim(),
        working_dir: document.getElementById('ws-dir').value.trim() || null,
        auto_start: document.getElementById('ws-auto-start').checked
    };

    if (!data.name) {
        showToast('名称不能为空', 'error');
        return;
    }

    await createWorkspace(data);
});

// 关闭模态框
document.querySelector('.modal-overlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        hideCreateModal();
    }
});

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 页面加载
document.addEventListener('DOMContentLoaded', () => {
    loadWorkspaces();
    loadVersion();
});

// 定时刷新（每 10 秒）
setInterval(loadWorkspaces, 10000);
