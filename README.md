# 832402105 计算器后端

本项目通过 HTTP JSON API 安全解析四则运算表达式，并把每次成功计算写入 SQLite。它与前端项目是两个独立目录，可分别放入不同的 GitHub 仓库。

## 技术与运行环境

- Python 3.10 或更新版本；仅使用 Python 标准库，无需安装第三方包。
- SQLite 由 Python 自带的 `sqlite3` 模块提供。
- Windows、macOS、Linux 均可运行。以下命令均从本项目根目录执行。

## 安装与启动

下载本目录后，进入 `calculator_backend`。无依赖安装步骤，运行：

```sh
python -m src.main
```

默认监听 `http://127.0.0.1:8000`。启动时会自动创建数据库文件 `calculations.db` 和 `calculation_history` 表；再次启动会继续使用已有数据。不要删除数据库文件，否则历史记录会丢失。

## 配置

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `CALCULATOR_HOST` | `127.0.0.1` | 监听地址；容器或远程服务器通常设为 `0.0.0.0`。 |
| `CALCULATOR_PORT` | `8000` | API 端口；未设置时也接受平台提供的 `PORT`。 |
| `CALCULATOR_DB_PATH` | 本目录的 `calculations.db` | SQLite 数据库文件路径；公开部署时应指向持久化磁盘。 |
| `CALCULATOR_ALLOWED_ORIGINS` | `*` | 允许访问 API 的前端源地址；可用英文逗号分隔多个地址。 |

PowerShell 配置示例：

```powershell
$env:CALCULATOR_PORT = '8000'
$env:CALCULATOR_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
python -m src.main
```

生产环境应通过 HTTPS 反向代理开放 API，并为 `CALCULATOR_DB_PATH` 配置持久化存储。部署后需要把前端 `src/config.js` 中的默认 API 地址改为公开后端地址，或在前端页面的“接口设置”中填写该地址。

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

支持 `+`、`-`、`*`、`/`、括号、小数、一元正负号；也接受界面使用的 `×`、`÷`、`−`。运算优先级由递归下降解析器实现，不执行用户代码。无效表达式、除零、请求体错误和不存在的记录会返回明确的错误码；失败计算不会写入历史。

## 代码结构与数据库

- `src/controller.py`：HTTP 路由、请求校验、统一 JSON 响应与 CORS。
- `src/service.py`：表达式分词式读取、递归下降解析和 Decimal 运算。
- `src/model.py`：SQLite 建表、插入、查询和按 ID 删除。
- `src/main.py`：配置与服务入口。
- `tests/`：解析器和真实 HTTP API 测试。

表 `calculation_history` 包含自增 `id`、`expression`、`result`、`created_at`。`result` 在数据库中以十进制文本保存；API 同时返回便于普通客户端使用的 JSON 数字 `result` 和精确文本 `result_text`。JavaScript 数字可能舍入长小数或大整数，因此前端优先显示 `result_text`。时间采用 UTC 的 ISO 8601 格式。

## 测试

```sh
python -m unittest discover -s tests -v
```

前后端联调步骤和验收用例见工作区根目录的 `README.md`。单独发布本目录时，可按本文件启动后端并配合独立的前端仓库运行。
