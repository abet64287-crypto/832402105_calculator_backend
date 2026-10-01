# 832402105 计算器后端

本项目通过 HTTP JSON API 安全解析四则与科学计算表达式，并把每次成功计算写入后端数据库。未配置 `DATABASE_URL` 时使用本地 SQLite；配置 PostgreSQL 连接地址后使用 PostgreSQL。它与前端项目是两个独立目录，可分别放入不同的 GitHub 仓库。

## 技术与运行环境

- Python 3.10 或更新版本；仓库的 `.python-version` 标记 3.12，Tencent Cloud 的 systemd 示例实际调用服务器的 `/usr/bin/python3`。HTTP 服务和 SQLite 模式仅使用 Python 标准库。
- PostgreSQL 模式使用 `psycopg`，依赖见 `requirements.txt`。
- Windows、macOS、Linux 均可运行。以下命令均从本项目根目录执行。

## 安装与启动

下载本目录后，进入 `calculator_backend`。本地 SQLite 模式无需安装依赖，运行：

```sh
python -m src.main
```

默认监听 `http://127.0.0.1:8000`。SQLite 模式启动时会自动创建数据库文件 `calculations.db` 和 `calculation_history` 表；再次启动会继续使用已有数据。不要删除数据库文件，否则历史记录会丢失。

同一地址和端口只允许启动一个后端进程；重复启动会直接报端口占用错误。启动时还会执行一次回滚的数据库写入检查，不会新增历史记录。SQLite 不可写时，请检查 `CALCULATOR_DB_PATH` 指向的文件及其父目录；PostgreSQL 无法连接或写入时，请检查 `DATABASE_URL` 和数据库权限。

## 配置

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `CALCULATOR_HOST` | `127.0.0.1` | 监听地址；Tencent Cloud 的 Caddy 反向代理方案保持回环地址，避免直接暴露 API 端口。 |
| `CALCULATOR_PORT` | `8000` | API 端口；未设置时也接受平台提供的 `PORT`。 |
| `DATABASE_URL` | 未设置 | PostgreSQL 连接 URL；设置后优先使用 PostgreSQL，忽略 `CALCULATOR_DB_PATH`。不要写入仓库。 |
| `CALCULATOR_DB_PATH` | 本目录的 `calculations.db` | 仅 SQLite 模式使用的数据库文件路径。 |
| `CALCULATOR_ALLOWED_ORIGINS` | `*` | 允许访问 API 的前端源地址；可用英文逗号分隔多个地址。 |

PowerShell 配置示例：

```powershell
$env:CALCULATOR_PORT = '8000'
$env:CALCULATOR_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
python -m src.main
```

部署后在前端 GitHub 仓库的 **Actions repository variable** 中将 `CALCULATOR_API_BASE_URL` 设为公开后端 HTTPS 地址，并重新运行 Pages 工作流；也可以在前端页面的 **API settings** 中填写该地址。浏览器以前保存的地址可能覆盖默认值。

## Tencent Cloud Lighthouse + SQLite 部署

此方案让 GitHub Pages 继续托管前端，Tencent Cloud Lighthouse（或 CVM）托管后端，历史记录写在服务器持久磁盘的 SQLite 文件。**无需创建 PostgreSQL、设置 `DATABASE_URL` 或开放数据库端口。**示例按 Ubuntu 24.04、后端仓库 `abet64287-crypto/832402105_calculator_backend`、前端 Pages 域名 `abet64287-crypto.github.io` 编写。Ubuntu 24.04 自带 Python 3.12；若选其他镜像，先确认 `python3 --version` 至少为 3.10。

购买前先确认云服务器的付费/续费期限**覆盖你要求的至少 3 个月公网可访问期**，不能仅按购买当天起算 3 个月；预留缓冲可选更长购买期或开启自动续费，并设置到期提醒。服务器本地系统盘不是离线备份。当前尚未购买服务器和域名，以下是部署模板，实际公网地址需要购买后填写。

前端 Pages 使用 HTTPS，API 也需要浏览器信任的 HTTPS。准备一个自己可控制 DNS 的域名，例如为 API 建立 `api.example.com` A 记录，指向云服务器的公网 IP。本文以香港等非中国内地地域为示例；若选择中国内地地域，先核对腾讯云关于网站接入和备案的现行要求。服务器防火墙/安全组仅开放 TCP 80、443 给公网；SSH 22 尽量限制为自己的管理 IP；**不要开放 8000**，Python API 只监听 `127.0.0.1`。

### 1. 安装后端并配置持久目录

SSH 登录 Ubuntu 服务器后运行（只在首次安装时创建 `calculator` 用户）：

```sh
sudo apt update
sudo apt install -y git python3 curl
sudo useradd --system --user-group --home-dir /var/lib/calculator --shell /usr/sbin/nologin calculator
sudo install -d -o calculator -g calculator -m 0750 /var/lib/calculator
sudo install -d -o calculator -g calculator -m 0700 /var/backups/calculator
sudo git clone https://github.com/abet64287-crypto/832402105_calculator_backend.git /opt/calculator-backend
cd /opt/calculator-backend
sudo install -o root -g root -m 0640 deploy/tencent/calculator-api.env.example /etc/calculator-api.env
sudo install -o root -g root -m 0644 deploy/tencent/calculator-api.service /etc/systemd/system/calculator-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now calculator-api.service
curl http://127.0.0.1:8000/api/health
```

最后应返回 `{"success": true, "status": "ok"}`。`/etc/calculator-api.env` 把 `CALCULATOR_DB_PATH` 固定到 `/var/lib/calculator/calculations.db`，并把跨域来源限制为 `https://abet64287-crypto.github.io`（**不含** `/832402105_calculator_frontend/` 路径）。服务使用专门的非登录账户运行，失败后由 systemd 自动重启。`/var/lib/calculator` 须位于会随服务器保留的磁盘上；请勿把它放在临时目录、部署代码目录或每次重建会丢弃的容器层。查看失败原因：

```sh
sudo systemctl status calculator-api.service --no-pager
sudo journalctl -u calculator-api.service -n 80 --no-pager
```

### 2. 用 Caddy 提供 HTTPS

按 [Caddy 官方 Ubuntu 安装说明](https://caddyserver.com/docs/install)安装稳定版；该包会创建 Caddy 的 systemd 服务。域名 DNS 已指向服务器、云防火墙已放行 TCP 80/443 后：

```sh
cd /opt/calculator-backend
sudo install -o root -g root -m 0644 deploy/tencent/Caddyfile /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

在编辑器中把 `api.example.com` **替换为实际 API 域名**。Caddy 将 HTTPS 请求代理到本机 `127.0.0.1:8000`；公网浏览器不直接访问 Python 端口。访问 `https://<实际 API 域名>/api/health` 确认返回成功 JSON。若证书未签发，检查 DNS 与 80/443 入站规则，并查看 `sudo journalctl -u caddy -n 80 --no-pager`。Caddy 自动 HTTPS 的条件见其[官方 HTTPS 指南](https://caddyserver.com/docs/quick-starts/https)。

### 3. 连接前端与验收持久性

在前端 GitHub 仓库 **Settings → Secrets and variables → Actions → Variables** 中设置 `CALCULATOR_API_BASE_URL=https://<实际 API 域名>`（只填 HTTPS 源地址，不加 `/api` 或尾部路径），然后重新运行 Pages 工作流。前端页面若以前手工保存过 API 地址，在 **API settings** 中改为新地址或清除旧设置；浏览器保存值可能覆盖构建默认值。

从 Pages 页面进行一次计算，刷新后确认历史仍在，删除一条记录，再计算并运行 `sudo systemctl restart calculator-api.service`，确认剩余历史仍在。正式验收时还应安全地重启一次云服务器，确认 systemd 自动启动 API 且历史仍在。直接查看 `GET /api/history` 也可核对。SQLite 首次启动自动建表，数据库文件仅存在于服务器，不放入 GitHub 仓库。

### 4. 备份、更新与续期

提供的备份脚本利用 Python `sqlite3` 在线备份 API，后端运行时也能生成一致的数据库副本。安装每日定时任务并立即试运行一次：

```sh
cd /opt/calculator-backend
sudo install -o root -g root -m 0644 deploy/tencent/calculator-backup.service /etc/systemd/system/calculator-backup.service
sudo install -o root -g root -m 0644 deploy/tencent/calculator-backup.timer /etc/systemd/system/calculator-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now calculator-backup.timer
sudo systemctl start calculator-backup.service
sudo journalctl -u calculator-backup.service -n 30 --no-pager
```

副本写入 `/var/backups/calculator/`，文件名带 UTC 时间。**同机备份无法防止服务器/磁盘丢失**：定期把副本下载到个人电脑或另存到云对象存储，并检查备份文件能打开；自行清理旧副本，避免占满磁盘。提醒自己检查服务器续费状态、磁盘容量、DNS 和 HTTPS 证书，确保整个验收窗口都可访问。

代码更新时先同步仓库再重启服务；更新配置文件模板后，按需重新安装对应的 systemd/Caddy 文件并 reload：

```sh
sudo git -C /opt/calculator-backend pull --ff-only
sudo systemctl restart calculator-api.service
```

当前 PostgreSQL 实现仍保留为可选模式：只有明确设置 `DATABASE_URL` 才会启用，届时需要先 `pip install -r requirements.txt`。此 Tencent Cloud 部署方案使用 SQLite，不需要它。SQLite 文件不会自动迁移到 PostgreSQL。

## API

所有响应均为 JSON。成功响应包含 `success: true`；错误响应为 `{"success": false, "error": {"code": "...", "message": "..."}}`。

| 方法与路径 | 用途 | 成功响应 |
| --- | --- | --- |
| `POST /api/calculate` | 提交 `{"expression":"(1+2)*3"}`，由后端计算并保存。 | `{"success":true,"id":1,"expression":"(1+2)*3","result":9,"result_text":"9","created_at":"..."}` |
| `GET /api/history` | 从数据库按最新记录优先读取全部历史。 | `{"success":true,"history":[...]}` |
| `DELETE /api/history/{id}` | 删除指定 ID 的数据库记录。 | `{"success":true,"id":1}`；不存在时返回 404。 |
| `GET /api/health` | 检查服务是否可访问。 | `{"success":true,"status":"ok"}` |

示例（PowerShell）：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/calculate' -Method Post -ContentType 'application/json' -Body '{"expression":"(1+2)*3"}'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/history'
```

支持 `+`、`-`、`*`、`/`、括号、小数、一元正负号；也接受界面使用的 `×`、`÷`、`−`。科学计算扩展支持：

| 语法 | 含义 | 示例 |
| --- | --- | --- |
| `a^b` | 幂，右结合，优先于一元负号 | `2^3^2=512`、`-2^2=-4`、`2^-3=0.125` |
| `sqrt(x)`、`abs(x)` | 平方根、绝对值 | `sqrt(81)=9`、`abs(-5)=5` |
| `ln(x)`、`log(x)` | 自然对数、以 10 为底的对数 | `ln(e)=1`、`log(100)=2` |
| `sin(x)`、`cos(x)`、`tan(x)` | 三角函数，参数单位为**弧度** | `sin(pi/2)=1`、`cos(pi)=-1` |
| `pi` 或 `π`、`e` | 数学常数 | `pi/2`、`e^2` |

函数名使用小写且必须带括号；相乘需写出 `*` 或 `×`，例如 `2*pi`。平方根的参数必须非负；对数的参数必须大于零；`tan(pi/2)`、`0^0` 和负数的非整数次幂无定义。三角函数参数绝对值上限为 1,000,000 弧度，以保证数值约简的可靠性。运算优先级由递归下降解析器实现，不执行用户代码。无效表达式、参数范围错误、除零、请求体错误和不存在的记录会返回明确的错误码；失败计算不会写入历史。

## 代码结构与数据库

- `src/controller.py`：HTTP 路由、请求校验、统一 JSON 响应与 CORS。
- `src/service.py`：表达式分词式读取、递归下降解析、Decimal 运算与科学函数。
- `src/model.py`：SQLite/PostgreSQL 建表、插入、查询和按 ID 删除。
- `src/main.py`：配置与服务入口。
- `deploy/tencent/`：Tencent Cloud 的 systemd、Caddy 与在线 SQLite 备份模板。
- `tests/`：解析器和真实 HTTP API 测试。

两种数据库的表 `calculation_history` 均包含自增 `id`、`expression`、`result`、`created_at`。PostgreSQL 的自增 ID 可能因启动检查事务回滚而跳号，记录 ID 不保证连续。`result` 在数据库中以十进制文本保存；API 同时返回便于普通客户端使用的 JSON 数字 `result` 和精确文本 `result_text`。JavaScript 数字可能舍入长小数或大整数，因此前端优先显示 `result_text`。时间采用 UTC 的 ISO 8601 格式。

## 测试

```sh
python -m unittest discover -s tests -v
```

前后端联调步骤和验收用例见工作区根目录的 `README.md`。单独发布本目录时，可按本文件启动后端并配合独立的前端仓库运行。
