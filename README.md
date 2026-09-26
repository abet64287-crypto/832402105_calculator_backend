# 832402105 计算器后端

本项目通过 HTTP JSON API 安全解析四则与科学计算表达式，并把每次成功计算写入后端数据库。未配置 `DATABASE_URL` 时使用本地 SQLite；配置 PostgreSQL 连接地址后使用 PostgreSQL。它与前端项目是两个独立目录，可分别放入不同的 GitHub 仓库。

## 技术与运行环境

- Python 3.10 或更新版本；Render 根据 `.python-version` 使用 Python 3.12。HTTP 服务和 SQLite 模式使用 Python 标准库。
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
| `CALCULATOR_HOST` | `127.0.0.1` | 监听地址；容器或远程服务器通常设为 `0.0.0.0`。 |
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

## Render Web Service + PostgreSQL 部署

1. 在 Render 创建 PostgreSQL 数据库，并在同一地区创建连接后端 GitHub 仓库的 Web Service。数据库和 Web Service 使用同一地区，可通过 Render 内网连接。
2. Web Service 的 **Build Command** 填 `pip install -r requirements.txt`，**Start Command** 填 `python -m src.main`，**Health Check Path** 填 `/api/health`。
3. 在 Web Service 的 **Environment** 配置 `CALCULATOR_HOST=0.0.0.0`、`DATABASE_URL=<PostgreSQL Internal URL>`、`CALCULATOR_ALLOWED_ORIGINS=<前端完整 HTTPS 源地址>`。前端源地址不带末尾 `/`，例如 `https://username.github.io`。Render 提供的 `PORT` 会自动读取，不必另设 `CALCULATOR_PORT`。
4. 部署日志显示 API 启动后，访问 `https://<后端域名>/api/health`，应得到 `{"success":true,"status":"ok"}`。启动时自动建表；成功计算后记录写入 PostgreSQL，刷新页面及重启 Web Service 后应仍能查询、删除。

`DATABASE_URL` 必须从 Render 数据库页面复制 **Internal URL** 并保存在 Web Service 环境变量中，不要写进代码、配置文件或提交记录。本地没有设置 `DATABASE_URL` 时会使用 SQLite；Render 上缺少 `DATABASE_URL` 会拒绝启动，避免把历史误存到临时文件。原来本地 SQLite 中的记录不会自动迁移到新的 PostgreSQL 数据库。

Render Free PostgreSQL 数据库在创建 30 天后到期；如果作业验收期超过该期限，需要升级或在到期前安排可用的持久数据库。Free Web Service 也可能休眠，首次请求需要等待唤醒。

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
- `tests/`：解析器和真实 HTTP API 测试。

两种数据库的表 `calculation_history` 均包含自增 `id`、`expression`、`result`、`created_at`。PostgreSQL 的自增 ID 可能因启动检查事务回滚而跳号，记录 ID 不保证连续。`result` 在数据库中以十进制文本保存；API 同时返回便于普通客户端使用的 JSON 数字 `result` 和精确文本 `result_text`。JavaScript 数字可能舍入长小数或大整数，因此前端优先显示 `result_text`。时间采用 UTC 的 ISO 8601 格式。

## 测试

```sh
python -m unittest discover -s tests -v
```

前后端联调步骤和验收用例见工作区根目录的 `README.md`。单独发布本目录时，可按本文件启动后端并配合独立的前端仓库运行。
