# AI Workspace Service

独立的 AI 工作台后端，默认监听 `127.0.0.1:8766`。它与
`services/knowledge-base` 的旧知识问答服务不共享数据库、文件或接口。

## Local run

```powershell
cd D:\PY\RuoShopAdmin
.\.venv\Scripts\pip.exe install -r services\ai-workspace\requirements.txt
Start-Process .\.venv\Scripts\python.exe -ArgumentList server.py `
  -WorkingDirectory services\ai-workspace -WindowStyle Hidden
```

状态检查：`http://127.0.0.1:8766/api/status`。

运行数据位于 `ai_workspace.db` 和 `files/`，两者都不提交到 Git。PC 和移动端
开发服务器把 `/ai-api/` 转发到本服务；生产环境配置见
`deploy/systemd/ai-workspace.service.template` 和 `deploy/nginx/xiaoxu.conf.template`。

## Main APIs

- `/api/config`, `/api/test`: 模型与 Embedding 配置
- `/api/chats`: 服务端会话
- `/api/models`: 自定义模型与能力绑定
- `/api/knowledge`, `/api/files/*`, `/api/search`: 知识管理和混合检索
- `/api/prompts`, `/api/skills`, `/api/tools`: 工作区能力
- `/api/web-search`: 联网搜索
- `/api/chat/stream`: 流式聊天
