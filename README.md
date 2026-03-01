# TeneoNode

An automated multi-account node bot for the Teneo Network with real-time dashboard, proxy management, and heartbeat tracking.

## 🚀 Join Teneo Network

To get started and earn points, sign up using my referral link:

👉 **[Join Teneo Network](https://dashboard.teneo.pro/auth/signup?referralCode=sYkC5)**

---

## ✨ Features

- **Multi-Account Support** – manage multiple accounts simultaneously from a single instance
- **Real-time Dashboard** – live Rich UI showing connection status, points, heartbeats, uptime, and pts/hr per account
- **Token Validation** – validates each access token via the Teneo API before connecting
- **Heartbeat Tracking** – counts and displays heartbeats per account (75 pts each)
- **Daily Progress Bars** – visual progress toward the 7,200 daily point cap per account
- **Global Statistics Panel** – total points, today's points, active accounts, average pts/hr, and runtime
- **Proxy Support** – HTTP and SOCKS5 proxies with concurrent speed testing (filters >1000ms)
- **Proxy Per Account** – optionally assign a different proxy to each account
- **Automatic Rotation** – optional proxy rotation on reconnect
- **Random User-Agent** – simulates organic traffic via `fake-useragent`
- **Automatic Reconnection** – reconnects on WebSocket disconnect (up to 5 attempts, then resets)
- **Connection Pre-Test** – tests WebSocket connectivity before starting all accounts
- **Logging** – records all activity and errors to `logs/teneo_node.log`

---

## 🛠️ Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/mejri02/TeneoNode.git
cd TeneoNode
```

### 2️⃣ Install Requirements

Make sure Python 3.8+ is installed, then run:

```bash
pip install -r requirements.txt
```

### 3️⃣ Configure Accounts

If `config.json` doesn't exist, the bot will auto-generate a template on first run. Edit it to add your accounts:

```json
{
  "accounts": [
    {
      "access_token": "YOUR_TOKEN_HERE",
      "label": "Main Account"
    },
    {
      "access_token": "SECOND_TOKEN_HERE",
      "label": "Secondary Account"
    }
  ],
  "ws_url": "wss://secure.ws.teneo.pro/websocket",
  "version": "v0.2"
}
```

- Add as many account objects as needed
- `label` is optional but recommended for easy identification in the dashboard

### 4️⃣ Proxy Setup (Optional)

Create a `proxies.txt` in the project root with one proxy per line:

```text
http://username:password@ip:port
socks5://ip:port
socks5://username:password@ip:port
```

> Proxies are automatically speed-tested on startup. Any proxy with a ping above 1000ms is discarded.

---

## ▶️ Usage

```bash
python bot.py
```

On startup, the bot will prompt you to configure:

- **Use proxies?** – enable/disable proxy usage
- **Proxy per account?** – assign a unique proxy to each account (rotates through the list)
- **Auto-rotate proxies?** – rotate to a new proxy on each reconnect

The bot will then:
1. Validate all account tokens
2. Run a WebSocket connection pre-test
3. Launch all accounts concurrently (with a 2-second stagger)
4. Display the live dashboard

---

## 📊 Dashboard Overview

| Column | Description |
|---|---|
| Status | 🟢 Connected / 🔴 Disconnected / 🔄 Reconnecting |
| Label | Account name from config |
| Today | Points earned today |
| Total | All-time total points |
| Heartbeats | Number of heartbeats received this session |
| Uptime | Time connected this session |
| Pts/Hr | Points per hour rate |

The footer shows individual daily progress bars toward the **7,200 point daily cap**.

---

## 💬 Support

- **GitHub:** `mejri02`
