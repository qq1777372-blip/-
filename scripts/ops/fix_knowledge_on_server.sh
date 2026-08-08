#!/usr/bin/env bash
#
# 修复线上「知识问答」整页 404。在生产机（ubuntu@152.32.174.85）上执行。
#
# 症状：/ui/knowledge 打开后 iframe 里显示 {"detail":"Not Found"}。
# 原因：nginx 缺三段 location，/knowledge/ 和 /knowledge-api/ 落到 `location /`
#       被 FastAPI 当成未知路由。nginx 配置不在代码里，CI 也不碰它。
#
# 本脚本做两件事：
#   1. 把 /srv/knowledge-base 的代码更新为 /tmp/kb 里的版本（如果存在）
#   2. 给 nginx 补上三段 location
#
# 可重复执行：两步都会先检测当前状态，已经就绪就跳过。
#
# 用法：
#   # 先在本机把代码传上来（不要传 ai_config.json）
#   scp services/knowledge-base/{server.py,storage.py,app.js,index.html,styles.css} \
#       ubuntu@152.32.174.85:/tmp/kb/
#   # 再在服务器上
#   sudo bash fix_knowledge_on_server.sh

set -euo pipefail

NGINX_CONF="/etc/nginx/sites-available/xiaoxu.conf"
KB_DIR="/srv/knowledge-base"
STAGE_DIR="/tmp/kb"
OWNER="fastapiproject:fastapiproject"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 运行。" >&2
  exit 1
fi

echo "=============================================="
echo " 第 1 步：同步知识库代码"
echo "=============================================="

if [ -d "$STAGE_DIR" ] && [ -n "$(ls -A "$STAGE_DIR" 2>/dev/null)" ]; then
  # ai_config.json 是服务器上的运行时配置（含 API Key），传上来的副本可能指向
  # 已失效的旧网关，覆盖会让问答直接不可用。这里显式拒绝。
  if [ -e "$STAGE_DIR/ai_config.json" ]; then
    echo "!! $STAGE_DIR 里有 ai_config.json，已跳过它。"
    echo "   服务器上的那份是运行时配置，不要覆盖。"
    rm -f "$STAGE_DIR/ai_config.json"
  fi

  mkdir -p "$KB_DIR/backup-$STAMP"
  for f in "$STAGE_DIR"/*; do
    name="$(basename "$f")"
    if [ -f "$KB_DIR/$name" ]; then
      cp -a "$KB_DIR/$name" "$KB_DIR/backup-$STAMP/$name"
    fi
    cp -a "$f" "$KB_DIR/$name"
    echo "  更新 $name"
  done
  chown -R "$OWNER" "$KB_DIR"
  echo "  旧文件已备份到 $KB_DIR/backup-$STAMP"

  systemctl restart knowledge-base
  sleep 3
  if systemctl is-active --quiet knowledge-base; then
    echo "  knowledge-base 已重启并在运行"
  else
    echo "!! knowledge-base 启动失败，回滚代码：" >&2
    cp -a "$KB_DIR/backup-$STAMP/." "$KB_DIR/" 2>/dev/null || true
    chown -R "$OWNER" "$KB_DIR"
    systemctl restart knowledge-base || true
    journalctl -u knowledge-base -n 20 --no-pager >&2
    exit 1
  fi
else
  echo "  $STAGE_DIR 为空或不存在，跳过代码同步。"
  echo "  （只想补 nginx 配置时这是正常的）"
fi

echo
echo "=============================================="
echo " 第 2 步：补 nginx 的三段 location"
echo "=============================================="

if grep -q "__knowledge_auth" "$NGINX_CONF"; then
  echo "  三段 location 已存在，跳过。"
else
  cp -a "$NGINX_CONF" "$NGINX_CONF.bak-$STAMP"
  echo "  已备份到 $NGINX_CONF.bak-$STAMP"

  # 用 Python 插入：要精准定位「server_name 恰为 xiaoxu666.asia 的 443 块」里的
  # `location /`，sed 做不到这种带上下文的判断。
  python3 - "$NGINX_CONF" <<'PYTHON'
import re
import sys

path = sys.argv[1]
source = open(path, encoding="utf-8").read()

BLOCKS = """
    # 知识问答（知识库）—— 独立服务 knowledge-base.service，监听 127.0.0.1:8765。
    # 缺少这三段时 /knowledge/ 和 /knowledge-api/ 会落到下面的 `location /`，
    # 被 FastAPI 当成未知路由返回 {"detail":"Not Found"}，前端整页 404。
    #
    # 鉴权完全依赖 auth_request（子请求打本项目的 /auth/me）。知识库服务自身不校验
    # 会话，删掉 auth_request 等于把整个知识库公开。
    location = /__knowledge_auth {
        internal;
        proxy_pass http://127.0.0.1:8000/auth/me;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header Cookie $http_cookie;
        proxy_set_header X-Original-URI $request_uri;
    }

    location = /knowledge {
        return 302 /knowledge/;
    }

    # 用 proxy_pass 而不是 alias /srv/knowledge-base/public/：正文配图路径形如
    # alidocs_images/<hash>/001.png，只在服务运行目录里，不在 public/。
    # 用 alias 时页面能开但所有配图 404。
    location ^~ /knowledge/ {
        auth_request /__knowledge_auth;
        proxy_pass http://127.0.0.1:8765/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_buffering off;
        add_header Cache-Control "no-cache";
    }

    # 前端调用 /knowledge-api/<name>，服务实际路径是 /api/<name>，尾斜杠负责改写。
    # 问答要等模型返回，超时给到 300s。
    location ^~ /knowledge-api/ {
        auth_request /__knowledge_auth;
        proxy_pass http://127.0.0.1:8765/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }

"""

# 找每个 server { ... } 的起点，挑出 443 且 server_name 恰为 xiaoxu666.asia 的那个。
# www 子域那块只做 301，不能插到那里。
starts = [m.start() for m in re.finditer(r"^server\s*\{", source, re.M)]
if not starts:
    sys.exit("找不到任何 server 块")
starts.append(len(source))

target = None
for i in range(len(starts) - 1):
    block = source[starts[i]:starts[i + 1]]
    if "listen 443" not in block:
        continue
    names = re.search(r"^\s*server_name\s+([^;]+);", block, re.M)
    if not names:
        continue
    if [n.strip() for n in names.group(1).split()] == ["xiaoxu666.asia"]:
        target = (starts[i], starts[i + 1], block)
        break

if target is None:
    sys.exit("找不到 server_name 恰为 xiaoxu666.asia 的 443 块，请手工插入")

begin, end, block = target

# 插到该块最后一个顶层 `location / {` 之前。^~ 前缀匹配优先于 `location /`，
# 所以理论上顺序无关；但放在前面更符合阅读习惯，也和仓库模板一致。
hits = list(re.finditer(r"^    location / \{", block, re.M))
if not hits:
    sys.exit("该 server 块里找不到 `location / {`，请手工插入")
at = hits[-1].start()

patched = source[:begin] + block[:at] + BLOCKS.lstrip("\n") + block[at:] + source[end:]
open(path, "w", encoding="utf-8").write(patched)
print("  已插入三段 location")
PYTHON

  if nginx -t; then
    systemctl reload nginx
    echo "  nginx 配置校验通过并已 reload"
  else
    echo "!! nginx -t 失败，已回滚配置。" >&2
    cp -a "$NGINX_CONF.bak-$STAMP" "$NGINX_CONF"
    exit 1
  fi
fi

echo
echo "=============================================="
echo " 验证"
echo "=============================================="
printf '  knowledge-base 服务   : %s\n' "$(systemctl is-active knowledge-base 2>&1)"
printf '  本地 8765 /api/status : %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8765/api/status)"
printf '  经 nginx /knowledge-api/status（未登录应为 401）: %s\n' \
  "$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 --resolve xiaoxu666.asia:443:127.0.0.1 https://xiaoxu666.asia/knowledge-api/status)"
printf '  经 nginx /knowledge/（未登录应为 401）        : %s\n' \
  "$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 --resolve xiaoxu666.asia:443:127.0.0.1 https://xiaoxu666.asia/knowledge/)"

echo
echo "如果上面两个 nginx 检查返回 401，说明配置生效了（未登录被 auth_request 拦住是对的）。"
echo "返回 404 说明 location 没生效；返回 502 说明 knowledge-base 没起来。"
echo "最后用浏览器登录后打开 https://xiaoxu666.asia/ui/knowledge 确认。"
