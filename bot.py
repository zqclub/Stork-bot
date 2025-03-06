import json
import os
import time
from datetime import datetime, timezone, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import create_urllib3_context
import logging
from typing import Dict, List, Optional
from pycognito import Cognito
from colorama import Fore, Back, Style, init

# 初始化 colorama
init(autoreset=True)

# 配置彩色日志
class ColoredFormatter(logging.Formatter):
    level_colors = {
        logging.DEBUG: Fore.CYAN + Style.DIM,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Back.WHITE
    }

    def format(self, record):
        level_color = self.level_colors.get(record.levelno, Fore.WHITE)
        record.levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"
        record.msg = f"{Fore.WHITE}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter(
    fmt=f'[{Fore.GREEN}%(asctime)s{Style.RESET_ALL}] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(handler)
logging.Formatter.converter = lambda *args: (datetime.now(timezone.utc) + timedelta(hours=8)).timetuple()

# 北京时间偏移 (UTC+8)
BEIJING_OFFSET = timedelta(hours=8)

# 全局配置
CONFIG = {
    "cognito": {
        "region": "ap-northeast-1",
        "client_id": "5msns4n49hmg3dftp2tp1t2iuh",
        "user_pool_id": "ap-northeast-1_M22I44OpC"
    },
    "stork": {
        "base_url": "https://app-api.jp.stork-oracle.network/v1",
        "auth_url": "https://api.jp.stork-oracle.network/auth",
        "interval_seconds": 5,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "origin": "chrome-extension://knnliglhgkmlblppdejchidfihjnockl"
    },
    "threads": {
        "max_workers": 1
    }
}

ACCOUNTS_PATH = 'accounts.txt'
TOKENS_PATH = 'tokens.txt'
PROXIES_PATH = 'proxies.txt'

# 美观化组件
def get_banner_text():
    banner = f"""
{Fore.CYAN}╭────────────────────────────────────────────────────────────╮
{Fore.CYAN}│{Fore.YELLOW}      ███████╗████████╗ ██████╗ ██████╗ ██╗  ██╗      {Fore.CYAN}│
{Fore.CYAN}│{Fore.YELLOW}      ██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗██║ ██╔╝      {Fore.CYAN}│
{Fore.CYAN}│{Fore.YELLOW}      ███████╗   ██║   ██║   ██║██████╔╝█████╔╝       {Fore.CYAN}│
{Fore.CYAN}│{Fore.YELLOW}      ╚════██║   ██║   ██║   ██║██╔══██╗██╔═██╗       {Fore.CYAN}│
{Fore.CYAN}│{Fore.YELLOW}      ███████║   ██║   ╚██████╔╝██║  ██║██║  ██╗      {Fore.CYAN}│
{Fore.CYAN}│{Fore.YELLOW}      ╚══════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝      {Fore.CYAN}│
{Fore.CYAN}├────────────────────────────────────────────────────────────┤
{Fore.BLUE}│           关注X: {Fore.WHITE}https://x.com/qklxsqf{Fore.BLUE} | 获得{Fore.WHITE}更多资讯        │
{Fore.BLUE}│           启动时间: {Fore.WHITE}{(datetime.now(timezone.utc) + BEIJING_OFFSET).strftime('%Y-%m-%d %H:%M:%S')}{Fore.BLUE} │
{Fore.CYAN}╰────────────────────────────────────────────────────────────╯
    """
    return banner

def mask_email(email: str) -> str:
    if '@' not in email:
        return f"{Fore.YELLOW}{email}"
    name, domain = email.split('@')
    if len(name) <= 2:
        return f"{Fore.CYAN}{name[0]}***@{domain}"
    return f"{Fore.CYAN}{name[:4]}****@{domain}"

# 文件操作函数
def load_accounts() -> List[Dict]:
    if not os.path.exists(ACCOUNTS_PATH):
        logger.error(f"{Fore.RED}未找到账户文件 {ACCOUNTS_PATH}")
        logger.info(f"{Fore.YELLOW}示例 accounts.txt 内容：")
        logger.info(f"{Fore.YELLOW}your@email.com:yourpassword")
        return []
    try:
        with open(ACCOUNTS_PATH, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        accounts = []
        for line in lines:
            if ':' not in line:
                logger.warning(f"{Fore.YELLOW}跳过无效账户行: {line}")
                continue
            username, password = line.split(':', 1)
            accounts.append({"username": username, "password": password})
        logger.info(f"{Fore.GREEN}成功加载 {len(accounts)} 个账户")
        return accounts
    except Exception as e:
        logger.error(f"{Fore.RED}加载账户文件失败: {e}")
        return []

def load_tokens() -> Dict:
    if not os.path.exists(TOKENS_PATH):
        logger.warning(f"{Fore.YELLOW}未找到令牌文件 {TOKENS_PATH}，将创建空令牌")
        with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
            f.write("{}")
        return {}
    try:
        with open(TOKENS_PATH, 'r', encoding='utf-8') as f:
            tokens = json.loads(f.read().strip())
        expires_at = tokens.get("expires_at", 0)
        beijing_expires = datetime.fromtimestamp(expires_at, tz=timezone.utc) + BEIJING_OFFSET
        logger.info(f"{Fore.GREEN}加载令牌成功，过期时间: {beijing_expires.strftime('%Y-%m-%d %H:%M:%S')}")
        return tokens
    except Exception as e:
        logger.warning(f"{Fore.YELLOW}加载令牌失败: {e}")
        return {}

def save_tokens(tokens: Dict):
    try:
        with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, ensure_ascii=False)
        beijing_expires = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc) + BEIJING_OFFSET
        logger.info(f"{Fore.GREEN}令牌保存成功，过期时间: {beijing_expires.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error(f"{Fore.RED}保存令牌失败: {e}")

def load_proxies() -> List[str]:
    if not os.path.exists(PROXIES_PATH):
        logger.warning(f"{Fore.YELLOW}未找到代理文件 {PROXIES_PATH}")
        return []
    try:
        with open(PROXIES_PATH, 'r', encoding='utf-8') as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        logger.info(f"{Fore.GREEN}成功加载 {len(proxies)} 个代理")
        return proxies
    except Exception as e:
        logger.error(f"{Fore.RED}加载代理失败: {e}")
        return []

# 代理适配器
class SocksAdapter(HTTPAdapter):
    def __init__(self, proxy_url: str):
        context = create_urllib3_context()
        super().__init__(pool_connections=10, pool_maxsize=10, ssl_context=context)
        self.proxy_url = proxy_url

    def proxy_manager_for(self, *args, **kwargs):
        from urllib3.contrib.socks import SOCKSProxyManager
        return SOCKSProxyManager(self.proxy_url)

# 核心类
class TokenHandler:
    def __init__(self, username: str, password: str, config: Dict):
        self.username = username
        self.password = password
        self.config = config
        self.cognito = Cognito(
            user_pool_id=config["cognito"]["user_pool_id"],
            client_id=config["cognito"]["client_id"],
            user_pool_region=config["cognito"]["region"],
            username=username
        )
        self.tokens = load_tokens()
        self.access_token_value = None
        self.refresh_token_value = None
        self.id_token_value = None
        self._initialize_tokens()

    def _initialize_tokens(self):
        if self.tokens and all(key in self.tokens for key in ["access_token", "refresh_token", "id_token"]):
            if time.time() < self.tokens.get("expires_at", 0):
                self.access_token_value = self.tokens["access_token"]
                self.refresh_token_value = self.tokens["refresh_token"]
                self.id_token_value = self.tokens["id_token"]
                self.cognito.access_token = self.access_token_value
                self.cognito.id_token = self.id_token_value
                logger.info(f"{Fore.GREEN}加载的令牌有效")
                return
        logger.info(f"{Fore.BLUE}令牌无效或过期，开始认证")
        self.authenticate()

    def authenticate(self) -> Dict:
        try:
            logger.info(f"{Fore.BLUE}🔑 认证用户 {mask_email(self.username)}")
            self.cognito.authenticate(password=self.password)
            tokens = {
                "access_token": self.cognito.access_token,
                "refresh_token": self.cognito.refresh_token,
                "id_token": self.cognito.id_token,
                "expires_at": time.time() + 3600
            }
            self.access_token_value = tokens["access_token"]
            self.refresh_token_value = tokens["refresh_token"]
            self.id_token_value = tokens["id_token"]
            save_tokens(tokens)
            self.tokens = tokens
            logger.info(f"{Fore.GREEN}✅ 认证成功")
            return tokens
        except Exception as e:
            logger.error(f"{Fore.RED}❌ 认证失败: {e}")
            raise

    def refresh(self) -> Dict:
        try:
            logger.info(f"{Fore.BLUE}🔄 刷新令牌")
            if not self.refresh_token_value:
                raise ValueError("无刷新令牌")
            response = self.cognito.client.initiate_auth(
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={'REFRESH_TOKEN': self.refresh_token_value},
                ClientId=self.config["cognito"]["client_id"]
            )
            auth_result = response['AuthenticationResult']
            tokens = {
                "access_token": auth_result['AccessToken'],
                "refresh_token": self.refresh_token_value,
                "id_token": auth_result.get('IdToken', self.id_token_value),
                "expires_at": time.time() + 3600
            }
            self.access_token_value = tokens["access_token"]
            self.id_token_value = tokens["id_token"]
            self.cognito.access_token = self.access_token_value
            self.cognito.id_token = self.id_token_value
            save_tokens(tokens)
            self.tokens = tokens
            logger.info(f"{Fore.GREEN}✅ 刷新成功")
            return tokens
        except Exception as e:
            logger.error(f"{Fore.RED}❌ 刷新失败: {e}")
            return self.authenticate()

    def get_valid_token(self) -> str:
        current_time = time.time()
        expires_at = self.tokens.get("expires_at", 0) if self.tokens else 0
        if current_time >= expires_at - 300:  # 提前 5 分钟刷新
            logger.info(f"{Fore.YELLOW}令牌即将过期，刷新中...")
            if self.refresh_token_value:
                self.refresh()
            else:
                self.authenticate()
        return self.access_token_value

class StorkClient:
    def __init__(self, config: Dict, token_handler: TokenHandler, use_proxy: bool, proxies_list: List[str]):
        self.config = config
        self.token_handler = token_handler
        self.use_proxy = use_proxy
        self.proxies_list = proxies_list
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": config["stork"]["user_agent"],
            "Origin": config["stork"]["origin"]
        }

    def get_signed_prices(self) -> List[Dict]:
        token = self.token_handler.get_valid_token()
        session = requests.Session()
        proxy = self.proxies_list[0] if self.use_proxy and self.proxies_list else None
        if proxy:
            if proxy.startswith("socks"):
                session.mount("https://", SocksAdapter(proxy))
            else:
                session.proxies = {"https": proxy}
            logger.info(f"{Fore.BLUE}使用代理 {proxy} 获取价格")
        else:
            logger.info(f"{Fore.BLUE}直连获取价格")
        try:
            response = session.get(
                f"{self.config['stork']['base_url']}/stork_signed_prices",
                headers={**self.headers, "Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()["data"]
            prices = [
                {
                    "asset": key,
                    "msg_hash": value["timestamped_signature"]["msg_hash"],
                    "price": value["price"],
                    "timestamp": value["timestamped_signature"]["timestamp"] / 1000000
                }
                for key, value in data.items()
            ]
            logger.info(f"{Fore.GREEN}✅ 获取 {len(prices)} 条价格数据")
            return prices
        except Exception as e:
            logger.error(f"{Fore.RED}❌ 获取价格失败: {e}")
            raise

    def send_validation(self, msg_hash: str, is_valid: bool, proxy: Optional[str] = None):
        token = self.token_handler.get_valid_token()
        session = requests.Session()
        if self.use_proxy and proxy:
            if proxy.startswith("socks"):
                session.mount("https://", SocksAdapter(proxy))
            else:
                session.proxies = {"https": proxy}
            logger.info(f"{Fore.BLUE}使用代理 {proxy} 提交验证")
        else:
            logger.info(f"{Fore.BLUE}直连提交验证")
        try:
            response = session.post(
                f"{self.config['stork']['base_url']}/stork_signed_prices/validations",
                headers={**self.headers, "Authorization": f"Bearer {token}"},
                json={"msg_hash": msg_hash, "valid": is_valid}
            )
            response.raise_for_status()
            logger.info(f"{Fore.GREEN}✅ 验证提交成功: {'有效' if is_valid else '无效'}")
        except Exception as e:
            logger.error(f"{Fore.RED}❌ 验证提交失败: {e}")
            raise

    def get_user_stats(self) -> Dict:
        token = self.token_handler.get_valid_token()
        session = requests.Session()
        proxy = self.proxies_list[0] if self.use_proxy and self.proxies_list else None
        if proxy:
            if proxy.startswith("socks"):
                session.mount("https://", SocksAdapter(proxy))
            else:
                session.proxies = {"https": proxy}
            logger.info(f"{Fore.BLUE}使用代理 {proxy} 获取统计")
        else:
            logger.info(f"{Fore.BLUE}直连获取统计")
        try:
            response = session.get(
                f"{self.config['stork']['base_url']}/me",
                headers={**self.headers, "Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()["data"]
        except Exception as e:
            logger.error(f"{Fore.RED}❌ 获取统计失败: {e}")
            raise

# 辅助函数
def validate_price(price_data: Dict) -> bool:
    if not all(k in price_data for k in ["msg_hash", "price", "timestamp"]):
        logger.warning(f"{Fore.YELLOW}数据不完整: {price_data.get('asset', '未知')}")
        return False
    if (time.time() - price_data["timestamp"]) / 60 > 60:
        logger.warning(f"{Fore.YELLOW}数据过期: {price_data['asset']}")
        return False
    return True

def worker_task(price_data: Dict, client: StorkClient, proxy: Optional[str]):
    try:
        logger.info(f"{Fore.BLUE}验证资产: {price_data['asset']}")
        is_valid = validate_price(price_data)
        client.send_validation(price_data["msg_hash"], is_valid, proxy)
        return {"success": True, "msg_hash": price_data["msg_hash"]}
    except Exception as e:
        logger.error(f"{Fore.RED}验证资产 {price_data['asset']} 失败: {e}")
        return {"success": False, "msg_hash": price_data["msg_hash"]}

def display_stats(stats: Dict):
    if not stats or "stats" not in stats:
        logger.warning(f"{Fore.YELLOW}⚠️ 无有效统计信息")
        return
    logger.info(f"{Fore.CYAN}╭─────────── {Fore.BLUE}用户统计 {Fore.CYAN}───────────╮")
    logger.info(f"{Fore.CYAN}│{Fore.BLUE} 用户: {mask_email(stats.get('email', '未知'))}")
    logger.info(f"{Fore.CYAN}│{Fore.BLUE} 有效验证: {Fore.GREEN}{stats['stats'].get('stork_signed_prices_valid_count', 0)}")
    logger.info(f"{Fore.CYAN}│{Fore.BLUE} 无效验证: {Fore.RED}{stats['stats'].get('stork_signed_prices_invalid_count', 0)}")
    last_verified = stats['stats'].get('stork_signed_prices_last_verified_at', '从未')
    if last_verified != '从未':
        beijing_time = datetime.strptime(last_verified, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc) + BEIJING_OFFSET
        last_verified = f"{Fore.YELLOW}{beijing_time.strftime('%Y-%m-%d %H:%M:%S')}"
    logger.info(f"{Fore.CYAN}│{Fore.BLUE} 最后验证: {last_verified}")
    logger.info(f"{Fore.CYAN}╰─────────────────────────────────╯")

def log_current_ip(account: Dict, proxies_list: List[str], use_proxy: bool):
    proxy = proxies_list[0] if use_proxy and proxies_list else None
    try:
        session = requests.Session()
        if proxy:
            if proxy.startswith("socks"):
                session.mount("https://", SocksAdapter(proxy))
            else:
                session.proxies = {"https": proxy}
            logger.info(f"{Fore.BLUE}使用代理 {proxy} 获取 IP")
        else:
            logger.info(f"{Fore.BLUE}直连获取 IP")
        response = session.get("https://api.ipify.org?format=json", timeout=10)
        logger.info(f"{Fore.GREEN}账户 {mask_email(account['username'])} 当前 IP: {response.json()['ip']}")
    except Exception as e:
        logger.error(f"{Fore.RED}获取 IP 失败: {e}")

# 主逻辑
def main():
    print(get_banner_text())
    logger.info(f"{Fore.MAGENTA}🚀 系统初始化中...")

    while True:
        use_proxy_input = input(f"{Fore.BLUE}[?] 是否使用代理？(y/n): ").strip().lower()
        if use_proxy_input in ['y', 'n']:
            use_proxy = use_proxy_input == 'y'
            break
        logger.warning(f"{Fore.YELLOW}⚠️ 请输入 'y' 或 'n'")

    accounts_list = load_accounts()
    if not accounts_list:
        logger.error(f"{Fore.RED}无有效账户，程序退出")
        return

    proxies_list = load_proxies() if use_proxy else []
    if use_proxy and not proxies_list:
        logger.warning(f"{Fore.YELLOW}代理列表为空，将直连运行")
        use_proxy = False

    account_index = 0
    max_workers = CONFIG["threads"]["max_workers"]

    while True:
        if account_index >= len(accounts_list):
            account_index = 0
            time.sleep(CONFIG["stork"]["interval_seconds"])
            continue

        account = accounts_list[account_index]
        logger.info(f"{Fore.MAGENTA}处理账户: {mask_email(account['username'])}")
        log_current_ip(account, proxies_list, use_proxy)

        token_handler = TokenHandler(account["username"], account["password"], CONFIG)
        stork_client = StorkClient(CONFIG, token_handler, use_proxy, proxies_list)

        try:
            logger.info(f"{Fore.CYAN}───── 开始验证流程 ─────")
            initial_stats = stork_client.get_user_stats()
            display_stats(initial_stats)
            initial_count = initial_stats['stats'].get('stork_signed_prices_valid_count', 0)

            prices = stork_client.get_signed_prices()
            if not prices:
                logger.info(f"{Fore.YELLOW}无新数据可验证")
                display_stats(stork_client.get_user_stats())
                account_index += 1
                time.sleep(CONFIG["stork"]["interval_seconds"])
                continue

            logger.info(f"{Fore.BLUE}处理 {len(prices)} 条数据，线程数: {max_workers}")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(
                        worker_task,
                        price,
                        stork_client,
                        proxies_list[i % len(proxies_list)] if use_proxy and proxies_list else None
                    )
                    for i, price in enumerate(prices)
                ]
                results = [f.result() for f in futures]
                success_count = sum(1 for r in results if r["success"])
                logger.info(f"{Fore.GREEN}完成 {success_count}/{len(results)} 条验证")

            time.sleep(30)
            final_stats = stork_client.get_user_stats()
            final_count = final_stats['stats'].get('stork_signed_prices_valid_count', 0)
            logger.info(f"{Fore.GREEN}验证前后变化: {initial_count} -> {final_count}")
            display_stats(final_stats)

            account_index += 1
            time.sleep(CONFIG["stork"]["interval_seconds"])
        except Exception as e:
            logger.error(f"{Fore.RED}验证流程出错: {e}")
            time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info(f"{Fore.YELLOW}🛑 用户中断，程序退出")
    except Exception as e:
        logger.error(f"{Fore.RED}💥 未处理异常: {e}")
