# Calculator Backend (832402105)

I built this Python JSON API for my calculator assignment. The [frontend](https://github.com/abet64287-crypto/832402105_calculator_frontend) is a separate project. It sends expressions to this backend, which calculates them and saves successful results for the history page.

The frontend is published on GitHub Pages. I bought a Tencent Cloud server in Hong Kong and the `calculator-demo.site` domain for this backend. The Pages deployment now uses <https://43-129-177-221.sslip.io/api/health> because direct connections to my domain reset on some networks. Both hostnames reach the same server at `43.129.177.221`. I keep SQLite history on the server disk. The code also supports PostgreSQL, but it is optional. Public HTTPS, calculation, history, deletion, error requests, and a Pages browser test have passed. A saved row also survived a full server reboot.

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

## Tencent Cloud deployment (Ubuntu Server 24.04 LTS)

My server is in Tencent Cloud's Hong Kong Zone 3, and it uses Ubuntu Server 24.04 LTS. On October 3, I confirmed that the DNSPod A record for `api.calculator-demo.site` resolves to `43.129.177.221`. I later added `43-129-177-221.sslip.io` as a second hostname because direct requests to the purchased domain were reset on some networks. The API runs under systemd on `127.0.0.1:8000` behind Caddy. Direct requests to the second hostname returned HTTP 200 with a valid HTTPS certificate, and Caddy listened on TCP 80 and 443. I have not separately verified HTTP redirection.

The task asks for public access during evaluation and does not specify a three-month period. My server expires on **2027-01-01**, about three months after purchase, and I am using that term for now. If evaluation continues beyond that date, I will need to renew the server. The public [domain registration record](https://rdap.radix.host/rdap/domain/calculator-demo.site), checked on October 3, lists expiry as **2027-10-03 07:53:10 UTC**. I also need to keep the services running during evaluation.

GitHub Pages uses HTTPS, so the public API needs HTTPS. In the Tencent Cloud firewall, allow inbound TCP 80 and 443, and restrict SSH 22 to my management IP if possible. **Do not open port 8000 publicly**. Python listens only on `127.0.0.1`, with Caddy in front. SQLite does not need a database port.

### 1. Check the DNS A record and firewall

I added an `A` record in DNSPod for `calculator-demo.site` with host **`api`**, line **Default**, and value **`43.129.177.221`**. The verified result is `api.calculator-demo.site -> 43.129.177.221`. To check it again from my computer:

```powershell
Resolve-DnsName api.calculator-demo.site -Type A
```

The returned IPv4 address should be `43.129.177.221`. If it differs later, check the DNSPod record and wait for the previous DNS cache to expire. The alternate `43-129-177-221.sslip.io` name embeds the same IP and needs no DNSPod record. DNS alone would not prove that ports 80 and 443 are available.

### 2. Install and start the API

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
curl --retry 8 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:8000/api/health
```

The local health request returned HTTP 200. Systemd can mark this `Type=simple` service active just before Python begins listening; the retry avoids treating that short startup gap as a failed install. The environment file puts SQLite at `/var/lib/calculator/calculations.db` and limits CORS to `https://abet64287-crypto.github.io`. A public CORS preflight returned HTTP 204 with that allowed origin. A CORS origin does **not** contain the Pages repository path. Systemd runs the service as a dedicated non-login user and restarts it after failures. Keep `/var/lib/calculator` on a disk that survives restarts and code updates.

If startup fails:

```sh
sudo systemctl status calculator-api.service --no-pager
sudo journalctl -u calculator-api.service -n 80 --no-pager
```

### 3. Set up Caddy and HTTPS

After DNS resolves to the server and TCP 80/443 are reachable, install stable Caddy using its [official Ubuntu package instructions](https://caddyserver.com/docs/install):

```sh
sudo apt install --yes debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

The repository's Caddyfile names both HTTPS hostnames and proxies them to the local API. Install and check it:

```sh
cd /opt/calculator-backend
sudo install -o root -g root -m 0644 deploy/tencent/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
curl -fsS https://43-129-177-221.sslip.io/api/health
```

Caddy sends requests to `127.0.0.1:8000` and [manages the certificates](https://caddyserver.com/docs/automatic-https). Certificate setup may take a moment after reload. The alternate hostname is provided by [sslip.io](https://sslip.io/), which maps its embedded IP to this server. I verified the alternate health and history endpoints over a direct connection without a proxy; TLS validation passed, and the Pages CORS preflight returned HTTP 204. The purchased domain still works from some networks, but direct requests on my tested route returned `ERR_CONNECTION_RESET`. If HTTPS fails later, check DNS, TCP 80/443, `sudo systemctl status caddy --no-pager`, and `sudo journalctl -u caddy -n 80 --no-pager`. If the server IP changes, the sslip.io hostname and Pages variable must change too. I have not separately verified HTTP redirection.

### 4. Connect the frontend and check persistence

The frontend GitHub repository has `CALCULATOR_API_BASE_URL` set to `https://43-129-177-221.sslip.io`, with no `/api` path or trailing slash. Pages workflow run `37127417185` succeeded on October 3. The public page returned HTTP 200, and its published `config.js` contains that API origin. The frontend's **API settings** can hold a manual address; replace an older browser-saved address if it overrides the build value.

Direct public HTTPS API requests returned `12+8=20` as history ID 1 and `sqrt(81)=9` as ID 2. I read history, deleted ID 1, restarted `calculator-api.service`, and confirmed ID 2 remained. `1/0` returned HTTP 400 without adding a row. After switching Pages to the alternate hostname, the previously failing device and Wi-Fi showed **Backend connected**; `sin(pi/2)=1` entered history and deletion worked. After a full server reboot, `calculator-api.service`, `caddy.service`, and `calculator-backup.timer` were active. The `sqrt(81)=9` row and backup file remained. More expression and theme cases can still be checked in the public browser.

### 5. Back up and maintain SQLite

The included script uses Python's SQLite online backup API for a consistent copy while the API runs. The daily timer is active. A manual run succeeded on October 3 and created a 12 KB file at `/var/backups/calculator/calculations-20261003T085144366294Z.db`. These commands install the timer and run a backup again:

```sh
cd /opt/calculator-backend
sudo install -o root -g root -m 0644 deploy/tencent/calculator-backup.service /etc/systemd/system/calculator-backup.service
sudo install -o root -g root -m 0644 deploy/tencent/calculator-backup.timer /etc/systemd/system/calculator-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now calculator-backup.timer
sudo systemctl start calculator-backup.service
sudo journalctl -u calculator-backup.service -n 30 --no-pager
```

Copies go to `/var/backups/calculator/` with UTC timestamps. The manual copy remained after a full server reboot. A copy on the same server cannot protect against loss of that server or disk. I still need to move copies off the server, check that one can be opened, remove old files before the disk fills, and monitor renewal, DNS, certificates, and service status during evaluation.

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
