# easy_wg_mikrotik

Web UI for managing WireGuard peers on MikroTik routers. Talks directly to RouterOS API, generates client configs and QR codes. Runs as a plain Python app — no Docker, no Node.

## Requirements

- Python 3.10+
- MikroTik router running RouterOS v7+ with WireGuard

## Setup

```bash
git clone https://github.com/ottoxgam/easy_wg_mikrotik.git
cd easy_wg_mikrotik

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # edit as needed
python app.py
```

Open `http://localhost:5000`.

## Configuration

`.env` values:

| Variable | Default | Notes |
|---|---|---|
| `MIKROTIK_HOST` | `192.168.88.1` | Pre-fills the login form |
| `MIKROTIK_PORT` | `8728` | RouterOS API port |
| `DEFAULT_LOCALE` | `en` | `ko` / `zh` / `ja` |
| `SECRET_KEY` | random | Change this in production |
| `PORT` | `5000` | |
| `FLASK_DEBUG` | `0` | |

## Usage

1. Log in with your MikroTik credentials
2. Pick a WireGuard interface — subnet and keepalive are auto-filled from the router
3. Set an endpoint (`host:port`) and create the client
4. Scan the QR code or download the `.conf` file

Clients can be deleted from the list view at any time.

## Stack

- Flask, librouteros, cryptography (X25519), qrcode[svg]
- Tailwind CSS + Bootstrap Icons (CDN), Stimulus (importmap)

## Security notes

Credentials live only in the server-side session (encrypted with `SECRET_KEY`). The remember-me cookie stores host/user/port, never the password. Use HTTPS in production.
