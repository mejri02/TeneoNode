from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.align import Align
from datetime import datetime
import websocket
import json
import time
import threading
import os
import logging
import requests
import random
from pathlib import Path
from fake_useragent import UserAgent

console = Console()

class TeneoNode:
    def __init__(self):
        self.setup_logging()
        self.load_config()
        self.prompt_user_preferences()
        self.initialize_variables()
        self.ws_thread = None
        self.connection_lock = threading.Lock()
        self.points_lock = threading.Lock()

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

    def load_config(self):
        try:
            config_path = Path("config.json")
            if not config_path.exists():
                console.print("[red]config.json not found.[/]")
                os._exit(1)
            with config_path.open('r') as f:
                self.config = json.load(f)
            self.ACCESS_TOKEN = self.config['access_token']
            self.WS_URL = self.config.get('ws_url', 'wss://secure.ws.teneo.pro/websocket')
            self.VERSION = self.config.get('version', 'v0.2')
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            os._exit(1)

    def prompt_user_preferences(self):
        console.print(Panel("[bold cyan]TeneoNode Configuration[/]"))
        
        self.use_proxies = console.input("Use proxies? (y/n): ").lower() == 'y'
        self.proxies = []
        self.current_proxy = None
        self.auto_rotate = False
        
        if self.use_proxies:
            proxy_path = Path("proxies.txt")
            if proxy_path.exists():
                with open(proxy_path, 'r') as f:
                    self.proxies = [line.strip() for line in f if line.strip()]
                console.print(f"[green]Loaded {len(self.proxies)} proxies.[/]")
                self.auto_rotate = console.input("Auto-rotate proxies on reconnect? (y/n): ").lower() == 'y'
            else:
                console.print("[red]proxies.txt not found! Switching to direct connection.[/]")
                self.use_proxies = False

        self.random_ua = console.input("Use random User-Agent? (y/n): ").lower() == 'y'
        self.ua_generator = UserAgent() if self.random_ua else None

    def get_random_ua(self):
        if self.random_ua:
            try: return self.ua_generator.random
            except: return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        return 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'

    def get_current_proxy_data(self):
        """Parses the proxy string into components needed by websocket-client."""
        if not self.use_proxies or not self.proxies:
            return None, None, None, None

        if not self.current_proxy or self.auto_rotate:
            self.current_proxy = random.choice(self.proxies)

        p_url = self.current_proxy
        p_type = "socks5" if "socks5" in p_url.lower() else "http"
        
        # Strip protocol
        clean = p_url.replace("socks5://", "").replace("http://", "").replace("https://", "")
        
        auth, host_port = None, None
        if "@" in clean:
            auth_str, host_port = clean.split("@")
            auth = tuple(auth_str.split(":")) # (user, pass)
        else:
            host_port = clean
        
        host, port = host_port.split(":")
        return p_type, host, int(port), auth

    def initialize_variables(self):
        self.ws = None
        self.is_connected = False
        self.current_points = 0
        self.points_today = 0
        self.script_start_time = datetime.now()
        self.current_latency = 0
        self.stop_display = False

    def get_status_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )

        runtime = str(datetime.now() - self.script_start_time).split('.')[0]
        
        node_info = (
            f"[bold cyan]Points Today:[/] {self.points_today:,}\n"
            f"[bold cyan]Total Points:[/] {self.current_points:,}\n"
            f"[bold cyan]Heartbeats:[/] {self.points_today//75}/96\n"
            f"[bold cyan]Runtime:[/] {runtime}"
        )

        # Show a truncated proxy for cleaner UI
        px_display = (self.current_proxy[:40] + '...') if self.current_proxy and len(self.current_proxy) > 40 else self.current_proxy

        network_info = (
            f"[bold magenta]Proxy:[/] {px_display if self.use_proxies else 'Direct'}\n"
            f"[bold magenta]Status:[/] {'🟢 Online' if self.is_connected else '🔴 Offline'}"
        )

        layout["header"].update(Panel(Align.center("[bold white]TENEO NETWORK AUTO-BOT[/]"), border_style="blue"))
        layout["main"].split_row(
            Panel(node_info, title="Earnings", border_style="green"),
            Panel(network_info, title="Network Status", border_style="magenta")
        )
        layout["footer"].update(Panel(Align.center(f"Last UI Refresh: {datetime.now().strftime('%H:%M:%S')}"), border_style="white"))
        
        return layout

    def display_thread_function(self):
        with Live(self.get_status_layout(), refresh_per_second=1) as live:
            while not self.stop_display:
                live.update(self.get_status_layout())
                time.sleep(1)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if "pointsToday" in data:
                with self.points_lock:
                    self.points_today = data.get("pointsToday", 0)
                    self.current_points = data.get("pointsTotal", 0)
        except: pass

    def on_error(self, ws, error):
        self.is_connected = False
        logging.error(f"WebSocket Error: {error}")

    def on_open(self, ws):
        self.is_connected = True
        logging.info("WebSocket successfully connected")

    def on_close(self, ws, close_status_code, close_msg):
        self.is_connected = False
        logging.warning("WebSocket connection closed")

    def create_new_connection(self):
        p_type, host, port, auth = self.get_current_proxy_data()
        
        url = f"{self.WS_URL}?accessToken={self.ACCESS_TOKEN}&version={self.VERSION}"
        self.ws = websocket.WebSocketApp(
            url,
            header={'User-Agent': self.get_random_ua()},
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        run_args = {}
        if host:
            run_args = {
                'proxy_type': p_type,
                'http_proxy_host': host,
                'http_proxy_port': port,
                'http_proxy_auth': auth
            }

        self.ws_thread = threading.Thread(
            target=self.ws.run_forever, 
            kwargs=run_args,
            daemon=True
        )
        self.ws_thread.start()

    def start(self):
        threading.Thread(target=self.display_thread_function, daemon=True).start()
        while True:
            if not self.is_connected:
                self.create_new_connection()
            time.sleep(15) # Wait between check/reconnect attempts

if __name__ == "__main__":
    node = TeneoNode()
    node.start()
