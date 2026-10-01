# Calculator Backend (832402105)

I built this Python JSON API for my calculator assignment. The [frontend](https://github.com/abet64287-crypto/832402105_calculator_frontend) is a separate project. It sends expressions to this backend, which calculates them and saves successful results for the history page.

My deployment plan is GitHub Pages for the frontend and Tencent Cloud Lighthouse for this backend. The cloud server will use SQLite on its persistent disk. The code also supports PostgreSQL, but it is optional. **The server and domain have not been purchased or deployed yet**, so the online checks described below are still pending.

## Requirements and local use

- Python 3.10 or newer. I use Python 3.12 in development (`.python-version`).
- Windows, macOS, or Linux locally. The cloud steps use Ubuntu Server 24.04 LTS.
- SQLite mode uses only the standard library. PostgreSQL mode needs `pip install -r requirements.txt`.

From this repository directory, start the API:

```sh
python -m src.main
```

It listens at `http://127.0.0.1:8000`. SQLite automatically creates `calculations.db` and the `calculation_history` table on first start, then reuses them. Keep that file to keep history. Only one backend process can use the same port. Startup checks database write access in a rolled-back transaction, without adding history.

Run tests with:

```sh
python -m unittest discover -s tests -v
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CALCULATOR_HOST` | `127.0.0.1` | Listening address; keep it on localhost behind Caddy. |
| `CALCULATOR_PORT` | `8000` | API port; `PORT` is also accepted if this is unset. |
| `CALCULATOR_DB_PATH` | `calculations.db` in this repository | SQLite file path; use a persistent absolute path on the server. |
| `CALCULATOR_ALLOWED_ORIGINS` | `*` | Comma-separated browser origins allowed by CORS. Restrict it for deployment. |
| `DATABASE_URL` | Unset | Optional PostgreSQL URL. When set, PostgreSQL is used instead of SQLite. Never commit it. |

For a local PowerShell frontend at port 5173:

```powershell
$env:CALCULATOR_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
python -m src.main
```

If SQLite cannot be opened, check the file and parent directory permissions. In PostgreSQL mode, check the URL and database permissions. This Tencent Cloud setup sets neither `DATABASE_URL` nor `RENDER`.

## Tencent Cloud Lighthouse deployment plan

I plan to run the backend on a Hong Kong Lighthouse server. A CVM server can also use these steps. Choose Ubuntu Server 24.04 LTS or verify that another image has Python 3.10 or newer. I need a persistent disk and an API domain such as `api.example.com` pointing to the server's public IP.

The site must remain accessible during evaluation. I am planning for **at least three months of public availability**, so I need to check both the server and domain expiry dates, allow setup time, and renew before they expire. For a mainland China server, check current domain and ICP filing requirements.

GitHub Pages uses HTTPS, so the public API also needs HTTPS. Create a DNS A record for the API domain. In the Tencent Cloud firewall, open TCP 80 and 443, and restrict SSH 22 to my management IP if possible. **Do not open port 8000 publicly**. Python listens only on `127.0.0.1`, with Caddy in front. SQLite does not need a database port.

### 1. Install and start the API

Connect by SSH and run these commands once. Create the `calculator` user only on the initial install:

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

The health response should be `{"success": true, "status": "ok"}`. The environment file puts SQLite at `/var/lib/calculator/calculations.db` and limits CORS to `https://abet64287-crypto.github.io`. A CORS origin does **not** contain the Pages repository path. Systemd runs the service as a dedicated non-login user and restarts it after failures. Keep `/var/lib/calculator` on a disk that survives restarts and code updates.

If startup fails:

```sh
sudo systemctl status calculator-api.service --no-pager
sudo journalctl -u calculator-api.service -n 80 --no-pager
```

### 2. Set up Caddy and HTTPS

Install stable Caddy using the [official Ubuntu instructions](https://caddyserver.com/docs/install). Once DNS and TCP 80/443 are ready:

```sh
cd /opt/calculator-backend
sudo install -o root -g root -m 0644 deploy/tencent/Caddyfile /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Replace `api.example.com` in the editor with the real API domain. Visit `https://<your-api-domain>/api/health`. Caddy sends requests to `127.0.0.1:8000` and [manages the certificate](https://caddyserver.com/docs/quick-starts/https). If HTTPS fails, check DNS, the firewall, and `sudo journalctl -u caddy -n 80 --no-pager`.

### 3. Connect the frontend and check persistence

In the frontend GitHub repository, open **Settings → Secrets and variables → Actions → Variables**. Set `CALCULATOR_API_BASE_URL` to `https://<your-api-domain>`, with no `/api` path, then rerun the Pages workflow. The frontend's **API settings** can also hold a manual address; clear an older browser-saved address if it overrides the build value.

On the public Pages site, calculate an expression, refresh to view history, delete a record, and calculate again. Restart the backend with `sudo systemctl restart calculator-api.service` and check that the remaining history is still there. Before final acceptance, safely reboot the server and confirm systemd starts the API and history persists. `GET /api/history` can help inspect records. **These online checks remain pending until the server and domain exist.**

### 4. Back up and maintain SQLite

The included script uses Python's SQLite online backup API for a consistent copy while the API runs. Install its daily timer and try one backup:

```sh
cd /opt/calculator-backend
sudo install -o root -g root -m 0644 deploy/tencent/calculator-backup.service /etc/systemd/system/calculator-backup.service
sudo install -o root -g root -m 0644 deploy/tencent/calculator-backup.timer /etc/systemd/system/calculator-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now calculator-backup.timer
sudo systemctl start calculator-backup.service
sudo journalctl -u calculator-backup.service -n 30 --no-pager
```

Copies go to `/var/backups/calculator/` with UTC timestamps. A copy on the same server cannot protect against loss of that server or disk. I will need to download copies or store them elsewhere, check that one can be opened, remove old files before the disk fills, and monitor renewal, DNS, certificates, and service status during evaluation.

To update the code:

```sh
sudo git -C /opt/calculator-backend pull --ff-only
sudo systemctl restart calculator-api.service
```

If a deployment template changes, reinstall that systemd or Caddy file and reload its service. This plan uses SQLite, so no `DATABASE_URL`, PostgreSQL server, or `pip install -r requirements.txt` is needed. SQLite history does not automatically migrate to PostgreSQL.

## API reference

Every response is JSON. Success has `success: true`; errors use `{"success":false,"error":{"code":"...","message":"..."}}`.

| Method and path | What it does | Example success |
| --- | --- | --- |
| `POST /api/calculate` | Calculate and save `{"expression":"(1+2)*3"}`. | `{"success":true,"id":1,"expression":"(1+2)*3","result":9,"result_text":"9","created_at":"..."}` |
| `GET /api/history` | List history, newest first. | `{"success":true,"history":[...]}` |
| `DELETE /api/history/{id}` | Delete a record; a missing ID returns 404. | `{"success":true,"id":1}` |
| `GET /api/health` | Check if the API responds. | `{"success":true,"status":"ok"}` |

Local PowerShell example:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/calculate' -Method Post -ContentType 'application/json' -Body '{"expression":"(1+2)*3"}'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/history'
```

## Calculator input

The parser handles `+`, `-`, `*`, `/`, parentheses, decimals, unary signs, and the display symbols `×`, `÷`, and `−`. Scientific input includes:

| Syntax | Meaning | Example |
| --- | --- | --- |
| `a^b` | Right-associative power, above unary minus | `2^3^2=512`; `-2^2=-4` |
| `sqrt(x)`, `abs(x)` | Square root and absolute value | `sqrt(81)=9` |
| `ln(x)`, `log(x)` | Natural and base-10 logarithms | `ln(e)=1`; `log(100)=2` |
| `sin(x)`, `cos(x)`, `tan(x)` | Trigonometry in **radians** | `sin(pi/2)=1` |
| `pi` or `π`, `e` | Constants | `2*pi` |

Functions are lowercase and need parentheses; multiplication must be explicit, as in `2*pi`. Square root inputs must be nonnegative and logarithm inputs positive. `tan(pi/2)`, `0^0`, and negative numbers raised to non-integer powers are undefined. Trigonometric inputs are limited to an absolute value of 1,000,000 radians for numerical reliability. I use a recursive descent parser instead of running input as Python code. Invalid input and division by zero produce JSON errors; failed calculations are not saved.

## Code and database

- `src/controller.py`: HTTP routes, validation, JSON responses, and CORS.
- `src/service.py`: parser, Decimal arithmetic, and scientific functions.
- `src/model.py`: SQLite and optional PostgreSQL history operations.
- `src/main.py`: configuration and server startup.
- `deploy/tencent/`: systemd, Caddy, and SQLite backup templates.
- `tests/`: parser and HTTP API tests.

The `calculation_history` table stores an auto-incrementing `id`, `expression`, `result`, and `created_at`. Results are decimal text in the database. The API returns a JSON number (`result`) and exact decimal text (`result_text`); the frontend displays the text because JavaScript numbers can round large or precise values. Timestamps use UTC ISO 8601. PostgreSQL IDs can skip numbers after a rolled-back startup check.
