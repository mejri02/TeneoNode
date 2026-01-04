# TeneoNode

An automated node bot for the Teneo Network, designed for stability and efficiency.

## 🚀 Join Teneo Network

To get started and earn points, sign up using my referral link:

👉 **[Join Teneo Network](https://dashboard.teneo.pro/auth/signup?referralCode=sYkC5)**

---

## ✨ Features

- **Real-time Monitoring** – live status updates (connection, uptime, latency, points)
- **Proxy Support** – HTTP and SOCKS5 proxies
- **Automatic Rotation** – optional proxy rotation on reconnect
- **Random User-Agent** – simulates organic traffic
- **Automatic Reconnection** – reconnects if WebSocket disconnects
- **Logging** – records activity and errors

---

## 🛠️ Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/mejri02/TeneoNode.git
cd TeneoNode
```

### 2️⃣ Install Requirements

Make sure Python is installed, then run:

```bash
pip install -r requirements.txt
```

### 3️⃣ Proxy Setup (Optional)

If you plan to use proxies, create a file named `proxies.txt` in the project root and add your proxies (one per line):

**Examples:**

```text
http://username:password@ip:port
socks5://ip:port
```

### 4️⃣ Edit Configuration File

Open `config.json` and replace the placeholder token:

```json
{
  "access_token": "your_access_token_here",
  "ws_url": "wss://secure.ws.teneo.pro/websocket",
  "version": "v0.2"
}
```

---

## ▶️ Usage

Run the bot:

```bash
python bot.py
```

Follow the on-screen prompts to configure:

- proxy usage
- User-Agent preferences

---

## 💬 Support

- **GitHub:** `mejri02`
