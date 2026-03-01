from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.align import Align
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.text import Text
from rich import box
from datetime import datetime
import websocket
import json
import time
import threading
import os
import logging
import requests
import random
import ssl
from pathlib import Path
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor

console = Console()

class TeneoNode:
    def __init__(self):
        self.setup_logging()
        self.load_config()
        self.prompt_user_preferences()
        self.initialize_variables()
        self.ws_threads = {}
        self.connection_locks = {}
        self.points_locks = {}
        self.account_stats = {}
        self.session = self.setup_api_session()
        self.ua_generator = UserAgent()
        self.debug_mode = True

    def setup_logging(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[logging.FileHandler(log_dir / "teneo_node.log")]
        )

    def setup_api_session(self):
        session = requests.Session()
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def load_config(self):
        try:
            config_path = Path("config.json")
            if not config_path.exists():
                console.print("[red]config.json not found.[/]")
                console.print("[yellow]Creating template config.json...[/]")
                template = {
                    "accounts": [
                        {
                            "access_token": "YOUR_TOKEN_HERE",
                            "label": "Main Account"
                        }
                    ],
                    "ws_url": "wss://secure.ws.teneo.pro/websocket",
                    "version": "v0.2"
                }
                with open(config_path, 'w') as f:
                    json.dump(template, f, indent=2)
                console.print("[green]Template created. Edit config.json with your token[/]")
                os._exit(1)
            
            with config_path.open('r') as f:
                self.config = json.load(f)
            self.accounts = self.config.get('accounts', [])
            if not self.accounts:
                console.print("[red]No accounts found in config.json[/]")
                os._exit(1)
            self.WS_URL = self.config.get('ws_url', 'wss://secure.ws.teneo.pro/websocket')
            self.VERSION = self.config.get('version', 'v0.2')
            
            console.print(f"[green]Loaded {len(self.accounts)} accounts[/]")
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            console.print(f"[red]Error loading config: {e}[/]")
            os._exit(1)

    def prompt_user_preferences(self):
        console.print(Panel("[bold cyan]TeneoNode Multi-Account Bot[/]"))
        
        self.use_proxies = console.input("Use proxies? (y/n): ").lower() == 'y'
        self.proxies = []
        self.proxy_pings = {}
        self.auto_rotate = False
        self.proxy_per_account = False
        
        if self.use_proxies:
            self.proxy_per_account = console.input("Assign different proxy per account? (y/n): ").lower() == 'y'
            proxy_path = Path("proxies.txt")
            if proxy_path.exists():
                with open(proxy_path, 'r') as f:
                    self.proxies = [line.strip() for line in f if line.strip()]
                console.print(f"[green]Loaded {len(self.proxies)} proxies.[/]")
                self.auto_rotate = console.input("Auto-rotate proxies on reconnect? (y/n): ").lower() == 'y'
                if len(self.proxies) > 5:
                    self.test_proxies_concurrent()
            else:
                console.print("[red]proxies.txt not found! Switching to direct connection.[/]")
                self.use_proxies = False

    def test_proxy_ping(self, proxy):
        try:
            start = time.time()
            test_url = "https://api.teneo.pro/api/health"
            response = self.session.get(test_url, proxies={'http': proxy, 'https': proxy}, timeout=5)
            latency = (time.time() - start) * 1000
            return latency
        except:
            return float('inf')

    def test_proxies_concurrent(self):
        console.print("[yellow]Testing proxy speeds...[/]")
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(self.test_proxy_ping, self.proxies))
        
        proxy_pings = list(zip(self.proxies, results))
        proxy_pings.sort(key=lambda x: x[1])
        
        self.proxies = [p for p, ping in proxy_pings if ping < 1000]
        self.proxy_pings = {p: ping for p, ping in proxy_pings if ping < 1000}
        
        console.print(f"[green]Kept {len(self.proxies)} proxies with <1000ms ping[/]")
        if len(proxy_pings) > 0:
            for i, (proxy, ping) in enumerate(proxy_pings[:3]):
                console.print(f"  {i+1}. {proxy[:50]}... - {ping:.0f}ms")

    def get_random_ua(self):
        try: 
            return self.ua_generator.random
        except: 
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def get_proxy_for_account(self, account_index):
        if not self.use_proxies or not self.proxies:
            return None, None, None, None
        
        if self.proxy_per_account:
            proxy = self.proxies[account_index % len(self.proxies)]
        else:
            if self.auto_rotate:
                proxy = random.choice(self.proxies)
            else:
                proxy = self.proxies[0]
        
        p_url = proxy
        p_type = "socks5" if "socks5" in p_url.lower() else "http"
        
        clean = p_url.replace("socks5://", "").replace("http://", "").replace("https://", "")
        
        auth, host_port = None, None
        if "@" in clean:
            auth_str, host_port = clean.split("@")
            auth = tuple(auth_str.split(":"))
        else:
            host_port = clean
        
        try:
            host, port = host_port.split(":")
            return p_type, host, int(port), auth
        except:
            return None, None, None, None

    def initialize_variables(self):
        self.ws_connections = {}
        self.is_connected = {}
        self.current_points = {}
        self.points_today = {}
        self.heartbeats_today = {}
        self.last_heartbeat_time = {}
        self.connection_uptime = {}
        self.script_start_time = datetime.now()
        self.stop_display = False
        self.account_labels = {}
        self.connection_attempts = {}
        self.total_heartbeats_sent = {}
        self.points_per_hour = {}

    def validate_token(self, access_token):
        try:
            response = self.session.get(
                "https://api.teneo.pro/api/users/stats",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]Token valid! Stats: {data.get('points_total', 0)} points[/]")
                return True
            else:
                console.print(f"[red]Token validation failed: {response.status_code}[/]")
                return False
        except Exception as e:
            console.print(f"[red]Token validation error: {e}[/]")
            return False

    def on_message(self, ws, message, account_id):
        try:
            data = json.loads(message)
            current_time = time.time()
            
            if "pointsToday" in data:
                with self.points_locks[account_id]:
                    old_points = self.points_today.get(account_id, 0)
                    self.points_today[account_id] = data.get("pointsToday", 0)
                    self.current_points[account_id] = data.get("pointsTotal", 0)
                    
                    # Calculate heartbeats (75 points each)
                    new_points = self.points_today[account_id] - old_points
                    if new_points > 0:
                        self.total_heartbeats_sent[account_id] = self.total_heartbeats_sent.get(account_id, 0) + 1
                        self.last_heartbeat_time[account_id] = current_time
                    
                    # Calculate points per hour
                    if account_id in self.connection_uptime:
                        uptime_hours = self.connection_uptime[account_id] / 3600
                        if uptime_hours > 0:
                            self.points_per_hour[account_id] = self.current_points[account_id] / uptime_hours
                    
                    if self.debug_mode:
                        heartbeat_num = self.total_heartbeats_sent.get(account_id, 0)
                        console.print(f"[dim]{account_id} - 💓 Heartbeat #{heartbeat_num} | +{new_points} pts | Total: {self.points_today[account_id]} today[/]")
                    
                    if self.points_today[account_id] >= 7200:
                        logging.info(f"Account {account_id} reached max daily points")
        except Exception as e:
            if self.debug_mode:
                console.print(f"[red]Message error: {e}[/]")

    def on_error(self, ws, error, account_id):
        self.is_connected[account_id] = False
        if account_id in self.connection_uptime:
            self.connection_uptime[account_id] = 0
        console.print(f"[red]Account {account_id} WebSocket Error: {error}[/]")
        logging.error(f"Account {account_id} WebSocket Error: {error}")

    def on_open(self, ws, account_id):
        self.is_connected[account_id] = True
        self.connection_attempts[account_id] = 0
        self.connection_uptime[account_id] = 0
        self.last_heartbeat_time[account_id] = time.time()
        console.print(f"[green]✓ Account {account_id} connected successfully![/]")
        logging.info(f"Account {account_id} WebSocket connected")

    def on_close(self, ws, close_status_code, close_msg, account_id):
        self.is_connected[account_id] = False
        if account_id in self.connection_uptime:
            self.connection_uptime[account_id] = 0
        console.print(f"[yellow]Account {account_id} connection closed ({close_status_code})[/]")
        logging.warning(f"Account {account_id} WebSocket connection closed")

    def create_new_connection(self, account_id, access_token, account_index):
        if account_id not in self.connection_attempts:
            self.connection_attempts[account_id] = 0
        
        self.connection_attempts[account_id] += 1
        
        p_type, host, port, auth = self.get_proxy_for_account(account_index)
        
        url = f"{self.WS_URL}?accessToken={access_token}&version={self.VERSION}"
        
        if self.debug_mode:
            console.print(f"[dim]Connecting {account_id} (attempt {self.connection_attempts[account_id]})...[/]")
        
        self.connection_locks[account_id] = threading.Lock()
        self.points_locks[account_id] = threading.Lock()
        
        if host and self.debug_mode:
            console.print(f"[dim]Using proxy: {host}:{port} ({p_type})[/]")
        
        ws = websocket.WebSocketApp(
            url,
            header={
                'User-Agent': self.get_random_ua(),
                'X-Client-Version': self.VERSION,
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            },
            on_open=lambda ws: self.on_open(ws, account_id),
            on_message=lambda ws, msg: self.on_message(ws, msg, account_id),
            on_error=lambda ws, err: self.on_error(ws, err, account_id),
            on_close=lambda ws, code, msg: self.on_close(ws, code, msg, account_id)
        )
        
        self.ws_connections[account_id] = ws
        
        run_args = {
            'skip_utf8_validation': True,
            'ping_interval': 30,
            'ping_timeout': 10,
            'sslopt': {
                'cert_reqs': ssl.CERT_NONE,
                'check_hostname': False
            }
        }
        
        if host:
            run_args.update({
                'proxy_type': p_type,
                'http_proxy_host': host,
                'http_proxy_port': port,
            })
            if auth:
                run_args['http_proxy_auth'] = auth

        ws_thread = threading.Thread(
            target=ws.run_forever,
            kwargs=run_args,
            daemon=True
        )
        self.ws_threads[account_id] = ws_thread
        ws_thread.start()

    def manage_account(self, account_index, account):
        account_id = f"acc_{account_index}"
        access_token = account.get('access_token')
        label = account.get('label', f"Account {account_index+1}")
        
        if not access_token or access_token == "YOUR_TOKEN_HERE":
            logging.error(f"Account {account_index} has no valid access token")
            return
        
        console.print(f"[yellow]Validating token for {label}...[/]")
        if not self.validate_token(access_token):
            console.print(f"[red]Token invalid for {label}. Skipping.[/]")
            return
        
        self.account_labels[account_id] = label
        self.connection_attempts[account_id] = 0
        self.total_heartbeats_sent[account_id] = 0
        
        self.is_connected[account_id] = False
        self.points_today[account_id] = 0
        self.current_points[account_id] = 0
        
        self.create_new_connection(account_id, access_token, account_index)
        
        uptime_thread = threading.Thread(target=self.update_uptime, args=(account_id,), daemon=True)
        uptime_thread.start()
        
        while True:
            time.sleep(10)
            if not self.is_connected.get(account_id, False):
                if self.connection_attempts.get(account_id, 0) < 5:
                    if self.debug_mode:
                        console.print(f"[yellow]Reconnecting {label}...[/]")
                    self.create_new_connection(account_id, access_token, account_index)
                else:
                    if self.connection_attempts.get(account_id, 0) > 10:
                        self.connection_attempts[account_id] = 0

    def update_uptime(self, account_id):
        while True:
            time.sleep(1)
            if self.is_connected.get(account_id, False):
                self.connection_uptime[account_id] = self.connection_uptime.get(account_id, 0) + 1

    def get_status_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="stats", size=6),
            Layout(name="accounts", ratio=2),
            Layout(name="footer", size=4)
        )

        runtime = str(datetime.now() - self.script_start_time).split('.')[0]
        
        total_points = sum(self.current_points.values())
        total_today = sum(self.points_today.values())
        active_accounts = sum(1 for v in self.is_connected.values() if v)
        total_heartbeats = sum(self.total_heartbeats_sent.values())
        
        # Top stats panel
        stats_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="bold white")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="bold white")
        
        stats_table.add_row(
            "📊 Total Points", f"{total_points:,}",
            "📈 Today", f"{total_today:,}"
        )
        stats_table.add_row(
            "💓 Heartbeats", f"{total_heartbeats}",
            "🟢 Active", f"{active_accounts}/{len(self.accounts)}"
        )
        stats_table.add_row(
            "⏱️ Runtime", runtime,
            "⚡ Avg Pts/Hr", f"{int(total_points / (max(1, (time.time() - self.script_start_time.timestamp()) / 3600)))}"
        )
        
        # Accounts table
        accounts_table = Table(title=f"📋 Account Details ({len(self.accounts)})", box=box.ROUNDED, header_style="bold magenta")
        accounts_table.add_column("Status", width=4)
        accounts_table.add_column("Label", style="cyan")
        accounts_table.add_column("Today", justify="right")
        accounts_table.add_column("Total", justify="right")
        accounts_table.add_column("Heartbeats", justify="right")
        accounts_table.add_column("Uptime", justify="right")
        accounts_table.add_column("Pts/Hr", justify="right")
        
        for i, account in enumerate(self.accounts):
            account_id = f"acc_{i}"
            points = self.current_points.get(account_id, 0)
            today = self.points_today.get(account_id, 0)
            heartbeats = self.total_heartbeats_sent.get(account_id, 0)
            uptime = self.connection_uptime.get(account_id, 0)
            uptime_str = f"{uptime//3600}h{(uptime%3600)//60}m" if uptime > 0 else "0m"
            pts_per_hour = int(self.points_per_hour.get(account_id, 0))
            
            status = "🟢" if self.is_connected.get(account_id, False) else "🔴"
            if not self.is_connected.get(account_id, False) and self.connection_attempts.get(account_id, 0) > 0:
                status = "🔄"
            
            accounts_table.add_row(
                status,
                account.get('label', f"Acc{i+1}"),
                f"{today:,}",
                f"{points:,}",
                f"{heartbeats}",
                uptime_str,
                f"{pts_per_hour}"
            )
        
        # Progress bars
        progress_table = Table.grid(padding=(0, 2))
        progress_table.add_column()
        
        for i, account in enumerate(self.accounts):
            account_id = f"acc_{i}"
            today = self.points_today.get(account_id, 0)
            percent = min(100, int((today / 7200) * 100))
            
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            )
            task = progress.add_task(f"{account.get('label', f'Acc{i+1}')}", total=7200, completed=today)
            progress_table.add_row(progress)
        
        layout["header"].update(Panel(Align.center("[bold white]⚡ TENEO NETWORK FARMING BOT ⚡[/]"), border_style="blue"))
        layout["stats"].update(Panel(stats_table, title="📊 Global Statistics", border_style="green"))
        layout["accounts"].update(Panel(accounts_table, border_style="cyan"))
        layout["footer"].update(Panel(progress_table, title="📈 Daily Progress (Max: 7,200 pts)", border_style="yellow"))
        
        return layout

    def display_thread_function(self):
        with Live(self.get_status_layout(), refresh_per_second=1, screen=True) as live:
            while not self.stop_display:
                live.update(self.get_status_layout())
                time.sleep(1)

    def test_connection(self):
        console.print("[yellow]Testing direct WebSocket connection...[/]")
        
        if not self.accounts:
            return
        
        token = self.accounts[0].get('access_token')
        if not token or token == "YOUR_TOKEN_HERE":
            console.print("[red]No valid token to test[/]")
            return
        
        try:
            ws = websocket.create_connection(
                f"{self.WS_URL}?accessToken={token}&version={self.VERSION}",
                header={"User-Agent": self.get_random_ua()},
                timeout=10,
                sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
            )
            console.print("[green]✓ Direct WebSocket connection successful![/]")
            ws.close()
            return True
        except Exception as e:
            console.print(f"[red]✗ Direct WebSocket connection failed: {e}[/]")
            return False

    def start(self):
        console.print(Panel("[bold cyan]Starting Teneo Node Bot[/]"))
        
        if not self.test_connection():
            console.print("[red]WebSocket connection test failed. Check:[/]")
            console.print("  1. Your internet connection")
            console.print("  2. Token is valid")
            console.print("  3. No firewall blocking wss://secure.ws.teneo.pro")
            
            retry = console.input("Continue anyway? (y/n): ").lower() == 'y'
            if not retry:
                return
        
        threading.Thread(target=self.display_thread_function, daemon=True).start()
        
        threads = []
        for i, account in enumerate(self.accounts):
            t = threading.Thread(target=self.manage_account, args=(i, account), daemon=True)
            t.start()
            threads.append(t)
            time.sleep(2)
        
        console.print("[green]✨ All accounts started. Happy farming! ✨[/]")
        
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/]")
            self.stop_display = True
            for ws in self.ws_connections.values():
                try:
                    ws.close()
                except:
                    pass
            console.print("[green]Shutdown complete[/]")

if __name__ == "__main__":
    try:
        node = TeneoNode()
        node.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]Bot stopped by user[/]")
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/]")
        logging.error(f"Fatal error: {e}")
