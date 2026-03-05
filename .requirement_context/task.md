# 任务：修复 copaw-app-manager 两个 bug

## 项目路径
`F:\Workspace\AI\projects\My-CoPaw`

## 问题 1：编辑按钮点击没反应

**问题描述**：点击编辑按钮没有任何反应

**问题位置**：`src/copaw_app_manager/static/app.js`

**原因分析**：
- `editWorkspace(id)` 函数调用 `fetch(API_BASE/${id})` 获取工作区信息
- API 返回格式是 `{ workspace: { meta: {...}, runtime: {...} } }`
- 但 `showEditModal(workspace)` 函数中使用了 `workspace.id`，应该是 `workspace.meta.id`
- 表单提交时 `fetch(API_BASE}/${workspace.id}` 也是错误的，应该是 `${workspace.meta.id}`

**修复要求**：
1. `showEditModal` 函数中，将 `workspace.id` 改为 `workspace.meta.id`
2. 同样在表单提交的 fetch URL 中也要修正

---

## 问题 2：点击停止按钮页面显示已停止但实际进程没停止

**问题描述**：点击停止按钮，页面状态变成"已停止"，但实际进程仍在运行

**问题位置**：`src/copaw_app_manager/service/manager.py` 的 `stop_workspace` 方法

**原因分析**：
1. 停止时只根据 `workspace.runtime.pid` 来杀进程，但如果该 PID 进程已经不存在了（手动被杀掉或者之前就没有正确记录），就会漏掉
2. 进程可能监听的端口和记录的端口不一致
3. 没有根据实际端口来查找并杀死进程

**修复要求**：
1. 在停止时，除了根据 PID 杀进程，还要根据端口号查找并杀死进程
2. 使用 `netstat` 或类似方式找到占用指定端口的进程并杀掉
3. 确保无论进程以什么方式启动的，都能被正确停止

---

## 约束
- 只修改上述两个问题相关的代码
- 不要改动其他无关代码
- 修复后确保功能正常
