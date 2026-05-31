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

python app.py
```

Open `http://localhost:5000`.

No `.env` file is required. A secret key is auto-generated and saved to `.secret_key` on first run. See `.env.example` for optional overrides (pre-filling the login form, changing the port, etc.).

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

### Creating a client

1. Log in with your MikroTik credentials
2. Pick a WireGuard interface — subnet, keepalive, and endpoint are auto-filled from the router
3. Fill in any remaining fields and click Create
4. Scan the QR code or download the `.conf` file

The private key and all client-side settings (`client-endpoint`, `client-dns`, `client-allowed-address`, etc.) are stored on the router at creation time, so the config and QR code can be regenerated later from the peer list.

### Managing clients

- **List** — shows each peer's assigned IP, current endpoint, last handshake, and connection status (Active / Disconnected / Waiting)
- **Edit** — modify any peer field that RouterOS exposes: name, comment, allowed address, keepalive, preshared key, responder flag, and all client-side config fields
- **Config / QR** — regenerate the `.conf` file and QR code for any peer that has a stored private key
- **Delete** — removes the peer from the router

### Connection status

| Badge | Meaning |
|---|---|
| Active (green, fast pulse) | Last handshake within 2 minutes |
| Disconnected (yellow, slow pulse) | Last handshake older than 2 minutes |
| Waiting (gray, no pulse) | Never connected |

## Stack

- Flask, librouteros, cryptography (X25519), qrcode[svg]
- Tailwind CSS + Bootstrap Icons (CDN), Stimulus (importmap)

## Security notes

Credentials live only in the server-side session (encrypted with `SECRET_KEY`). The remember-me cookie stores host/user/port, never the password. Use HTTPS in production.
