# CoPaw APP Manager - Bug 问题清单

> 创建日期：2026-03-03

---

## 📋 发现的问题

### 1. 创建应用没有加载框

| 问题描述 | 创建 APP 时没有显示加载/等待提示 |
|----------|-------------------------------|
| 现象 | 点击创建后，用户不知道是否正在处理 |
| 原因 | 前端没有添加 loading 状态 |
| 严重程度 | 🟡 中 |
| 建议 | 添加加载动画或禁用按钮，防止重复提交 |

---

### 2. 启动 APP 后访问显示 hello world（不是 CoPaw 控制台）

| 问题描述 | 启动后访问显示 "Hello World"，不是 CoPaw 控制台 |
|----------|----------------------------------------------|
| 现象 | 访问 `http://127.0.0.1:8109/` 返回 `{"message":"Hello World"}` |
| 现象 | 访问 `http://127.0.0.1:8109/api/config` 返回 `{"detail":"Not Found"}` |
| 原因 | **已确认是前端构建问题** - CoPaw 的前端 Console 没有构建 |
| 真相 | 后端 API 服务其实已成功启动，只是前端页面缺失 |
| 严重程度 | ✅ 不是 bug，是部署问题 |
| 解决方案 | 需要在 CoPaw 项目中构建前端：<br>`cd console && npm ci && npm run build` |
| 备注 | 这是 CoPaw 原项目的问题，不是 APP Manager 的问题 |

---

### 3. 删除工作区未传递 delete_data 参数

| 问题描述 | 删除 APP 时没有真正删除工作目录 |
|----------|------------------------------|
| 现象 | 调用删除 API 时未传递 `delete_data=true` 参数 |
| 原因 | 前端删除时硬编码或遗漏了该参数 |
| 正确行为 | 删除时应该弹窗让用户确认，并询问是否删除工作目录 |
| 严重程度 | 🔴 高 |

**修复建议：**

```javascript
// 删除前弹窗确认
const confirmDelete = async (id, name) => {
    if (confirm(`确定要删除 "${name}" 吗？`)) {
        const deleteData = confirm("是否同时删除工作目录？");
        // 传递 delete_data 参数
        await fetch(`/api/workspaces/${id}?delete_data=${deleteData}`, {
            method: 'DELETE'
        });
    }
}
```

---

## 📝 待办

- [ ] 创建应用时添加加载框/禁用按钮
- [x] ~~启动 APP 后返回 hello world~~ - 已确认是 CoPaw 前端未构建的问题，不是 bug
- [ ] 修复删除工作区时传递 delete_data 参数
- [ ] 删除前弹窗确认
- [ ] 启动 APP 时添加加载状态（按钮禁用或加载动画）
- [x] ~~停止 APP 功能~~ - 已确认功能正常
- [ ] 编辑按钮点击无反应 - 需要检查 JS 事件绑定

---

## 📎 相关文件

- 前端入口：`src/copaw_app_manager/templates/index.html`
- 前端逻辑：`src/copaw_app_manager/static/app.js`
- 后端 API：`src/copaw_app_manager/routers/workspaces.py`
