# 部署配置说明

记录 `xiaoxu666.asia` 后台服务在服务器上的运行时配置。**本目录只有模板，不含任何密钥值。**

## 为什么需要这个目录

应用代码在 git 里，但服务真正跑起来还依赖三样不在 git 里的东西：

1. systemd 服务定义和环境变量（在 `/etc/systemd/system/`）
2. nginx 站点配置（在 `/etc/nginx/sites-available/`）
3. 两个加密密钥（一个是环境变量，一个是文件）

以前这些只存在于服务器磁盘上，没有任何记录。本目录补上「需要配什么」的清单，
避免重建服务器时漏配。真实值仍然只在服务器和你的密码管理器里。

## 当前生产环境

| 项目 | 值 |
|---|---|
| 主机 | `ubuntu@152.32.174.85`（UCloud 香港） |
| SSH 密钥 | `D:\ServerKeys\xiaoxu-ucloud-ed25519` |
| 应用目录 | `/srv/fastapiproject` |
| 运行用户 | `fastapiproject` |
| 应用端口 | `127.0.0.1:8000`（只监听本地，由 nginx 转发） |
| 公网地址 | `https://xiaoxu666.asia/ui/` |
| systemd 单元 | `fastapiproject.service` |
| 前端产物 | `/srv/fastapiproject/frontend/dist` |
| 手机 App 产物 | `/srv/fastapiproject/app-frontend-dist` |
| 生意参谋数据库 | `/srv/fastapiproject/sycm_data/sycm_data.db` |

同机还有一个 `fastapiproject-old-server-tunnel.service`，用 SSH 隧道连到旧的
阿里云服务器 `121.196.150.21`，供 `/software/` 和 `/wpfapp1/` 两个路径转发使用。

## 知识问答（独立服务，代码在 `services/knowledge-base/`）

前端「知识问答」页面（`frontend/src/views/KnowledgeView.vue`、
`app-frontend/src/views/KnowledgePage.vue`）调用的 `/knowledge/` 和 `/knowledge-api/`
**不由本项目 FastAPI 提供**，而是另一个独立服务：

| 项目 | 值 |
|---|---|
| 服务 | `knowledge-base.service` |
| 端口 | `127.0.0.1:8765` |
| 运行目录 | `/srv/knowledge-base` |
| 入口 | `server.py`（标准库 `ThreadingHTTPServer`，非 FastAPI） |
| 仓库内代码 | `services/knowledge-base/`（详见该目录的 README） |
| 数据库 | `/srv/knowledge-base/knowledge.db`（不入 git） |
| 文档配图 | `/srv/knowledge-base/alidocs_images/`（不入 git） |
| 模型配置 | `/srv/knowledge-base/ai_config.json`（含 API Key，不入 git） |

代码 2026-08-08 已纳入本仓库的 `services/knowledge-base/`。在那之前只存在于开发机的
`C:\Users\Administrator\ai-knowledge-web`，无版本控制——曾发生改动被静默还原、
以及新旧副本只能靠比对 md5 分辨的情况。

**但 CI 目前只部署 `/srv/fastapiproject`，不会碰 `/srv/knowledge-base`。**
改了那个目录的代码仍需手工同步并 `systemctl restart knowledge-base`，步骤见其 README。

三条 nginx location（`/__knowledge_auth`、`/knowledge/`、`/knowledge-api/`）
缺任何一条，请求都会落到 `location /` 被 FastAPI 当成未知路由，
前端表现为知识问答整页 404。登录鉴权完全由 `auth_request` 提供，
知识库服务自身不校验会话，删掉 `auth_request` 等于把知识库公开。

## 目录内容

```
deploy/
├── README.md                              本文件
├── .env.example                           全部环境变量清单（只有名字，没有值）
├── systemd/
│   ├── fastapiproject.service.template    主服务单元
│   ├── knowledge-base.service.template    知识问答服务单元
│   └── drop-ins.template.md               5 个 drop-in 配置说明
└── nginx/
    └── xiaoxu.conf.template               站点配置
```

## 两个不可再生的密钥

这两样丢了无法恢复，**必须单独备份到密码管理器**：

| 密钥 | 位置 | 丢失后果 |
|---|---|---|
| `AUTH_ENCRYPTION_KEY` | systemd drop-in `auth-security.conf` | 已启用二次验证的账号，TOTP 密钥无法解密 |
| `account-password.key` | `/srv/fastapiproject/.runtime-secrets/`（44 字节文件） | 店铺账号里所有已加密的密码字段无法解开 |

其余令牌（`SYCM_UPLOAD_TOKEN`、`DINGTALK_PROFIT_SYNC_TOKEN`、`LICENSE_ADMIN_TOKEN`、
`DINGTALK_ROBOT_WEBHOOK`）可以随时更换，代价只是同步更新调用方配置。

其中 `SYCM_UPLOAD_TOKEN` 更换后，本地生意参谋采集程序也要改成同一个值，
否则采集端无法上传数据和领取同步任务。

`SERVER_STATUS_PUSH_TOKEN` 同理：每台被监控的机器上，上报脚本用的值必须和主站一致，
否则上报被 401 拒绝，那台机器在「服务器运行」页上会一直停在「未上报」。

## 服务器运行页要显示第二台机器

主站只能读它自己所在的机器（`/proc`、`systemctl`、磁盘用量都是本地的），
所以每台额外的机器必须主动上报。少了任何一步，页面就只显示一台。

**主站**（`fastapiproject.service`）：

```
Environment=SERVER_STATUS_REMOTE_NODES=aliyun:阿里云旧服务器
Environment=SERVER_STATUS_PUSH_TOKEN=<随机串>
```

`SERVER_STATUS_REMOTE_NODES` 是 `id:显示名` 列表，逗号分隔。
**没列在这里的机器，在它第一次上报之前不会出现在页面上** ——
列出来才能显示成「未上报」，否则你无法区分"这台机器坏了"和"我忘了配"。

**被监控的机器**：拷两个文件过去，不需要装依赖（纯标准库）。

```bash
sudo mkdir -p /opt/ops
# 从仓库拷：scripts/ops/report_server_status.py 和 app/services/server_status.py
# 保持仓库目录结构，或者把两个文件放同一目录

sudo cp deploy/systemd/server-status-report.service.template \
        /etc/systemd/system/server-status-report.service
# 改里面的 --node-id / --label，并把 token 写进 drop-in
sudo systemctl enable --now server-status-report
```

`--node-id` 必须和主站 `SERVER_STATUS_REMOTE_NODES` 里的 id 一致，否则会多出一张无标签的卡片。

验证：

```bash
# 在被监控的机器上手动跑一次，看返回
sudo -u ops SERVER_STATUS_PUSH_TOKEN=<值> python3 /opt/ops/report_server_status.py \
    --base-url https://xiaoxu666.asia --node-id aliyun --token-env SERVER_STATUS_PUSH_TOKEN

# 期望 "ok 200 {...}"；401 说明 token 和主站不一致
```

## 备份现有配置

在服务器上执行，把当前真实配置（含密钥值）导出到一个文件，然后自己保存到安全位置：

```bash
sudo sh -c '
  echo "=== fastapiproject.service ==="
  cat /etc/systemd/system/fastapiproject.service
  echo
  echo "=== drop-ins ==="
  for f in /etc/systemd/system/fastapiproject.service.d/*.conf; do
    echo "--- $f ---"; cat "$f"
  done
  echo
  echo "=== account-password.key (base64) ==="
  base64 -w0 /srv/fastapiproject/.runtime-secrets/account-password.key; echo
' > ~/fastapiproject-config-backup.txt
```

**这个文件含明文密钥，不要提交到 git，不要放在项目目录里。**
下载到本地后建议存进密码管理器，然后删除服务器上的副本。

## 重建服务器的步骤

1. 装依赖：Python 3.12、nginx、certbot
2. 建用户和目录：`useradd -r fastapiproject`，代码放 `/srv/fastapiproject`
3. 建虚拟环境：`python3 -m venv .venv`，然后 `.venv/bin/pip install -r requirements.txt`
4. 按 `systemd/` 下的模板创建服务单元和 5 个 drop-in，填入真实密钥值
5. 恢复 `.runtime-secrets/account-password.key`（权限 `640`，属主 `fastapiproject`）
6. 恢复数据库 `shop_records.db` 和 `sycm_data/sycm_data.db`
7. 按 `nginx/` 模板配置站点，用 certbot 申请证书
8. `systemctl daemon-reload && systemctl enable --now fastapiproject`
9. 验证：`curl -s http://127.0.0.1:8000/api/health`
10. 恢复知识问答服务（见上文「知识问答」一节）：
    代码从本仓库 `services/knowledge-base/` 复制到 `/srv/knowledge-base`，
    再从备份还原三样不入 git 的运行时数据——`knowledge.db`、`alidocs_images/`、
    `ai_config.json`。然后建 `.venv` 装 `requirements.txt`，
    `systemctl enable --now knowledge-base`
11. 验证知识问答：

    ```bash
    curl -s http://127.0.0.1:8765/api/status
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/api/documents
    # 经 nginx（未登录应为 401，登录后为 200）
    curl -sk -o /dev/null -w '%{http_code}\n' https://xiaoxu666.asia/knowledge-api/status
    ```

## 已知问题

`scripts/release.ps1` 的默认部署目标是 `121.196.150.21` / `root` / `xiaoxu.pem`，
指向的是旧的阿里云服务器，**不是**当前生产环境。直接运行会发布到错误的机器上。
使用前必须显式传参，或先修正脚本里的默认值。
