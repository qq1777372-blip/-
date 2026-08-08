# 知策 AI 运营知识库

后台「知识问答」页面背后的服务。**它是独立进程，不是本项目 FastAPI 的一部分**：用
标准库 `ThreadingHTTPServer` 写的，自己监听 `127.0.0.1:8765`，有自己的 systemd 单元。

代码 2026-08-08 才纳入本仓库。在那之前只存在于开发机的
`C:\Users\Administrator\ai-knowledge-web`，没有任何版本控制——期间发生过改动被静默还原、
以及新旧副本只能靠比对 md5 才能分辨的情况，这是纳入仓库的直接原因。

## 运行位置

| 项目 | 值 |
|---|---|
| 服务 | `knowledge-base.service`（模板见 `../../deploy/systemd/`） |
| 端口 | `127.0.0.1:8765`（可用 `ZHICE_PORT` 覆盖） |
| 服务器目录 | `/srv/knowledge-base` |
| 入口 | `server.py` |
| 运行用户 | `fastapiproject` |

## 接入方式

后台通过 iframe 嵌入，两条路径都由 nginx 转发：

- `/knowledge/` → `127.0.0.1:8765/`，页面本体
- `/knowledge-api/<name>` → `127.0.0.1:8765/api/<name>`，接口

访问控制**完全依赖 nginx 的 `auth_request`**（子请求打本项目的 `/auth/me`）。本服务自己
不校验登录，所以少了那段 nginx 配置就等于把整个知识库公开。这三段 location
（`/__knowledge_auth`、`/knowledge/`、`/knowledge-api/`）在
`../../deploy/nginx/xiaoxu.conf.template` 里，**曾经在生产机上整段丢失**，导致知识问答
整页 404，请勿再删。

PC 端入口是 `frontend/src/views/KnowledgeView.vue`（路由 `/ui/knowledge`），
App 端是 `app-frontend/src/views/KnowledgePage.vue`。

## 本机开发

```bat
启动知识库.bat
```

或直接 `python server.py`，然后开 `http://127.0.0.1:8765`。

首次运行要在页面右上角「AI 设置」里填接口地址、模型名和 API Key，它们写入本机
`ai_config.json`（已 gitignore）。未配置时问答退化为本地检索。

两个前端的 dev server 已把 `/knowledge` 和 `/knowledge-api` 代理到 8765（见各自的
`vite.config.ts`），所以从 `http://127.0.0.1:5173/ui/knowledge` 打开就能联调，
**但要先把本服务跑起来**，否则 iframe 是空的。

## 不在 git 里的运行时数据

`.gitignore` 排除了四样，它们要靠服务器备份还原，不能靠拉代码：

- `ai_config.json` —— 含明文 API Key
- `knowledge.db` —— 文档、图文结构、完整性指标、导入任务，27MB 起
- `alidocs_images/` —— 正文配图，5665 个文件；正文按相对路径引用，必须和
  `knowledge.db` 一起还原，否则页面能开但配图全 404
- `alidocs_import.json` —— 14MB，旧版迁移来源，仅作兼容备份

## 部署

CI（`.github/workflows/release.yml`）目前**只部署 `/srv/fastapiproject`**，不会碰
`/srv/knowledge-base`。所以改了本目录的代码，要手工同步到服务器再重启：

```bash
# 只传代码，不要覆盖服务器上的 ai_config.json
scp server.py storage.py app.js index.html styles.css ubuntu@<host>:/tmp/kb/
sudo cp /tmp/kb/* /srv/knowledge-base/
sudo chown fastapiproject:fastapiproject /srv/knowledge-base/*
sudo systemctl restart knowledge-base
```

改了 `app.js` 或 `styles.css` 时记得同时递增 `index.html` 里的 `?v=` 版本号，
否则浏览器会继续用缓存里的旧文件。

验证：

```bash
curl -s http://127.0.0.1:8765/api/status
# 经 nginx，未登录应为 401，登录后 200
curl -sk -o /dev/null -w '%{http_code}\n' https://xiaoxu666.asia/knowledge-api/status
```

## 已知约束

**图片只能发给视觉模型。** 问答时服务会把命中文档的配图转 base64、以 `image_url`
多模态段发出。纯文本模型（`deepseek-chat`、`deepseek-v4-pro` 等）会整个请求 400 拒收，
报 `unknown variant image_url, expected text`。`call_model` 已对这类报错退回纯文本重试
一次——文档的图片 OCR 文字本来就在上下文里，所以退回后仍能作答。但用户当次上传的截图
无法降级，那种情况会明确提示去换支持视觉的模型。

**依赖分两层。** `pypdf` 在 `server.py` 导入时就需要；`playwright` 和
`rapidocr_onnxruntime` 只被导入/OCR 子进程用到，缺了不影响服务启动和问答。
