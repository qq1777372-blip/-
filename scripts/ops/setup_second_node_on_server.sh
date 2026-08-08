#!/usr/bin/env bash
#
# 在主服务器上启用「服务器运行」的多节点显示。
#
# 现状：SERVER_STATUS_PUSH_TOKEN 未配置，所以 /dashboard/server-status/push
# 一律返回 503（fail-closed，见 app/api/routes/server_status.py 的
# require_push_token）。任何机器都上报不进来，页面因此只有主服务器一个节点。
#
# 本脚本做两件事：
#   1. 给 fastapiproject 加 SERVER_STATUS_PUSH_TOKEN（没给就随机生成）
#   2. 加 SERVER_STATUS_REMOTE_NODES 声明期望的第二个节点
#
# 跑法（在主服务器上，root 或有 sudo）：
#   sudo bash setup_second_node_on_server.sh
#
# 想自己指定 token 或节点：
#   sudo TOKEN=你的随机串 NODE_ID=aliyun NODE_LABEL=阿里云旧机 \
#        bash setup_second_node_on_server.sh
#
# 可重复运行：已存在的 token 不会被覆盖（除非显式传 TOKEN=）。
set -euo pipefail

SERVICE="fastapiproject"
NODE_ID="${NODE_ID:-aliyun}"
NODE_LABEL="${NODE_LABEL:-阿里云旧机}"
DROPIN_DIR="/etc/systemd/system/${SERVICE}.service.d"
DROPIN="${DROPIN_DIR}/server-status.conf"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 root 或 sudo 运行" >&2
  exit 1
fi

echo "=============================================="
echo " 1/3  读取当前配置"
echo "=============================================="

# 已经配过就沿用，避免每次跑都换 token（换了上报端就要跟着改）
EXISTING_TOKEN=""
if [ -f "$DROPIN" ]; then
  EXISTING_TOKEN="$(sed -n 's/^Environment=SERVER_STATUS_PUSH_TOKEN=//p' "$DROPIN" | head -1)"
  echo "  已有 drop-in: $DROPIN"
  cp -a "$DROPIN" "${DROPIN}.bak-${STAMP}"
  echo "  已备份 -> ${DROPIN}.bak-${STAMP}"
else
  echo "  尚无 drop-in，将新建"
fi

if [ -n "${TOKEN:-}" ]; then
  PUSH_TOKEN="$TOKEN"
  echo "  使用你传入的 TOKEN"
elif [ -n "$EXISTING_TOKEN" ]; then
  PUSH_TOKEN="$EXISTING_TOKEN"
  echo "  沿用已存在的 token（不改动，上报端无需调整）"
else
  PUSH_TOKEN="$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | cut -c1-40)"
  echo "  已随机生成 token"
fi

echo
echo "=============================================="
echo " 2/3  写入 systemd drop-in"
echo "=============================================="

mkdir -p "$DROPIN_DIR"
cat > "$DROPIN" <<EOF
# 由 scripts/ops/setup_second_node_on_server.sh 生成于 ${STAMP}
#
# SERVER_STATUS_PUSH_TOKEN：/dashboard/server-status/push 的鉴权。未设置时该接口
# 返回 503 并拒绝一切上报，页面上就只会有主服务器一个节点。
#
# SERVER_STATUS_REMOTE_NODES：声明期望哪些远程节点，格式 id:显示名，逗号分隔。
# 声明后即使对方还没上报，页面也会显示该节点为「未上报」，而不是干脆不显示——
# 这样才能看出是「没配」还是「配了但挂了」。
[Service]
Environment=SERVER_STATUS_PUSH_TOKEN=${PUSH_TOKEN}
Environment=SERVER_STATUS_REMOTE_NODES=${NODE_ID}:${NODE_LABEL}
EOF
chmod 600 "$DROPIN"
echo "  已写入 $DROPIN (权限 600)"

systemctl daemon-reload
systemctl restart "$SERVICE"
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
  echo "  ${SERVICE} 重启成功"
else
  echo "!! ${SERVICE} 重启后未运行，回滚 drop-in" >&2
  if [ -f "${DROPIN}.bak-${STAMP}" ]; then
    cp -a "${DROPIN}.bak-${STAMP}" "$DROPIN"
  else
    rm -f "$DROPIN"
  fi
  systemctl daemon-reload
  systemctl restart "$SERVICE" || true
  journalctl -u "$SERVICE" -n 30 --no-pager >&2
  exit 1
fi

echo
echo "=============================================="
echo " 3/3  验证"
echo "=============================================="

# 关键判据：没配 token 时是 503，配好后假 token 应该变成 401。
CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H 'Content-Type: application/json' \
  -H 'X-Server-Status-Token: definitely-wrong' \
  --data '{"node_id":"probe","metrics":{}}' \
  http://127.0.0.1:8000/dashboard/server-status/push || echo 000)"

case "$CODE" in
  401) echo "  push 接口返回 401 -> token 已生效（拒绝了错误 token，符合预期）" ;;
  503) echo "!! 仍返回 503 -> token 没读进去，检查 drop-in 是否被别的配置覆盖" >&2 ;;
  422) echo "  push 接口返回 422 -> token 已生效（校验走到了请求体）" ;;
  *)   echo "  push 接口返回 $CODE（预期 401/422，请人工确认）" ;;
esac

echo
echo "=============================================="
echo " 完成。下面是上报端要用的信息"
echo "=============================================="
echo
echo "  PUSH TOKEN : ${PUSH_TOKEN}"
echo "  NODE ID    : ${NODE_ID}"
echo "  NODE LABEL : ${NODE_LABEL}"
echo
echo "刷新「服务器运行」页面，现在应该能看到两个节点："
echo "  主服务器（有数据）和 ${NODE_LABEL}（显示未上报）。"
echo
echo "要让第二个节点真正有数据，在那台机器（121.196.150.21）上："
echo
echo "  # 1. 拷两个文件过去（保持仓库目录结构，或放同一目录）"
echo "  #    scripts/ops/report_server_status.py"
echo "  #    app/services/server_status.py"
echo
echo "  # 2. 手工试一次，确认能通"
echo "  python3 report_server_status.py \\"
echo "      --base-url https://xiaoxu666.asia \\"
echo "      --node-id ${NODE_ID} \\"
echo "      --label '${NODE_LABEL}' \\"
echo "      --token '${PUSH_TOKEN}'"
echo
echo "  # 3. 通了之后配 systemd timer 每 2 分钟上报一次"
echo "  #    unit 模板见 report_server_status.py 开头的注释"
echo
echo "注意：token 建议用 --token-env 从环境变量读，避免出现在 ps 输出里。"
