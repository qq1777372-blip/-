# systemd drop-ins (`/etc/systemd/system/fastapiproject.service.d/`)

Secret values are NOT stored in this repo. Each file below holds one
`Environment=` line; replace `__REPLACE_ME__` with the real value on the server.

| Drop-in file | Variable | Kind |
|---|---|---|
| `auth-security.conf` | `AUTH_ENCRYPTION_KEY` | secret (hex key) |
| `dingtalk-profit-sync.conf` | `DINGTALK_PROFIT_SYNC_TOKEN` | secret |
| `dingtalk-robot.conf` | `DINGTALK_ROBOT_WEBHOOK` | secret (URL with access_token) |
| `https.conf` | `SESSION_COOKIE_SECURE` | non-secret (`true` behind HTTPS) |
| `sycm-upload.conf` | `SYCM_UPLOAD_TOKEN` | secret |

Template for each:

```ini
[Service]
Environment=VAR_NAME=__REPLACE_ME__
```

Apply with:

```bash
sudo systemctl daemon-reload
sudo systemctl restart fastapiproject
```

## Env vars read by the app but not set on the server (defaults apply)

`APP_NAME`, `DATABASE_URL`, `DINGTALK_ROBOT_SECRET`, `PRODUCT_PARSE_CACHE_DB_PATH`,
`PUBLIC_APP_BASE_URL`, `PUBLISH_FAILURE_REPORT_DB_PATH`,
`PUBLISH_FAILURE_REPORT_READER_USERNAMES`, `REDIS_PREFIX`, `REDIS_URL`,
`RULE_CATALOG_DB_PATH`, `SYCM_DATA_DB_PATH`

## Related unit

`fastapiproject-old-server-tunnel.service` — SSH tunnel (`User=ubuntu`,
`ExecStart=/usr/bin/ssh -NT ...`) to the legacy software server, needed for
`LICENSE_SERVER_BASE_URL` / management API access.

## Runtime secret file (not in repo)

`/srv/fastapiproject/.runtime-secrets/account-password.key` — 44 bytes, mode
`0640`, owner `fastapiproject`. Used by `app/core/account_password_crypto.py`.
