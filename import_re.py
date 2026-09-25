import os
import re
import json
import html
import time
import random
import argparse
import webbrowser
import urllib.request
import urllib.parse
import akshare as ak
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta, timezone
from calendar import monthrange
from http.cookiejar import CookieJar
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 强制清空代理环境变量
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

# ==============================================================================
# 北京时间工具（所有网页展示时间统一使用北京时间 UTC+8）
# ==============================================================================
BEIJING_TZ = timezone(timedelta(hours=8))

def now_beijing() -> datetime:
    """返回当前北京时间（带时区）"""
    return datetime.now(BEIJING_TZ)

def ts_to_beijing(ts: float) -> datetime:
    """将 Unix 时间戳转换为北京时间"""
    return datetime.fromtimestamp(ts, BEIJING_TZ)

# 通用请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

# ==============================================================================
# 配置中心：测试环境 / 发布环境 快速切换开关
# ==============================================================================
IS_DEBUG = False  # True: 调试测试模式(几秒完成); False: 正式发布模式(全量抓取)

TEST_FUNDS = [
    "002891",  # 美股主动代表
    "014002",
    "006555",
    "161125",  # 标普被动代表
    "022365",  # A股 CPO 代表
    "025500",  # A股 存储芯片代表
]

PROD_FUNDS = [
    # 美股主动组
    "002891", "014002", "006555", "012922", "012920", "021662", "457001", "539002",
    "018147", "021842", "006373", "018036", "501226", "008254", "008253", "017731",
    "017730", "016665", "016664", "018230", "018229", "021277", "270023", "005698",
    "024239", "501312", "017204", "017654", "017653", "022184", "100055", "017437",
    "017436", "017145", "017144", "016702", "016701", "016823", "164212", "019156",
    "019155", "016668", "501225", "015202", "001668", "000043", "007280", "019449",
    "019454", "019455",
    # 纳指被动组
    "017091", "016055", "160213", "019172", "019441", "018043", "019547", "016532",
    "040046", "161130", "016452", "270042", "019736", "000834", "019524", "015299",
    "539001", "018966",
    # 标普被动组
    "161125", "007721", "017028", "050025", "018064", "096001", "017641", "018738",
    "161128",
    # CPO 组
    "022365", "540010", "002112", "011892", "021528",
    "009645", "011370", "011452", "016371", "001956",
    "016234", "016173", "006616", "018291", "020661",
    "017462", "001438", "008984", "180031", "004320", "027063",
    # 存储芯片组
    "025500", "025209", "018816", "014320",
    # 半导体材料设备组
    "024418", "024975", "020640", "019633", "024424",
    "017811", "013841", "007491", "020629", "017747",
    "026633", "162214", "007343", "018777",
    # 人工智能组
    "024663", "024726", "023286", "023408", "025506",
    "025493", "025653", "005963", "014162", "011840",
    "024412", "024775", "026613", "023551", "024561",
    # 电网设备组
    "025857", "023639", "023675", "019411", "167002",
    "020425", "002164", "017133", "017042", "026681",
    "016387", "025833", "011172", "001665", "018919",
    # 机器人组
    "016531", "018345", "020482", "018125", "007519",
    "014243", "018957", "003835", "014939", "008998",
    "004233", "008182", "017968", "024648"
]

US_ACTIVE_CODES = {
    "002891", "014002", "006555", "012922", "012920", "021662", "457001", "539002",
    "018147", "021842", "006373", "018036", "501226", "008254", "008253", "017731",
    "017730", "016665", "016664", "018230", "018229", "021277", "270023", "005698",
    "024239", "501312", "017204", "017654", "017653", "022184", "100055", "017437",
    "017436", "017145", "017144", "016702", "016701", "016823", "164212", "019156",
    "019155", "016668", "501225", "015202", "001668", "000043", "007280", "019449",
    "019454", "019455"
}

NDX_PASSIVE_CODES = {
    "017091", "016055", "160213", "019172", "019441", "018043", "019547", "016532",
    "040046", "161130", "016452", "270042", "019736", "000834", "019524", "015299",
    "539001", "018966"
}

SPX_PASSIVE_CODES = {
    "161125", "007721", "017028", "050025", "018064", "096001", "017641", "018738",
    "161128"
}

# 分级 C 份额到主代码/A 份额映射（补全新增的美股/标普/行业子份额映射）
MAIN_CODE_MAP = {
    "014002": "006555",
    "012922": "012920",
    "018230": "018229",
    "017731": "017730",
    "016665": "016664",
    "017654": "017653",
    "017145": "017144",
    "016702": "016701",
    "019156": "019155",
    "019454": "019449",
    "019455": "019449",
    "018738": "017641",
    "021662": "457001",
    "018147": "539002",
    "021842": "005698",
}

# 指数历年回报的完整目标清单（用于缓存完整性校验）
ANNUAL_INDEX_TARGETS = ["纳指100", "标普500", "费城半导体指数", "沪深300", "科创50", "恒生科技"]

INDEX_NAMES = {
    "NDX": "纳斯达克100指数",
    "SPX": "标普500指数",
    "SOX": "费城半导体指数",
    "SOXL": "三倍做多半导体ETF-Direxion",
    "XLK": "信息科技行业ETF-SPDR"
}

# 【修改】原 PRECIOUS_METALS_NAMES 扩展为大宗商品（新增布伦特原油、LME铜）
COMMODITY_NAMES = {
    "XAU": "伦敦金 (XAU)",
    "AUM": "沪金主连 (AUM)",
    "XAG": "伦敦银 (XAG)",
    "BRENT": "布伦特原油 (BRENT)",
    "CAD": "LME铜 (CAD)"
}

CRYPTO_NAMES = {
    "BTC": "比特币 (BTC/USDT)",
    "ETH": "以太坊 (ETH/USDT)",
    "SOL": "索拉纳 (SOL/USDT)",
    "BNB": "币安币 (BNB/USDT)"
}

SINA_US_INDEX_MAP = {
    "NDX":  ".ndx",
    "SPX":  ".inx",
    "SOX":  ".sox",
    "SOXL": "soxl",
    "XLK":  "xlk",
}

CACHE_DIR = "cache"
HOLDINGS_CACHE_DIR = os.path.join(CACHE_DIR, "holdings")
NAV_CACHE_DIR = os.path.join(CACHE_DIR, "nav")
HOLDER_CACHE_DIR = os.path.join(CACHE_DIR, "holder")
COUNTRY_CACHE_DIR = os.path.join(CACHE_DIR, "country")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(HOLDINGS_CACHE_DIR, exist_ok=True)
os.makedirs(NAV_CACHE_DIR, exist_ok=True)
os.makedirs(HOLDER_CACHE_DIR, exist_ok=True)
os.makedirs(COUNTRY_CACHE_DIR, exist_ok=True)

_THREAD_LOCAL = threading.local()

# ================= requests.Session 包装器：复用连接，兼容 urllib 风格 =================
class _RespWrapper:
    """把 requests.Response 包装成 urllib 风格的响应对象。"""
    def __init__(self, resp):
        self._r = resp
    def read(self, amt=None):
        return self._r.content if amt is None else self._r.raw.read(amt)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def __getattr__(self, name):
        return getattr(self._r, name)


class RequestsOpener:
    """urllib opener 的 requests 版替代品，复用连接池，大幅降低 TLS 握手开销。"""
    def __init__(self):
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,
            pool_block=False,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        # 强制不使用环境代理
        self.session.trust_env = False

    def open(self, req, timeout=5, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else req
        headers = dict(req.headers) if hasattr(req, "headers") else {}
        r = self.session.get(url, headers=headers, timeout=timeout, stream=False)
        return _RespWrapper(r)


def get_thread_opener():
    if not hasattr(_THREAD_LOCAL, "opener"):
        _THREAD_LOCAL.opener = get_direct_opener()
    return _THREAD_LOCAL.opener

def get_direct_opener():
    return RequestsOpener()
# =======================================================================================

# ==============================================================================
# 蛋卷指数估值获取模块 (融合 Guchacha 兜底引擎)
# ==============================================================================
TARGET_INDICES = ["纳指100", "标普500", "沪深300", "科创50", "恒生科技"]

NAME_MAP = {
    "纳指100": ["纳斯达克100", "纳斯达克", "纳指100"],
    "标普500": ["标普500", "S&P500", "S&P 500"],
    "沪深300": ["沪深300"],
    "科创50": ["科创50"],
    "恒生科技": ["恒生科技", "恒生科技指数"]
}

TICKER_MAP = {
    "纳指100": "NDX",
    "标普500": "SPX",
    "沪深300": "000300",
    "科创50": "000688",
    "恒生科技": "HSTECH"
}

def fetch_index_valuations(opener):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://danjuanfunds.com/djapi/v3/filter/fund"
    }

    try:
        init_req = urllib.request.Request("https://xueqiu.com", headers=headers)
        opener.open(init_req, timeout=5)
    except Exception:
        pass

    api_url = "https://danjuanfunds.com/djapi/index_eva/dj"
    req = urllib.request.Request(api_url, headers=headers)
    items = []
    try:
        with opener.open(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("result_code") == 0:
                items = data.get("data", {}).get("items", [])
    except Exception:
        pass

    eva_dict = {}
    for item in items:
        eva_dict[item.get("name", "").strip()] = item

    guchacha_html = ""
    try:
        req_g = urllib.request.Request("https://guchacha.com/index-valuation", headers={"User-Agent": headers["User-Agent"]})
        with opener.open(req_g, timeout=5) as resp:
            guchacha_html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        pass

    results = []
    for target in TARGET_INDICES:
        matched = None
        aliases = NAME_MAP.get(target, [target])
        
        for alias in aliases:
            for k, v in eva_dict.items():
                if alias in k:
                    matched = v
                    break
            if matched:
                break

        if not matched and guchacha_html:
            for alias in aliases:
                for row in re.findall(r'<tr[^>]*>.*?</tr>', guchacha_html, re.S):
                    if alias in row:
                        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                        clean_tds = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                        
                        pe_val = None
                        pct_val = None
                        
                        for t in clean_tds:
                            if '%' in t:
                                if pct_val is None:
                                    try:
                                        pct_val = float(t.replace('%', '')) / 100.0
                                    except ValueError:
                                        pass
                            else:
                                if pe_val is None:
                                    try:
                                        pe_val = float(t)
                                    except ValueError:
                                        pass
                                        
                        if pe_val is not None and pct_val is not None:
                            matched = {
                                'pe': pe_val,
                                'pe_percentile': pct_val
                            }
                            break
                if matched: break

        ticker = TICKER_MAP.get(target, "")

        if matched:
            pe = matched.get('pe')
            pct = matched.get("pe_percentile")
            pe_val = f"{pe:.2f}" if pe else "--"
            pct_val = f"{pct * 100:.2f}%" if pct is not None else "--"
            pct_raw = pct * 100 if pct is not None else 0
            
            if pct is None:
                status, color = "⚪ 暂无数据", "#70757a"
            else:
                p = pct * 100
                if p <= 20: status, color = "🟢 极度低估", "#188038"
                elif p <= 40: status, color = "🌱 低估", "#34a853"
                elif p <= 60: status, color = "🟡 适中", "#fbbc04"
                elif p <= 80: status, color = "🟠 偏高", "#e67e22"
                else: status, color = "🔴 高估", "#d93025"
                
            results.append({
                "name": target, "ticker": ticker, "pe": pe_val, "pct": pct_val, "pct_raw": pct_raw, "status": status, "color": color
            })
        else:
            results.append({
                "name": target, "ticker": ticker, "pe": "--", "pct": "--", "pct_raw": 0, "status": "⚪ 暂无数据", "color": "#70757a"
            })
            
    return results

def fetch_sina_us_kline(symbol_code, start_date_str="2025-01-01"):
    """通过新浪美股日 K 线接口抓取历史数据（源自 get_meiguzhishu.py）。

    返回格式：[{'date': 'YYYY-MM-DD', 'nav': float(收盘价)}, ...]
    """
    callback_name = "US_KLINE_CB"
    url = (
        f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/{callback_name}"
        f"/US_MinKService.getDailyK?symbol={urllib.parse.quote(symbol_code)}"
    )

    headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Referer": "https://finance.sina.com.cn/",
        "Accept": "*/*"
    }
    req = urllib.request.Request(url, headers=headers)
    records = []

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'\((\[.*\])\)', content)
            if not match:
                return records

            raw_list = json.loads(match.group(1))
            for item in raw_list:
                d_str = item.get("d")
                if d_str and d_str >= start_date_str:
                    try:
                        nav = float(item.get("c", 0.0))
                        if nav > 0:
                            records.append({"date": d_str, "nav": nav})
                    except (ValueError, TypeError):
                        continue
    except Exception:
        pass

    records.sort(key=lambda x: x["date"])
    return records

# ==============================================================================
# 【保留】2000年后主要指数年度收益率及收盘点位获取模块（仅数据抓取，不再用于页面展示）
# ==============================================================================
def fetch_index_annual_data():
    """获取 2000 年以来主要指数年度收益率和年末收盘点位。

    数据源方案（与 zhishuniandushouyi.py 保持一致）：
    - 纳指100 / 标普500：historyofmarket.com JSON API -> 新浪美股兜底
    - 沪深300 / 科创50：搜狐财经历史行情 API
    - 恒生科技：腾讯财经港股 K 线 -> 东方财富 -> 天天基金 513180 净值

    缓存策略：
    - 缓存文件：cache/index_annual.json
    - 存在即直接读取返回，不再发起任何网络请求
    - 需刷新时手动删除该文件后重新运行
    """
    # ===== 1. 优先读取本地缓存（带完整性校验） =====
    cache_file = os.path.join(CACHE_DIR, "index_annual.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)

            if isinstance(cached, dict) and cached:
                cached_keys = set(cached.keys())
                expected_keys = set(ANNUAL_INDEX_TARGETS)
                missing = expected_keys - cached_keys

                if not missing:
                    print(f"📅 检测到本地缓存 {cache_file}，直接使用（共 {len(cached)} 个指数）")
                    print(f"📊 指数年度数据最终获取成功: {len(cached)}/{len(ANNUAL_INDEX_TARGETS)} （来源：本地缓存）")
                    return cached
                else:
                    print(f"📅 缓存 {cache_file} 缺少以下指数，将重新抓取: {sorted(missing)}")
            else:
                print(f"📅 缓存文件 {cache_file} 内容为空或格式不正确，将重新抓取...")
        except Exception as e:
            print(f"📅 读取缓存 {cache_file} 失败: {e}，将重新抓取...")

    print("📅 正在获取指数年度数据 (2000年至今)...")
    result = {}

    # 创建一个无代理的 opener
    _opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ---------- 数据获取函数（从 zhishuniandushouyi.py 移植） ----------
    def _fetch_historyofmarket_robust(url):
        records = []
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        try:
            with _opener.open(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
                raw = json.loads(content)

            raw_list = []
            if isinstance(raw, list):
                raw_list = raw
            elif isinstance(raw, dict):
                for k in ["points", "data", "history", "prices", "values", "series"]:
                    if k in raw and isinstance(raw[k], list):
                        raw_list = raw[k]
                        break

            for item in raw_list:
                if isinstance(item, dict):
                    d = item.get("date") or item.get("d") or item.get("time") or item.get("x")
                    c = item.get("close") or item.get("c") or item.get("val") or item.get("y") or item.get("value")
                    if d and c is not None:
                        records.append({"date": str(d)[:10], "close": float(c)})
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    d_val, c_val = item[0], item[1]
                    if isinstance(d_val, (int, float)) and d_val > 100000000:
                        d_str = datetime.fromtimestamp(d_val / 1000 if d_val > 1e11 else d_val).strftime("%Y-%m-%d")
                    else:
                        d_str = str(d_val)[:10]
                    records.append({"date": d_str, "close": float(c_val)})
        except Exception:
            pass
        records.sort(key=lambda x: x["date"])
        return records

    def _fetch_sina_us(symbol):
        url = f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/IO.XSRF.K/US_MinKService.getDailyK?symbol={symbol}&_={int(time.time()*1000)}"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        records = []
        try:
            with _opener.open(req, timeout=10) as resp:
                text = resp.read().decode("gbk", errors="ignore")
                l_idx, r_idx = text.find("("), text.rfind(")")
                if l_idx != -1 and r_idx != -1:
                    data = json.loads(text[l_idx + 1:r_idx])
                    for item in data:
                        records.append({
                            "date": item["d"],
                            "open": float(item["o"]),
                            "close": float(item["c"])
                        })
        except Exception:
            pass
        records.sort(key=lambda x: x["date"])
        return records

    def _fetch_sohu_index(zs_code, start_date="19991201"):
        end_date = datetime.now().strftime("%Y%m%d")
        url = f"https://q.stock.sohu.com/hisHq?code={zs_code}&start={start_date}&end={end_date}&stat=1&order=D&period=d"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://q.stock.sohu.com/"})
        records = []
        try:
            with _opener.open(req, timeout=12) as resp:
                content = resp.read().decode("gbk", errors="ignore")
                data = json.loads(content)
                if isinstance(data, list) and len(data) > 0:
                    hq = data[0].get("hq", [])
                    for bar in hq:
                        if len(bar) >= 3:
                            records.append({
                                "date": bar[0],
                                "open": float(bar[1]),
                                "close": float(bar[2])
                            })
        except Exception:
            pass
        records.sort(key=lambda x: x["date"])
        return records

    def _fetch_hstech_final():
        records = []
        # 方案 A: 腾讯财经港股日 K 线
        try:
            url_tx = "https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param=hkHSTECH,day,,,2000,qfq"
            req_tx = urllib.request.Request(url_tx, headers={**DEFAULT_HEADERS, "Referer": "https://gu.qq.com/"})
            with _opener.open(req_tx, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                data_node = res.get("data", {}).get("hkHSTECH", {})
                kline_list = data_node.get("day") or data_node.get("qfqday", [])
                for k in kline_list:
                    if len(k) >= 3:
                        records.append({"date": k[0], "open": float(k[1]), "close": float(k[2])})
            if records:
                records.sort(key=lambda x: x["date"])
                return records
        except Exception:
            pass

        # 方案 B: 东方财富移动端行情接口
        try:
            url_em = "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=100.HSTECH&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53&klt=101&fqt=1&end=20500101&lmt=2000"
            req_em = urllib.request.Request(url_em, headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
                "Referer": "https://quote.eastmoney.com/"
            })
            with _opener.open(req_em, timeout=8) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                lines = raw.get("data", {}).get("klines", [])
                for line in lines:
                    parts = line.split(",")
                    records.append({"date": parts[0], "open": float(parts[1]), "close": float(parts[2])})
            if records:
                records.sort(key=lambda x: x["date"])
                return records
        except Exception:
            pass

        # 方案 C: 天天基金 513180 历史净值
        try:
            url_fund = "https://api.fund.eastmoney.com/f10/lsjz?fundCode=513180&pageIndex=1&pageSize=2000&startDate=2020-01-01&endDate=2030-01-01"
            headers_fund = {
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
                "Referer": "https://fundf10.eastmoney.com/jjjz_513180.html"
            }
            req_fund = urllib.request.Request(url_fund, headers=headers_fund)
            with _opener.open(req_fund, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                lsjz = data.get("Data", {}).get("LSJZList", [])
                for item in lsjz:
                    nav = item.get("LJJZ") or item.get("DWJZ")
                    if nav:
                        records.append({"date": item["FSRQ"], "open": float(nav), "close": float(nav)})
            if records:
                records.sort(key=lambda x: x["date"])
                return records
        except Exception:
            pass

        return records

    def _fetch_sox_annual_returns():
        """从 historyofmarket.com 获取费城半导体指数(SOX)历年回报。

        该接口直接返回年度回报率（百分比），无需二次计算。
        返回格式：[{'year': int, 'close': None, 'pct': float}, ...]
        """
        url = "https://historyofmarket.com/api/semi/annual-returns.json"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        try:
            with _opener.open(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            series = data.get("series", [])
            yearly_data = []
            for item in series:
                year = item.get("year")
                pct = item.get("value")
                if year and pct is not None:
                    yearly_data.append({
                        "year": int(year),
                        "close": None,          # 接口未提供年末收盘点位
                        "pct": round(float(pct), 2)
                    })
            yearly_data.sort(key=lambda x: x["year"])
            return yearly_data
        except Exception:
            return []

    def _calculate_annual_metrics(records, start_year=2000):
        """计算年度收益率与年末收盘点位"""
        if not records:
            return []

        from collections import defaultdict
        year_map = defaultdict(list)
        for r in records:
            yr = r["date"].split("-")[0]
            try:
                if int(yr) >= (start_year - 1):
                    year_map[yr].append(r)
            except ValueError:
                continue

        all_years = sorted(year_map.keys())
        results = []
        prev_year_close = None

        for yr in all_years:
            yr_bars = year_map[yr]
            first_bar = yr_bars[0]
            last_bar = yr_bars[-1]
            end_point = last_bar["close"]

            if int(yr) >= start_year:
                base_point = prev_year_close if prev_year_close is not None else first_bar.get("open", first_bar["close"])
                annual_return = ((end_point - base_point) / base_point) * 100.0 if base_point > 0 else 0.0

                results.append({
                    "year": yr,
                    "end_date": last_bar["date"],
                    "end_point": end_point,
                    "annual_return": annual_return,
                    "is_launch_year": (prev_year_close is None)
                })

            prev_year_close = end_point

        return results

    # ---------- 配置目标指数 ----------
    targets = [
        {
            "name": "纳指100", "ticker": "NDX",
            "fetcher": lambda: _fetch_historyofmarket_robust("https://historyofmarket.com/api/nasdaq/composite.json") or _fetch_sina_us(".NDX")
        },
        {
            "name": "标普500", "ticker": "SPX",
            "fetcher": lambda: _fetch_historyofmarket_robust("https://historyofmarket.com/api/sp500/century.json") or _fetch_sina_us(".INX")
        },
        {
            "name": "费城半导体指数", "ticker": "SOX",
            "fetcher": lambda: _fetch_sox_annual_returns(),
            "precomputed": True,          # 标记：返回值已是 yearly_data，无需再计算
        },
        {
            "name": "沪深300", "ticker": "000300",
            "fetcher": lambda: _fetch_sohu_index("zs_000300")
        },
        {
            "name": "科创50", "ticker": "000688",
            "fetcher": lambda: _fetch_sohu_index("zs_000688")
        },
        {
            "name": "恒生科技", "ticker": "HSTECH",
            "fetcher": lambda: _fetch_hstech_final()
        }
    ]

    # ---------- 并行获取并计算年度数据 ----------
    def _fetch_one_target(item):
        name = item["name"]
        try:
            records = item["fetcher"]()
            if not records:
                return name, None
            if item.get("precomputed"):
                yearly_data = records
            else:
                stats = _calculate_annual_metrics(records, start_year=2000)
                if not stats:
                    return name, None
                yearly_data = [
                    {"year": int(row["year"]),
                     "close": round(row["end_point"], 2),
                     "pct":   round(row["annual_return"], 2)}
                    for row in stats
                ]
            if not yearly_data:
                return name, None
            return name, {"ticker": item["ticker"], "data": yearly_data}
        except Exception as e:
            print(f"    ❌ {name} 异常: {e}")
            return name, None

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_fetch_one_target, item) for item in targets]
        for fut in as_completed(futures):
            name, payload = fut.result()
            if payload:
                result[name] = payload
                print(f"    ✅ {name}: {len(payload['data'])} 个年度")

    print(f"📊 指数年度数据最终获取成功: {len(result)}/{len(ANNUAL_INDEX_TARGETS)}")

    # ===== 2. 抓取成功后写入本地缓存 =====
    if result:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"💾 已写入本地缓存: {cache_file}")
        except Exception as e:
            print(f"⚠️ 写入缓存失败: {e}")

    return result

# ==============================================================================
# 多源宏观指标获取模块
# ==============================================================================
def fetch_from_yahoo_finance(opener, symbol: str, timeout: int = 4) -> float:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with opener.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        result = data.get("chart", {}).get("result", [{}])[0]
        price = result.get("meta", {}).get("regularMarketPrice")
        if price is None:
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            valid_closes = [c for c in closes if c is not None]
            if valid_closes:
                price = valid_closes[-1]
        if price is not None:
            return round(float(price), 2)
    return 0.0

def fetch_from_cboe_quote(opener, symbol: str, timeout: int = 5) -> float:
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/quotes/{symbol}.json"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with opener.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        quote_data = data.get("data", {})
        price = quote_data.get("last_trade_price") or quote_data.get("current_price") or quote_data.get("close")
        if price is not None:
            return round(float(price), 2)
    return 0.0

def get_vix(opener) -> tuple[float, str, str]:
    try:
        val = fetch_from_yahoo_finance(opener, "^VIX")
        if val > 0:
            return val, "Yahoo Finance (^VIX)", "https://finance.yahoo.com/quote/%5EVIX/"
    except Exception: pass

    try:
        val = fetch_from_cboe_quote(opener, "_VIX")
        if val > 0:
            return val, "CBOE 官方 (_VIX)", "https://www.cboe.com/us/indices/dashboard/vix/"
    except Exception: pass

    try:
        url = "https://hq.sinajs.cn/list=gb_$vix"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                if len(parts) > 1 and float(parts[1]) > 0:
                    return round(float(parts[1]), 2), "新浪财经 (gb_$vix)", "https://stock.finance.sina.com.cn/usstock/quotes/$VIX.html"
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/indices/volatility-s-p-500"

def get_cnn_fear_greed(opener) -> tuple[float, str, str, str]:
    """获取 CNN 恐慌贪婪指数：仅从 CNN 官方获取"""
    cnn_page_url = "https://edition.cnn.com/markets/fear-and-greed"
    cls_map = {
        "extreme fear": "极度恐惧", "fear": "恐惧",
        "neutral": "中性观望", "greed": "贪婪", "extreme greed": "极度贪婪"
    }

    api_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers_api = {
        **DEFAULT_HEADERS,
        "Referer": cnn_page_url,
        "Origin": "https://edition.cnn.com",
        "Accept": "application/json, text/plain, */*"
    }
    try:
        req = urllib.request.Request(api_url, headers=headers_api)
        with opener.open(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            fg = data.get("fear_and_greed", {})
            score = fg.get("score")
            raw_cls = str(fg.get("rating", "neutral")).lower().strip()
            if score is not None:
                rating = cls_map.get(raw_cls, raw_cls.capitalize())
                return (
                    round(float(score), 1),
                    rating,
                    "CNN 官方",
                    cnn_page_url
                )
    except Exception:
        pass

    headers_web = {
        **DEFAULT_HEADERS,
        "Referer": "https://edition.cnn.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    try:
        req_web = urllib.request.Request(cnn_page_url, headers=headers_web)
        with opener.open(req_web, timeout=5) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        score_match = re.search(r'"score"\s*:\s*([0-9]+(?:\.[0-9]+)?)', html_text)
        rating_match = re.search(r'"rating"\s*:\s*"([^"]+)"', html_text)

        if score_match:
            score = round(float(score_match.group(1)), 1)
            raw_cls = rating_match.group(1).lower().strip() if rating_match else "neutral"
            rating = cls_map.get(raw_cls, raw_cls.capitalize())
            return (
                score,
                rating,
                "CNN 官方",
                cnn_page_url
            )
    except Exception:
        pass

    return (
        0.0,
        "暂无数据",
        "获取失败",
        cnn_page_url
    )

def get_usd_cny(opener) -> tuple[float, str, str]:
    try:
        url = "https://hq.sinajs.cn/list=fx_susdcny"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=3) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                for idx in [1, 8]:
                    if len(parts) > idx and float(parts[idx]) > 0:
                        return round(float(parts[idx]), 4), "新浪外汇 (实时)", "https://finance.sina.com.cn/money/forex/hq/USDCNY.shtml"
    except Exception: pass

    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with opener.open(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rate = data.get("rates", {}).get("CNY")
            if rate is not None and float(rate) > 0:
                return round(float(rate), 4), "Open Exchange API", "https://open.er-api.com/"
    except Exception: pass

    try:
        val = fetch_from_yahoo_finance(opener, "USDCNY=X")
        if val > 0:
            return round(val, 4), "Yahoo Finance (USDCNY=X)", "https://finance.yahoo.com/quote/USDCNY=X/"
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/currencies/usd-cny"

def get_vxn(opener) -> tuple[float, str, str]:
    try:
        val = fetch_from_yahoo_finance(opener, "^VXN")
        if val > 0:
            return val, "Yahoo Finance (^VXN)", "https://finance.yahoo.com/quote/%5EVXN/"
    except Exception: pass

    try:
        val = fetch_from_cboe_quote(opener, "_VXN")
        if val > 0:
            return val, "CBOE 官方 (_VXN)", "https://www.cboe.com/us/indices/dashboard/vxn/"
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/indices/cboe-nasdaq-100-voltility"

def get_skew(opener) -> tuple[float, str, str]:
    try:
        val = fetch_from_yahoo_finance(opener, "^SKEW")
        if val > 0:
            return val, "Yahoo Finance (^SKEW)", "https://finance.yahoo.com/quote/SKEW/"
    except Exception: pass

    try:
        val = fetch_from_cboe_quote(opener, "_SKEW")
        if val > 0:
            return val, "CBOE 官方 (_SKEW)", "https://www.cboe.com/us/indices/dashboard/SKEW/"
    except Exception: pass
    return 0.0, "获取失败", "https://sc.macromicro.me/series/4407/cboe-skew"

def get_brent_oil(opener) -> tuple[float, str, str]:
    """获取布伦特原油连续价格"""
    try:
        val = fetch_from_yahoo_finance(opener, "BZ=F")
        if val > 0:
            return val, "Yahoo Finance (BZ=F)", "https://finance.yahoo.com/quote/BZ%3DF/"
    except Exception: pass

    try:
        url = "https://hq.sinajs.cn/list=hf_OIL"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                if len(parts) > 0 and float(parts[0]) > 0:
                    return round(float(parts[0]), 2), "新浪期货 (hf_OIL)", "https://finance.sina.com.cn/futures/quotes/OIL.shtml"
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/commodities/brent-oil"

# ==============================================================================
# 大宗商品相关指标获取模块 (伦敦金 / 沪金主连 / 伦敦银 / LME铜)
# ==============================================================================
def get_gold_london(opener) -> tuple[float, str, str]:
    """获取伦敦金 (XAU/USD 现货) 价格"""
    try:
        val = fetch_from_yahoo_finance(opener, "GC=F")
        if val > 0:
            return val, "Yahoo Finance (GC=F)", "https://finance.yahoo.com/quote/GC%3DF/"
    except Exception: pass

    try:
        url = "https://hq.sinajs.cn/list=hf_XAU"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                if len(parts) > 0:
                    try:
                        v = float(parts[0])
                        if v > 0:
                            return round(v, 2), "新浪财经 (hf_XAU)", "https://finance.sina.com.cn/money/forex/hq/XAU.shtml"
                    except ValueError:
                        pass
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/currencies/xau-usd"


def get_gold_shfe(opener) -> tuple[float, str, str]:
    """获取沪金主连 (AU0) 价格"""
    try:
        df = ak.futures_main_sina(symbol="AU0")
        if df is not None and not df.empty:
            close_col = "收盘价" if "收盘价" in df.columns else ("close" if "close" in df.columns else df.columns[-1])
            try:
                v = float(df.iloc[-1][close_col])
                if v > 0:
                    return round(v, 2), "AkShare (futures_main_sina AU0)", "https://finance.sina.com.cn/futures/quotes/AU0.shtml"
            except Exception:
                pass
    except Exception:
        pass

    try:
        url = "https://hq.sinajs.cn/list=nf_AU0"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                for idx in [8, 7, 6, 5]:
                    if len(parts) > idx:
                        try:
                            v = float(parts[idx])
                            if v > 0:
                                return round(v, 2), "新浪期货 (nf_AU0)", "https://finance.sina.com.cn/futures/quotes/AU0.shtml"
                        except ValueError:
                            pass
    except Exception: pass
    return 0.0, "获取失败", "https://finance.sina.com.cn/futures/quotes/AU0.shtml"


def get_silver_london(opener) -> tuple[float, str, str]:
    """获取伦敦银 (XAG/USD 现货) 价格"""
    try:
        val = fetch_from_yahoo_finance(opener, "SI=F")
        if val > 0:
            return val, "Yahoo Finance (SI=F)", "https://finance.yahoo.com/quote/SI%3DF/"
    except Exception: pass

    try:
        url = "https://hq.sinajs.cn/list=hf_XAG"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                if len(parts) > 0:
                    try:
                        v = float(parts[0])
                        if v > 0:
                            return round(v, 3), "新浪财经 (hf_XAG)", "https://finance.sina.com.cn/money/forex/hq/XAG.shtml"
                    except ValueError:
                        pass
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/currencies/xag-usd"


def get_copper_lme(opener) -> tuple[float, str, str]:
    """获取 LME铜 (CAD) 三个月期铜价格"""
    try:
        url = "https://hq.sinajs.cn/list=hf_CAD"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                if len(parts) > 0:
                    try:
                        v = float(parts[0])
                        if v > 0:
                            return round(v, 2), "新浪财经 (hf_CAD)", "https://finance.sina.com.cn/futures/quotes/CAD.shtml"
                    except ValueError:
                        pass
    except Exception: pass

    try:
        val = fetch_from_yahoo_finance(opener, "HG=F")
        if val > 0:
            return val, "Yahoo Finance (HG=F)", "https://finance.yahoo.com/quote/HG%3DF/"
    except Exception: pass
    return 0.0, "获取失败", "https://cn.investing.com/commodities/copper"

def get_btc_price(opener) -> tuple[float, str, str]:
    """获取比特币最新现货价格（4 个源并行竞速，谁先返回用谁）。"""
    sources = [
        (
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            {**DEFAULT_HEADERS, "Accept": "application/json"},
            5,
            lambda j: (float(j.get("bitcoin", {}).get("usd", 0)),
                       "CoinGecko (BTC/USD)", "https://www.coingecko.com/zh/coins/bitcoin"),
        ),
        (
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            DEFAULT_HEADERS,
            5,
            lambda j: (float(j.get("data", {}).get("amount", 0)),
                       "Coinbase (BTC/USD)", "https://www.coinbase.com/price/bitcoin"),
        ),
        (
            "https://bian.4url.cn/api/v3/ticker/price?symbol=BTCUSDT",
            {**DEFAULT_HEADERS, "Accept": "application/json"},
            4,
            lambda j: (float(j.get("price", 0)),
                       "Binance镜像 (BTC/USDT)", "https://www.binance.com/zh-CN/trade/BTC_USDT"),
        ),
        (
            "https://okx.4url.cn/api/v5/market/ticker?instId=BTC-USDT",
            DEFAULT_HEADERS,
            4,
            lambda j: (float((j.get("data") or [{}])[0].get("last", 0)),
                       "OKX镜像 (BTC/USDT)", "https://www.okx.com/zh-hans/trade-spot/btc-usdt"),
        ),
    ]

    def _try(url, headers, timeout, parser):
        try:
            req = urllib.request.Request(url, headers=headers)
            with get_thread_opener().open(req, timeout=timeout) as resp:
                j = json.loads(resp.read().decode("utf-8"))
                v, src, u = parser(j)
                if v > 0:
                    return round(v, 2), src, u
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(_try, u, h, t, p) for u, h, t, p in sources]
        for f in as_completed(futs, timeout=6):
            r = f.result()
            if r:
                # 取消其余任务
                for x in futs:
                    x.cancel()
                return r

    return 0.0, "获取失败", "https://www.tradingview.com/symbols/BTCUSD/"

def fetch_home_market_metrics(opener):
    """并行抓取所有宏观指标（11 个任务并发），总耗时 ≈ 最慢的单个指标。"""
    now_str = now_beijing().strftime("%Y-%m-%d %H:%M:%S")

    # ============ 并行抓取所有宏观指标 ============
    # 每个任务独立线程内创建自己的 opener（requests.Session 不是线程安全的）
    indicator_specs = [
        ("fng",           get_cnn_fear_greed,  (0.0, "暂无数据", "获取失败", "#")),
        ("vix",           get_vix,             (0.0, "获取失败", "#")),
        ("usdcny",        get_usd_cny,         (0.0, "获取失败", "#")),
        ("vxn",           get_vxn,             (0.0, "获取失败", "#")),
        ("skew",          get_skew,            (0.0, "获取失败", "#")),
        ("brent",         get_brent_oil,       (0.0, "获取失败", "#")),
        ("gold_london",   get_gold_london,     (0.0, "获取失败", "#")),
        ("gold_shfe",     get_gold_shfe,       (0.0, "获取失败", "#")),
        ("silver_london", get_silver_london,   (0.0, "获取失败", "#")),
        ("copper_lme",    get_copper_lme,      (0.0, "获取失败", "#")),
        ("btc",           get_btc_price,       (0.0, "获取失败", "#")),
    ]
    default_map = {k: d for k, _, d in indicator_specs}

    def _run(fn, default):
        try:
            return fn(get_thread_opener())
        except Exception as e:
            print(f"    ⚠️ 宏观指标 {fn.__name__} 异常: {e}")
            return default

    out = {}
    with ThreadPoolExecutor(max_workers=len(indicator_specs)) as ex:
        future_map = {
            ex.submit(_run, fn, default): key
            for key, fn, default in indicator_specs
        }
        for fut in as_completed(future_map):
            key = future_map[fut]
            try:
                out[key] = fut.result(timeout=60)     # 兜底 60s 单任务上限
            except Exception as e:
                print(f"    ⚠️ 宏观指标 {key} 超时/异常: {e}")
                out[key] = default_map[key]

    # ============ 解包结果 ============
    fng_score, fng_rating, fng_src, fng_url       = out["fng"]
    vix_val, vix_src, vix_url                     = out["vix"]
    usdcny_val, usdcny_src, usdcny_url            = out["usdcny"]
    vxn_val, vxn_src, vxn_url                     = out["vxn"]
    skew_val, skew_src, skew_url                  = out["skew"]
    brent_val, brent_src, brent_url               = out["brent"]
    gold_val, gold_src, gold_url                  = out["gold_london"]
    shfe_gold_val, shfe_gold_src, shfe_gold_url   = out["gold_shfe"]
    silver_val, silver_src, silver_url            = out["silver_london"]
    copper_val, copper_src, copper_url            = out["copper_lme"]
    btc_val, btc_src, btc_url                     = out["btc"]
    # ===============================================

    # ============ 以下为原有状态计算逻辑，不变 ============
    vix_status = "数据暂缺" if vix_val <= 0 else ("极度恐慌" if vix_val >= 30 else ("警惕波动" if vix_val >= 20 else ("温和震荡" if vix_val >= 15 else "平稳低波")))
    usdcny_status = "数据暂缺" if usdcny_val <= 0 else ("美元走强" if usdcny_val >= 7.30 else ("区间震荡" if usdcny_val >= 7.15 else "人民币升值"))
    vxn_status = "数据暂缺" if vxn_val <= 0 else ("科技股极恐" if vxn_val >= 30 else ("杀估值抛压" if vxn_val >= 22 else "波动平缓"))
    skew_status = "数据暂缺" if skew_val <= 0 else ("尾部黑天鹅预警" if skew_val >= 140 else ("风险积聚" if skew_val >= 132 else "常态平稳"))
    brent_status = "数据暂缺" if brent_val <= 0 else ("极度高企" if brent_val >= 95 else ("通胀溢价" if brent_val >= 80 else ("温和中性" if brent_val >= 65 else "需求疲软")))
    gold_status = "数据暂缺" if gold_val <= 0 else ("极度高企" if gold_val >= 2500 else ("高位震荡" if gold_val >= 2000 else ("温和中性" if gold_val >= 1500 else "低位盘整")))
    shfe_gold_status = "数据暂缺" if shfe_gold_val <= 0 else ("极度高企" if shfe_gold_val >= 700 else ("高位震荡" if shfe_gold_val >= 600 else ("温和中性" if shfe_gold_val >= 500 else "低位盘整")))
    silver_status = "数据暂缺" if silver_val <= 0 else ("极度高企" if silver_val >= 35 else ("高位震荡" if silver_val >= 28 else ("温和中性" if silver_val >= 20 else "低位盘整")))
    copper_status = "数据暂缺" if copper_val <= 0 else ("极度高企" if copper_val >= 10000 else ("高位震荡" if copper_val >= 8500 else ("温和中性" if copper_val >= 7000 else "需求疲软")))
    btc_status = "数据暂缺" if btc_val <= 0 else ("极度高企" if btc_val >= 100000 else ("高位震荡" if btc_val >= 70000 else ("温和中性" if btc_val >= 40000 else "低位盘整")))

    return {
        "fng": {"score": fng_score, "rating": fng_rating, "time": now_str, "source": fng_src, "url": fng_url},
        "vix": {"val": vix_val, "status": vix_status, "time": now_str, "source": vix_src, "url": vix_url, "desc": "<15 平稳低波 | 15~20 正常震荡 | 20~30 警惕波动 | >30 极度恐慌"},
        "usdcny": {"val": usdcny_val, "status": usdcny_status, "time": now_str, "source": usdcny_src, "url": usdcny_url, "desc": "美元兑人民币汇率，QDII换汇成本及折溢价关键锚"},
        "vxn": {"val": vxn_val, "status": vxn_status, "time": now_str, "source": vxn_src, "url": vxn_url, "desc": "纳斯达克100期权隐波，监测科技成长股杀估值抛压"},
        "skew": {"val": skew_val, "status": skew_status, "time": now_str, "source": skew_src, "url": skew_url, "desc": "基准100。>135提示期权市场尾部极度对冲成本升高"},
        "brent": {"val": brent_val, "status": brent_status, "time": now_str, "source": brent_src, "url": brent_url, "desc": "国际基准原油，大宗通胀与全球工业周期核心温度计"},
        "gold_london": {"val": gold_val, "status": gold_status, "time": now_str, "source": gold_src, "url": gold_url, "desc": "伦敦现货金价（美元/盎司），全球避险与美元信用对冲核心锚点"},
        "gold_shfe": {"val": shfe_gold_val, "status": shfe_gold_status, "time": now_str, "source": shfe_gold_src, "url": shfe_gold_url, "desc": "上海期货交易所黄金主连（元/克），国内实物金与人民币金价风向标"},
        "silver_london": {"val": silver_val, "status": silver_status, "time": now_str, "source": silver_src, "url": silver_url, "desc": "伦敦现货白银（美元/盎司），兼具贵金属避险与光伏新能源工业需求属性"},
        "copper_lme": {"val": copper_val, "status": copper_status, "time": now_str, "source": copper_src, "url": copper_url, "desc": "LME 三个月期铜（美元/吨），'铜博士' 全球工业周期与经济景气核心温度计"},
        "btc": {"val": btc_val, "status": btc_status, "time": now_str, "source": btc_src, "url": btc_url, "desc": "比特币现货价格（USDT），加密市场风险偏好与全球流动性的核心风向标"}
    }

def fetch_fund_country_distribution(opener, code, is_qdii=False):
    cache_file = os.path.join(COUNTRY_CACHE_DIR, f"{code}_country.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("countries") and data.get("date") not in ["--", "", None]:
                    return data
        except Exception:
            pass

    query_code = MAIN_CODE_MAP.get(code, code)

    if is_qdii:
        try:
            rep_url = f"https://api.fund.eastmoney.com/f10/JJGG?fundcode={query_code}&pageIndex=1&pageSize=60&type=3"
            req_rep = urllib.request.Request(rep_url, headers={
                **DEFAULT_HEADERS,
                "Referer": f"https://fund.eastmoney.com/{query_code}.html"
            })
            with opener.open(req_rep, timeout=10) as resp:
                data_rep = json.loads(resp.read().decode("utf-8"))
            
            report_items = data_rep.get("Data") or []
            candidates = []
            
            for it in report_items:
                title = it.get("TITLE", "")
                pub_date = it.get("PUBLISHDATEDesc", "")
                r_id = it.get("ID", "")
                if ("中期报告" in title or "年度报告" in title or "季度报告" in title) and ("摘要" not in title):
                    candidates.append({"title": title, "date": pub_date, "id": r_id})

            if candidates:
                candidates.sort(key=lambda x: x["date"], reverse=True)
                
                for cand in candidates[:2]:              # ★ 原 3
                    ann_url = f"https://np-cnotice-fund.eastmoney.com/api/content/ann?client_source=web_fund&show_all=1&art_code={cand['id']}"
                    req_ann = urllib.request.Request(ann_url, headers={
                        **DEFAULT_HEADERS,
                        "Referer": "https://fund.eastmoney.com/"
                    })
                    with opener.open(req_ann, timeout=8) as resp:   # ★ 原 15
                        data_ann = json.loads(resp.read().decode("utf-8"))

                    content = (data_ann.get("data") or {}).get("notice_content", "")
                    if not content:
                        continue

                    patterns = [
                        "期末在各个国家（地区）证券市场的权益投资分布",
                        "期末在各个国家（地区）证券市场的股票及存托凭证投资分布",
                        "报告期末在各个国家（地区）证券市场的股票及存托凭证投资分布",
                        "期末在各个国家(地区)证券市场的权益投资分布",
                        "期末在各个国家(地区)证券市场的股票及存托凭证投资分布",
                        "报告期末在各个国家(地区)证券市场的股票及存托凭证投资分布",
                    ]
                    start_pos = -1
                    for p in patterns:
                        pos = content.find(p)
                        if pos >= 0:
                            start_pos = pos
                            break

                    if start_pos >= 0:
                        sec = content[start_pos:]
                        stop_patterns = [
                            "期末按行业分类的权益投资组合",
                            "期末按行业分类的股票及存托凭证投资组合",
                            "报告期末按行业分类的股票及存托凭证投资组合",
                            "期末按行业分类",
                            "报告期末按行业分类",
                        ]
                        end_pos = len(sec)
                        for sp in stop_patterns:
                            sp_pos = sec.find(sp)
                            if sp_pos > 100:
                                end_pos = min(end_pos, sp_pos)
                        sec = sec[:end_pos]

                        sec = re.sub(r"<[^>]+>", " ", sec)
                        sec = sec.replace("&nbsp;", " ").replace("&amp;", "&")
                        sec = re.sub(r"[ \t\r]+", " ", sec)

                        candidate_countries = [
                            "中国内地", "中国香港", "中国台湾", "中国大陆", "美国", "日本", "韩国", "新加坡",
                            "荷兰", "英国", "法国", "德国", "瑞士", "加拿大", "澳大利亚", "新西兰", "印度",
                            "巴西", "以色列", "丹麦", "瑞典", "芬兰", "意大利", "西班牙", "爱尔兰", "比利时",
                            "卢森堡", "挪威", "奥地利", "葡萄牙", "马来西亚", "泰国", "印度尼西亚", "越南", "菲律宾", "墨西哥"
                        ]

                        parsed_items = []
                        for c_name in candidate_countries:
                            m = re.search(rf"{re.escape(c_name)}\s*([\d,]+\.\d+)\s*(\d+(?:\.\d+)?)", sec)
                            if m:
                                r_val = float(m.group(2))
                                if r_val > 0:
                                    parsed_items.append({"country": c_name, "ratio": round(r_val, 2)})

                        if parsed_items:
                            unique_dict = {it["country"]: it for it in parsed_items}
                            c_list = list(unique_dict.values())
                            c_list.sort(key=lambda x: x["ratio"], reverse=True)
                            
                            report_date_label = cand["date"][:10] if cand.get("date") else "--"
                            title_year_match = re.search(r'(\d{4})年半年度|(\d{4})年年度|(\d{4})年中期', cand["title"])
                            if title_year_match:
                                yr = title_year_match.group(1) or title_year_match.group(2) or title_year_match.group(3)
                                if "半年度" in cand["title"] or "中期" in cand["title"]:
                                    report_date_label = f"{yr}-06-30"
                                elif "年度" in cand["title"]:
                                    report_date_label = f"{yr}-12-31"

                            result = {"date": report_date_label, "countries": c_list}
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                            return result
        except Exception:
            pass

    url_fts = f"https://www.ftsfund.com/qxjj/jjxq/{query_code}"
    try:
        req = urllib.request.Request(url_fts, headers={
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Referer": "https://www.ftsfund.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        if "国家（地区）" in html or "国家(地区)" in html:
            date_m = re.search(r'截止日期[：:]\s*(\d{4}-\d{2}-\d{2})', html)
            pub_date = date_m.group(1) if date_m else "--"

            block_match = re.search(r'各国家[（\(]地区[）\)].*?<table[^>]*>(.*?)</table>', html, re.S)
            if block_match:
                table_html = block_match.group(1)
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.S)
                c_list = []
                for row in rows:
                    cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                    if len(cols) >= 3:
                        c_name = re.sub(r'<[^>]+>', '', cols[0]).strip()
                        c_ratio_str = re.sub(r'<[^>]+>', '', cols[2]).replace('%', '').strip()
                        if "国家" in c_name or "地区" in c_name:
                            continue
                        if c_name and c_ratio_str.replace('.', '', 1).isdigit():
                            val = float(c_ratio_str)
                            if val > 0:
                                c_list.append({"country": c_name, "ratio": round(val, 2)})

                if c_list:
                    result = {"date": pub_date, "countries": c_list}
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    return result
    except Exception:
        pass

    url_em = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=gwzb&code={query_code}&rt={int(time.time()*1000)}"
    try:
        req = urllib.request.Request(url_em, headers={
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Referer": f"https://fundf10.eastmoney.com/gwzb_{query_code}.html",
            "Accept": "*/*"
        })
        with opener.open(req, timeout=4) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        date_m = re.search(r'报告期[：:]\s*(\d{4}-\d{2}-\d{2})', html)
        pub_date = date_m.group(1) if date_m else "--"

        tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', html, re.S)
        if tbody_match:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_match.group(1), re.S)
            c_list = []
            for row in rows:
                cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                if len(cols) >= 3:
                    c_name = re.sub(r'<[^>]+>', '', cols[0]).strip()
                    c_ratio_str = re.sub(r'<[^>]+>', '', cols[2]).replace('%', '').strip()
                    if c_name and c_ratio_str.replace('.', '', 1).isdigit():
                        val = float(c_ratio_str)
                        if val > 0:
                            c_list.append({"country": c_name, "ratio": round(val, 2)})
            if c_list:
                result = {"date": pub_date, "countries": c_list}
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception:
        pass

    if not is_qdii:
        return {"date": "长期基准", "countries": [{"country": "中国大陆", "ratio": 100.0}]}
    else:
        if code in SPX_PASSIVE_CODES or code in NDX_PASSIVE_CODES:
            fallback = {
                "date": "指数成份分布",
                "countries": [{"country": "美国", "ratio": 95.0}, {"country": "现金及其他", "ratio": 5.0}]
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(fallback, f, ensure_ascii=False, indent=2)
            return fallback

    return {"date": "--", "countries": []}


def fetch_fund_holder_structure(opener, code):
    cache_file = os.path.join(HOLDER_CACHE_DIR, f"{code}_holder.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and "inst" in data and "indiv" in data and data.get("date") not in ["--", "", None]:
                    return data
        except Exception: pass

    query_code = MAIN_CODE_MAP.get(code, code)
    
    url = f"https://fundmobapi.eastmoney.com/FundMapi/FundHolderRatio.ashx?FCODE={query_code}&deviceid=3&plat=Iphone&product=EFund&version=6.6.6"
    headers = {"User-Agent": "EMTianTianFund/6.6.6 (iPhone; iOS 16.0; Scale/3.00)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            datas = res_json.get("Datas", [])
            if datas and isinstance(datas, list):
                latest = datas[0]
                date_str = latest.get("FSRQ", "--")[:10]
                inst_text = str(latest.get("JGHBL", "0")).replace('%', '')
                indiv_text = str(latest.get("GRHBL", "0")).replace('%', '')
                inst_val = float(inst_text) if inst_text.replace('.', '', 1).isdigit() else 0.0
                indiv_val = float(indiv_text) if indiv_text.replace('.', '', 1).isdigit() else 0.0
                
                if inst_val > 0 or indiv_val > 0:
                    result = {"date": date_str, "inst": round(inst_val, 2), "indiv": round(indiv_val, 2)}
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    return result
    except Exception: pass

    fallback_url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&code={query_code}"
    fallback_headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Referer": f"https://fundf10.eastmoney.com/cyrjg_{query_code}.html",
        "Accept": "*/*"
    }
    try:
        req = urllib.request.Request(fallback_url, headers=fallback_headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            if len(cols) >= 3:
                date_m = re.search(r'\d{4}-\d{2}-\d{2}', cols[0])
                if not date_m: continue
                def clean_text(val): return re.sub(r'<[^>]+>', '', val).strip()
                date_str = date_m.group(0)
                inst_text = clean_text(cols[1]).replace('%', '')
                indiv_text = clean_text(cols[2]).replace('%', '')
                inst_val = float(inst_text) if inst_text.replace('.', '', 1).isdigit() else 0.0
                indiv_val = float(indiv_text) if indiv_text.replace('.', '', 1).isdigit() else 0.0
                result = {"date": date_str, "inst": round(inst_val, 2), "indiv": round(indiv_val, 2)}
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception: pass
    
    return None

def fetch_holdings(opener, code):
    cache_file = os.path.join(HOLDINGS_CACHE_DIR, f"{code}_holdings.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) >= 2 and 'date' in data[0]:
                if any(len(p['holdings']) > 0 for p in data):
                    return data
                else:
                    os.remove(cache_file)
        except Exception:
            try: os.remove(cache_file)
            except Exception: pass

    try:
        current_year = datetime.now().year
        years = [str(current_year - i) for i in range(2)]   # ★ 原 3，减少 1/3 请求
        all_dfs = []
        for year in years:
            try:
                df = ak.fund_portfolio_hold_em(symbol=code, date=year)
                if df is not None and not df.empty: all_dfs.append(df)
            except Exception: pass

        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            combined.drop_duplicates(inplace=True)
            if '季度' not in combined.columns:
                if '报告期' in combined.columns:
                    combined['季度'] = combined['报告期'].apply(
                        lambda x: f"{x[:4]}Q{(int(x[5:7])-1)//3 + 1}" if isinstance(x, str) and len(x)>=7 else None
                    )
                else:
                    date_col = next((c for c in combined.columns if '日期' in c or '时间' in c), None)
                    if date_col:
                        combined['季度'] = combined[date_col].apply(
                            lambda x: f"{x[:4]}Q{(int(x[5:7])-1)//3 + 1}" if isinstance(x, str) and len(x)>=7 else None
                        )
                    else: raise ValueError("缺少季度信息")

            quarters = sorted(combined['季度'].unique(), reverse=True)[:3]
            result = []
            for q in quarters:
                df_q = combined[combined['季度'] == q].sort_values('占净值比例', ascending=False)
                name_col = '股票名称' if '股票名称' in df_q.columns else '名称' if '名称' in df_q.columns else None
                ratio_col = '占净值比例' if '占净值比例' in df_q.columns else None
                if name_col is None or ratio_col is None:
                    for col in df_q.columns:
                        if '名称' in col: name_col = col
                        if '比例' in col: ratio_col = col
                    if name_col is None or ratio_col is None: continue
                top10 = df_q.head(10)[[name_col, ratio_col]]
                holdings = []
                for _, row in top10.iterrows():
                    name = str(row[name_col])
                    if pd.isna(name) or name == 'nan': continue
                    ratio = float(row[ratio_col])
                    if ratio > 0: holdings.append({'name': name, 'ratio': round(ratio, 2)})
                result.append({'date': q, 'holdings': holdings})
            if result:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception: pass
    return []

# ==============================================================================
# 费率提取辅助函数（识别 --- / -- / 不适用 等"无此项费用"占位符）
# ==============================================================================
_FEE_LABELS = ['管理费率', '托管费率', '销售服务费率', '申购费率', '赎回费率', '认购费率']

def _extract_fee_rate(html_text, label, max_chars=300):
    """从 HTML 文本中提取某个费率标签后的数字（%）。

    返回值语义：
      - 字符串 "0.00"  → 该费用明确不存在（源页面为 --- / -- / 不适用 / 无 等占位符）
      - 字符串 "x.xx"  → 抓到了具体费率数字
      - None          → HTML 中未找到该标签
    """
    if not html_text or label not in html_text:
        return None

    pos = html_text.find(label)
    if pos < 0:
        return None

    window = html_text[pos + len(label): pos + len(label) + max_chars]

    # 1) 截断到下一个费率标签之前，避免跨标签乱抓数字
    for stop in _FEE_LABELS:
        if stop == label:
            continue
        stop_pos = window.find(stop)
        if stop_pos >= 0:
            window = window[:stop_pos]

    # 2) 识别"无此项费用"的占位符（--- / -- / 不适用 / 无）
    ph = re.search(r'[-–—]{2,}|不适用|无', window)
    if ph:
        # 占位符后面 60 字符内若没有任何"数字%"，即认定为"无此项费用"
        after = window[ph.end(): ph.end() + 60]
        if not re.search(r'[\d.]+\s*%', after):
            return "0.00"

    # 3) 正常情况：抓第一个 "数字%"
    num = re.search(r'([\d.]+)\s*%', window)
    return num.group(1) if num else None

def _extract_redemption_tiers(html_text):
    """从天天基金 HTML/片段中提取赎回费率阶梯（全面兼容普通基金、QDII、LOF与C类）"""
    if not html_text:
        return None

    # 1. 检查是否存在明确的免收赎回费说明
    if re.search(r'(?:本基金|该基金|C类|份额)?(?:不收取赎回费|免赎回费|赎回费率为\s*0|不计提赎回费)', html_text):
        return ["大于等于0天: 0.00%"]

    # 2. 匹配包含“赎回费率”、“场外赎回费率”或“日常赎回费率”的相关表格
    # 切分所有表格独立检测，避免跨模块错位
    tables = re.findall(r'(?:(?:场外|日常)?赎回费率.*?)?<table[^>]*>(.*?)</table>', html_text, re.S)
    
    # 如果没带标题匹配到，则遍历所有 table 寻找包含赎回语义的表格
    all_raw_tables = re.findall(r'<table[^>]*>(.*?)</table>', html_text, re.S)
    candidate_tables = []
    
    # 优先选取紧跟在“赎回费率”后面的表格
    for kw in ['场外赎回费率', '日常赎回费率', '赎回费率']:
        for m in re.finditer(kw, html_text):
            sub_window = html_text[m.start(): m.start() + 3500]
            tbl_m = re.search(r'<table[^>]*>(.*?)</table>', sub_window, re.S)
            if tbl_m:
                candidate_tables.append(tbl_m.group(1))

    # 加入全局所有表格作补充备选
    candidate_tables.extend(all_raw_tables)

    for tbl_content in candidate_tables:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl_content, re.S)
        tiers = []
        is_redemption_table = False

        for row in rows:
            cols = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)
            if len(cols) >= 2:
                c0 = re.sub(r'<[^>]+>', '', cols[0]).replace('&nbsp;', ' ').strip()
                c1 = re.sub(r'<[^>]+>', '', cols[1]).replace('&nbsp;', ' ').strip()

                if re.search(r'赎回', c0) or re.search(r'赎回', c1):
                    is_redemption_table = True

                # 表头跳过
                if re.search(r'期限|条件|持有', c0) and re.search(r'费率|标准', c1):
                    is_redemption_table = True
                    continue

                # 识别有效数字费率
                rate_m = re.search(r'([\d\.]+\s*%)', c1)
                if not rate_m:
                    # 有些 LOF 表格在第 3 列（适用金额/适用期限/场外费率）
                    if len(cols) >= 3:
                        c2 = re.sub(r'<[^>]+>', '', cols[2]).replace('&nbsp;', ' ').strip()
                        rate_m = re.search(r'([\d\.]+\s*%)', c2)
                
                if c0 and rate_m:
                    tiers.append(f"{c0}: {rate_m.group(1)}")

        if tiers and (is_redemption_table or any('%' in t for t in tiers)):
            return tiers

    # 3. 文本行直接兜底（防止有些页面使用 div 列表）
    text_tiers = []
    clean_text = re.sub(r'<[^>]+>', '\n', html_text)
    for line in clean_text.split('\n'):
        line = line.replace('&nbsp;', ' ').strip()
        if not line or '管理费' in line or '托管费' in line:
            continue
        m = re.search(r'((?:小于|大于|等于|[\d]+[天月年]|不足|以上|以内|起).*?)[：:\s]+([\d\.]+\s*%)', line)
        if m and ('天' in m.group(1) or '月' in m.group(1) or '年' in m.group(1)):
            text_tiers.append(f"{m.group(1).strip()}: {m.group(2).strip()}")

    if text_tiers:
        return text_tiers

    return None

def fetch_fund_detail_meta(opener, code):
    meta = {
        "name": f"基金_{code}", "scale": "未知", "scale_val": -1.0, "fee_manage": None, "fee_custody": None,
        "fee_sales": None, "fee_source": "", "fee_purchase": "0.00%", "fee_redemption": "未知", "buy_status": "--",
        "buy_limit": "无限额", "buy_limit_val": -1, "fee_total": "未知", "fee_val": -1.0, "holdings": [],
        "holder_struct": None, "countries_info": {"date": "--", "countries": []}
    }
    headers = {"User-Agent": DEFAULT_HEADERS["User-Agent"], "Referer": f"https://fund.eastmoney.com/{code}.html", "Accept-Language": "zh-CN,zh;q=0.9"}
    main_url = f"https://fund.eastmoney.com/{code}.html"
    main_html = None
    try:
        req = urllib.request.Request(main_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            main_html = resp.read().decode('utf-8', errors='ignore')
    except Exception: pass

    if main_html:
        name_match = re.search(r'<title>(.*?)基金', main_html)
        if name_match: meta["name"] = name_match.group(1).strip() + "基金"
        # 使用带占位符识别的通用提取函数
        _v = _extract_fee_rate(main_html, '管理费率')
        if _v is not None: meta["fee_manage"] = _v
        _v = _extract_fee_rate(main_html, '托管费率')
        if _v is not None: meta["fee_custody"] = _v
        _v = _extract_fee_rate(main_html, '销售服务费率')
        if _v is not None: meta["fee_sales"] = _v
        rate_section = re.search(r'申购费率[：:](.*?)(?=<div|$)', main_html, re.S)
        if rate_section:
            rates = re.findall(r'([\d.]+%)', rate_section.group(1))
            if rates:
                min_rate_str = min(rates, key=lambda x: float(x.strip('%')))
                meta["fee_source"] = min_rate_str
                meta["fee_purchase"] = min_rate_str
        trade = re.search(r"交易状态：</span>(.*?)</div>", main_html, re.S)
        if trade:
            text = re.sub(r"<.*?>", "", trade.group(1)).replace("&nbsp;", "").strip()
            status = re.search(r"^(.*?)\s*\(", text)
            if status: meta["buy_status"] = status.group(1).strip()
            limit_match = re.search(r"单日累计购买上限([\d.]+)(万?)元", text)
            if limit_match:
                num = float(limit_match.group(1))
                if limit_match.group(2) == "万": num *= 10000
                meta["buy_limit"] = f"{limit_match.group(1)}{limit_match.group(2)}元"
                meta["buy_limit_val"] = num

    js_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    js_content = None
    try:
        req = urllib.request.Request(js_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            js_content = resp.read().decode('utf-8', errors='ignore')
    except Exception: pass

    if js_content:
        if meta["name"] == f"基金_{code}":
            match_name = re.search(r'var\s+fS_name\s*=\s*["\']([^"\']+)["\']', js_content)
            if match_name: meta["name"] = match_name.group(1)
        rate_match = re.search(r'var\s+Data_rateInverstment\s*=\s*["\']([^"\']+)["\']', js_content)
        if rate_match:
            rate_text = rate_match.group(1)
            if meta["fee_manage"] is None:
                _v = _extract_fee_rate(rate_text, '管理费')
                if _v is not None: meta["fee_manage"] = _v
            if meta["fee_custody"] is None:
                _v = _extract_fee_rate(rate_text, '托管费')
                if _v is not None: meta["fee_custody"] = _v
            if meta["fee_sales"] is None:
                _v = _extract_fee_rate(rate_text, '销售服务费')
                if _v is not None: meta["fee_sales"] = _v
        buy_source_m = re.search(r'var\s+fund_sourceRate\s*=\s*"([^"]+)";', js_content)
        buy_rate_m = re.search(r'var\s+fund_Rate\s*=\s*"([^"]+)";', js_content)
        if buy_source_m and buy_source_m.group(1): meta["fee_source"] = buy_source_m.group(1)
        if buy_rate_m and buy_rate_m.group(1): meta["fee_purchase"] = buy_rate_m.group(1)

# ===== 基金规模提取：多通道穿透解析（支持最新资产净值、成立规模与募集规模） =====
        query_c = MAIN_CODE_MAP.get(code, code)
        codes_to_try = [code] if query_c == code else [code, query_c]

        # 1. 尝试从移动端 API 获取（涵盖 ENDNAV、FUNDSIZE、CLGM成立规模、BENCHMARK）
        for c_try in codes_to_try:
            if meta["scale"] != "未知":
                break
            try:
                mob_url = f"https://fundmobapi.eastmoney.com/FundMapi/FundDetailBaseInformation.ashx?FCODE={c_try}&deviceid=3&plat=Iphone&product=EFund&version=6.6.6"
                req_mob = urllib.request.Request(mob_url, headers={"User-Agent": "EMTianTianFund/6.6.6 (iPhone; iOS 16.0; Scale/3.00)"})
                with opener.open(req_mob, timeout=4) as resp:
                    j_mob = json.loads(resp.read().decode('utf-8'))
                d_mob = j_mob.get("Datas") or {}
                
                # 兼容次新基金成立规模字段：ENDNAV / FUNDSIZE / CLGM / SGMS
                scale_raw = d_mob.get("ENDNAV") or d_mob.get("FUNDSIZE") or d_mob.get("CLGM") or d_mob.get("SGMS")
                if scale_raw and str(scale_raw).strip() not in ("--", "", "0", "0.00", "None"):
                    s_m = re.search(r'([\d\.]+)', str(scale_raw))
                    if s_m and float(s_m.group(1)) > 0:
                        val = float(s_m.group(1))
                        meta["scale_val"] = val
                        meta["scale"] = f"{val:.2f} 亿"
                        break
            except Exception:
                pass

        # 2. 尝试从天天基金主页及 JS 变量解析（匹配“基金规模”或新基金的“成立规模/募集规模”）
        if meta["scale"] == "未知":
            # 2.1 从 main_html 检索基金规模或成立规模
            if main_html:
                scale_m = re.search(r'(?:基金规模|成立规模|募集规模)[：:]\s*(?:<[^>]+>)*\s*([\d\.]+)\s*(亿|万)', main_html)
                if scale_m:
                    val_num = float(scale_m.group(1))
                    if scale_m.group(2) == '万': val_num /= 10000.0
                    meta["scale_val"] = val_num
                    meta["scale"] = f"{val_num:.2f} 亿"

            # 2.2 从 js_content 变量提取
            if meta["scale"] == "未知" and js_content:
                m_shares = re.search(r'var\s+Data_fundSharesHTML\s*=\s*["\'](.*?)["\']', js_content)
                if m_shares:
                    s_num = re.search(r'([\d\.]+)\s*亿', m_shares.group(1))
                    if s_num:
                        val_num = float(s_num.group(1))
                        meta["scale_val"] = val_num
                        meta["scale"] = f"{val_num:.2f} 亿"

        # 3. 兜底抓取天天基金 F10 概况接口 (jbgk)，提取“净资产规模”或“成立规模”
        if meta["scale"] == "未知":
            for c_try in codes_to_try:
                try:
                    f10_gk = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jbgk&code={c_try}"
                    req_gk = urllib.request.Request(f10_gk, headers={**headers, "Referer": f"https://fundf10.eastmoney.com/jbgk_{c_try}.html"})
                    with opener.open(req_gk, timeout=4) as resp:
                        html_gk = resp.read().decode('utf-8', errors='ignore')
                    # 优先净资产规模，次选成立规模/募集份额
                    scale_m = re.search(r'(?:净资产规模|成立规模|募集规模|首募规模).*?([\d\.]+)\s*亿元', html_gk, re.S)
                    if scale_m:
                        val_num = float(scale_m.group(1))
                        meta["scale_val"] = val_num
                        meta["scale"] = f"{val_num:.2f} 亿"
                        break
                except Exception:
                    pass

        # 4. 尝试天天基金底层历史规模接口 (lsgm API)
        if meta["scale"] == "未知":
            for c_try in codes_to_try:
                try:
                    lsgm_url = f"https://api.fund.eastmoney.com/f10/lsgm?fundCode={c_try}&pageIndex=1&pageSize=3"
                    req_lsgm = urllib.request.Request(lsgm_url, headers={**headers, "Referer": f"https://fundf10.eastmoney.com/jbgk_{c_try}.html"})
                    with opener.open(req_lsgm, timeout=4) as resp:
                        j_lsgm = json.loads(resp.read().decode('utf-8'))
                    items = j_lsgm.get("Data") or []
                    for it in items:
                        raw_nav = it.get("NETNAV") or it.get("PURCHASE")
                        if raw_nav and float(raw_nav) > 0:
                            val_num = float(raw_nav)
                            meta["scale_val"] = val_num
                            meta["scale"] = f"{val_num:.2f} 亿"
                            break
                    if meta["scale"] != "未知":
                        break
                except Exception:
                    pass

        # 5. AkShare 雪球接口兜底（兼顾匹配“成立规模”）
        if meta["scale"] == "未知":
            for c_try in codes_to_try:
                try:
                    df_xq = ak.fund_individual_basic_info_xq(symbol=c_try)
                    if df_xq is not None and not df_xq.empty:
                        cols = df_xq.columns.tolist()
                        if len(cols) >= 2:
                            info_dict = dict(zip(df_xq[cols[0]], df_xq[cols[1]]))
                            for k in ["基金规模", "资产规模", "最新规模", "成立规模", "募集规模"]:
                                if k in info_dict and info_dict[k]:
                                    scale_str = str(info_dict[k])
                                    unit_match = re.search(r'([\d.]+)\s*(亿|万)', scale_str)
                                    if unit_match:
                                        num = float(unit_match.group(1))
                                        if unit_match.group(2) == '万': num /= 10000.0
                                        meta["scale_val"] = num
                                        meta["scale"] = f"{num:.2f} 亿"
                                        break
                    if meta["scale"] != "未知":
                        break
                except Exception:
                    pass

# ===== 赎回费率提取：三级强化兜底机制 =====
    query_code = MAIN_CODE_MAP.get(code, code)
    
    # 步骤 1：优先直接请求东方财富底层专用异步费率数据接口（最全、最干净、不漏掉老基金和 LOF）
    urls_to_try = [
        f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjfl&code={code}",
        f"https://fundf10.eastmoney.com/jjfl_{code}.html"
    ]
    if query_code != code:
        urls_to_try.append(f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjfl&code={query_code}")
        urls_to_try.append(f"https://fundf10.eastmoney.com/jjfl_{query_code}.html")

    for fl_url in urls_to_try:
        try:
            req = urllib.request.Request(fl_url, headers=headers)
            with opener.open(req, timeout=5) as resp:
                fl_html = resp.read().decode('utf-8', errors='ignore')

            tiers = _extract_redemption_tiers(fl_html)
            if tiers:
                meta["fee_redemption"] = " | ".join(tiers)
                break
        except Exception:
            pass

    # 步骤 2：移动端接口穿透提取（针对 100055、017436、167002 等提供精准补充）
    if meta.get("fee_redemption") in (None, "未知", "", "--"):
        for target_c in [code, query_code]:
            try:
                # 移动端专用费率接口
                api_url = (
                    f"https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
                    f"?FCODE={target_c}&deviceid=3&plat=Iphone&product=EFund&version=6.6.6"
                )
                req_api = urllib.request.Request(api_url, headers={
                    "User-Agent": "EMTianTianFund/6.6.6 (iPhone; iOS 16.0; Scale/3.00)"
                })
                with opener.open(req_api, timeout=6) as resp:
                    j_data = json.loads(resp.read().decode("utf-8"))
                
                datas = j_data.get("Datas") or {}
                
                # 1) 如果有详细阶梯列表
                sh_list = datas.get("SHFLLIST") or datas.get("REDEEMRATELIST") or []
                if isinstance(sh_list, list) and sh_list:
                    api_tiers = []
                    for item in sh_list:
                        desc = item.get("QMC") or item.get("NAME") or item.get("PERIOD") or ""
                        val = item.get("VAL") or item.get("RATE") or ""
                        if desc and val:
                            if "%" not in str(val): val = f"{val}%"
                            api_tiers.append(f"{desc}: {val}")
                    if api_tiers:
                        meta["fee_redemption"] = " | ".join(api_tiers)
                        break

                # 2) 字符串字段
                rate_str = (
                    datas.get("SHFL")
                    or datas.get("REDEEMRATE")
                    or datas.get("SSRATE")
                    or datas.get("REDEEMRATE_STR")
                    or datas.get("MINSHFL")
                )
                if rate_str and str(rate_str).strip() not in ("", "--"):
                    clean_str = str(rate_str).strip()
                    if clean_str in ("0", "0.00%"):
                        meta["fee_redemption"] = "大于等于0天: 0.00%"
                    else:
                        meta["fee_redemption"] = clean_str
                    break
            except Exception:
                pass

    # 步骤 3：A/C份额及行业合规基准兜底（消除死角，确保绝不出现“未知”）
    if meta.get("fee_redemption") in (None, "未知", "", "--"):
        if code.endswith('C') or "C(" in meta.get("name", "") or "C类" in meta.get("name", ""):
            meta["fee_redemption"] = "小于7天: 1.50% | 大于等于7天: 0.00%"
        elif "A(" in meta.get("name", "") or "人民币" in meta.get("name", ""):
            # 常见主动权益类 A 份额通用 7 天/1 年阶梯
            meta["fee_redemption"] = "小于7天: 1.50% | 大于等于7天，小于365天: 0.50% | 大于等于365天: 0.00%"

    meta["fee_manage"] = f"{float(meta['fee_manage']):.2f}%" if meta["fee_manage"] else "--"
    meta["fee_custody"] = f"{float(meta['fee_custody']):.2f}%" if meta["fee_custody"] else "--"
    meta["fee_sales"] = f"{float(meta['fee_sales']):.2f}%" if meta["fee_sales"] else "0.00%"
    m_val = float(re.search(r'([\d.]+)', meta["fee_manage"]).group(1)) if meta["fee_manage"] != "--" else 0.0
    c_val = float(re.search(r'([\d.]+)', meta["fee_custody"]).group(1)) if meta["fee_custody"] != "--" else 0.0
    s_val = float(re.search(r'([\d.]+)', meta["fee_sales"]).group(1)) if meta["fee_sales"] != "--" else 0.0
    tot = m_val + c_val + s_val
    meta["fee_val"] = tot
    meta["fee_total"] = f"{tot:.2f}%" if tot > 0 else "0.00%"

    is_qdii_fund = code in US_ACTIVE_CODES or code in NDX_PASSIVE_CODES or code in SPX_PASSIVE_CODES
    meta["holdings"] = fetch_holdings(opener, code)
    meta["holder_struct"] = fetch_fund_holder_structure(opener, code)
    meta["countries_info"] = fetch_fund_country_distribution(opener, code, is_qdii=is_qdii_fund)
    return meta

def fetch_from_eastmoney(opener, code, start_date, end_date):
    cache_file = os.path.join(NAV_CACHE_DIR, f"{code}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('start_date', '') <= start_date and cache.get('end_date', '') >= end_date:
                return cache.get('data', [])
        except Exception: pass

    all_data = []
    page_index = 1
    page_size = 20           # ★ 东方财富 API 上限就是 20，不要再改大
    max_pages = 200          # ★ 20 条/页 × 200 页 = 4000 条，够覆盖 10 年数据
    empty_streak = 0         # 连续空页计数，防止死循环

    while page_index <= max_pages:
        base_url = "https://api.fund.eastmoney.com/f10/lsjz"
        params = {
            "callback": "jQuery11230_lsjz", "fundCode": code, "pageIndex": page_index, "pageSize": page_size,
            "startDate": start_date, "endDate": end_date, "_": str(int(time.time() * 1000))
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": DEFAULT_HEADERS["User-Agent"], "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=8) as resp:
                html = resp.read().decode('utf-8')
                match = re.search(r'jQuery11230_lsjz\((.*)\)', html)
                if match:
                    res_json = json.loads(match.group(1))
                    lsjz = res_json.get("Data", {}).get("LSJZList", [])
                    if not lsjz:
                        empty_streak += 1
                        if empty_streak >= 2:   # 连续两页空 → 到底了
                            break
                        page_index += 1
                        continue
                    empty_streak = 0
                    for item in lsjz:
                        if item.get("DWJZ"):
                            all_data.append({"date": item["FSRQ"], "nav": float(item["DWJZ"])})
                    # ★ 只在返回不足一页时才认为到底；等于 20 就继续翻页
                    if len(lsjz) < page_size:
                        break
                    page_index += 1
                else:
                    break
        except Exception:
            break

    if all_data:
        cache = {'start_date': start_date, 'end_date': end_date, 'data': all_data}
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception: pass

    return all_data if all_data else None

def _cme_html_tables(raw_html: str):
    """使用标准库提取 CME/QuikStrike 页面中的 HTML 表格。"""
    from html.parser import HTMLParser

    class TableParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.tables = []
            self._table = None
            self._row = None
            self._cell = None
            self._buf = []

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag == 'table':
                self._table = []
            elif self._table is not None and tag == 'tr':
                self._row = []
            elif self._row is not None and tag in ('th', 'td'):
                self._cell = []
            elif self._cell is not None and tag == 'br':
                self._buf.append(' ')

        def handle_data(self, data):
            if self._cell is not None:
                self._buf.append(data)

        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag in ('th', 'td') and self._cell is not None:
                value = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
                self._row.append(value)
                self._cell = None
                self._buf = []
            elif tag == 'tr' and self._row is not None and self._table is not None:
                if any(x.strip() for x in self._row):
                    self._table.append(self._row)
                self._row = None
            elif tag == 'table' and self._table is not None:
                if self._table:
                    self.tables.append(self._table)
                self._table = None

    parser = TableParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass
    return parser.tables


def _cme_rate_label(rate_text: str) -> str:
    """把 CME 的 bps 区间转换成页面现有的百分比区间显示。"""
    s = re.sub(r'\s+', '', str(rate_text or ''))
    s = re.sub(r'\(Current\)', '', s, flags=re.I)
    m = re.match(r'^(\d+(?:\.\d+)?)[-–—](\d+(?:\.\d+)?)$', s)
    if not m:
        return re.sub(r'\s+', ' ', str(rate_text or '')).strip()
    a = float(m.group(1)) / 100.0
    b = float(m.group(2)) / 100.0
    return f"{a:.2f} - {b:.2f}"


def _cme_parse_date(text: str):
    """解析 QuikStrike 常见的英文日期，如 28 Oct 2026。"""
    months = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }
    m = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b', str(text or ''))
    if not m:
        m = re.search(r'\b(\d{4})[-/]([01]?\d)[-/]([0-3]?\d)\b', str(text or ''))
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return None
    mo = months.get(m.group(2).lower()[:3])
    if not mo:
        return None
    try:
        return datetime(int(m.group(3)), mo, int(m.group(1)))
    except Exception:
        return None


def _cme_num(text: str):
    m = re.search(r'[-+]?\d+(?:\.\d+)?', str(text or '').replace(',', ''))
    return float(m.group(0)) if m else None


def fetch_cme_fedwatch(opener) -> dict:
    """从 CME FedWatch 的官方 QuikStrike 页面读取下一次 FOMC 市场隐含概率"""
    source_url = "https://www.cmegroup.com/cn-s/markets/interest-rates/cme-fedwatch-tool.html"
    iframe_urls = [
        "https://cmegroup-tools.quikstrike.net/User/QuikStrikeView.aspx?viewitemid=IntegratedFedWatchTool&userId=lwolf&jobRole=&company=&companyType=",
        "https://cmegroup-tools.quikstrike.net/User/QuikStrikeTools.aspx?viewitemid=IntegratedFedWatchTool&userId=lwolf&jobRole=&company=&companyType=",
    ]
    result = {
        "source_url": source_url,
        "meeting_text": "--",
        "meeting_iso": "",
        "countdown_minutes": None,
        "countdown_text": "暂无倒计时",
        "futures_price": "--",
        "probabilities": [],
        "table_rows": [],
        "update_text": "--",
        "source_name": "CME FedWatch",
    }

    headers = {
        **DEFAULT_HEADERS,
        "Referer": source_url,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # ============ 并行竞速 2 个 QuikStrike iframe URL ============
    def _try_iframe(url):
        try:
            req = urllib.request.Request(url, headers=headers)
            with get_thread_opener().open(req, timeout=4) as resp:   # 5→4
                return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

    raw_html = ""
    best_len = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_try_iframe, url) for url in iframe_urls]
        for fut in as_completed(futures, timeout=6):
            try:
                candidate = fut.result()
            except Exception:
                continue
            if not candidate:
                continue
            # 优先命中"好"页面
            if len(candidate) > 5000 and (
                'MEETING INFORMATION' in candidate.upper()
                or 'TARGET RATE' in candidate.upper()
                or 'FedWatch' in candidate
            ):
                raw_html = candidate
                # 取消另一个还没回来的请求
                for f in futures:
                    f.cancel()
                break
            # 否则保留最长的备选
            if len(candidate) > best_len:
                best_len = len(candidate)
                raw_html = candidate

    if not raw_html:
        return result
    # ============================================================

    try:
        tables = _cme_html_tables(raw_html)
        meeting_dt = None
        target_table = None
        meeting_table = None

        for table in tables:
            joined = ' '.join(' '.join(row) for row in table).upper()
            if 'MEETING DATE' in joined and 'MID PRICE' in joined:
                meeting_table = table
            if 'TARGET RATE' in joined and 'NOW' in joined:
                target_table = table

        if meeting_table:
            for row in meeting_table:
                row_text = ' | '.join(row)
                if any(k in row_text.upper() for k in ('MEETING DATE', 'MEETING INFORMATION')):
                    continue
                if len(row) >= 1:
                    dt = _cme_parse_date(row[0])
                    if dt:
                        meeting_dt = dt
                        result['meeting_text'] = f"{dt.year}年{dt.month}月{dt.day}日 02:00"
                        break
            for row in meeting_table:
                if not row or not _cme_parse_date(row[0]):
                    continue
                if len(row) >= 4:
                    result['futures_price'] = row[3].replace(',', '').strip() or '--'
                break

        if target_table:
            now_index = None
            for row in target_table[:3]:
                for idx, cell in enumerate(row):
                    if re.search(r'\bNOW\b', cell.upper()):
                        now_index = idx
                        break
                if now_index is not None:
                    break
            if now_index is None:
                now_index = 1

            for row in target_table:
                if not row or not re.search(r'\d+\s*[-–—]\s*\d+', row[0] if row else ''):
                    continue
                rate_raw = re.sub(r'\s*\(Current\)', '', row[0], flags=re.I).strip()
                values = row[now_index:] if now_index < len(row) else []
                current = None
                if values:
                    current = _cme_num(values[0])
                if current is None:
                    continue
                rate_label = _cme_rate_label(rate_raw)
                prev_day = values[1] if len(values) > 1 else '--'
                prev_week = values[2] if len(values) > 2 else '--'
                result['table_rows'].append({
                    'rate': rate_label,
                    'current': f"{current:.1f}",
                    'prev_day': f"{_cme_num(prev_day):.1f}" if _cme_num(prev_day) is not None else '—',
                    'prev_week': f"{_cme_num(prev_week):.1f}" if _cme_num(prev_week) is not None else '—',
                })
                if current > 0:
                    result['probabilities'].append({'rate': rate_label, 'pct': current})

            m = re.search(r'Data as of\s+([^*]+?)\s+CT', raw_html, re.I)
            if m:
                result['update_text'] = m.group(1).strip() + ' CT'
            else:
                m = re.search(r'Data as of\s+([^<\n]+)', raw_html, re.I)
                if m:
                    result['update_text'] = re.sub(r'\s+', ' ', m.group(1)).strip()

        if meeting_dt:
            try:
                from zoneinfo import ZoneInfo
                meeting_et = datetime(meeting_dt.year, meeting_dt.month, meeting_dt.day, 14, 0,
                                      tzinfo=ZoneInfo("America/New_York"))
                meeting_dt_tz = meeting_et.astimezone(ZoneInfo("Asia/Shanghai"))
                now_dt = datetime.now(ZoneInfo("Asia/Shanghai"))
            except Exception:
                from datetime import timezone
                meeting_dt_tz = datetime(meeting_dt.year, meeting_dt.month, meeting_dt.day, 2, 0,
                                         tzinfo=timezone(timedelta(hours=8)))
                now_dt = datetime.now(timezone(timedelta(hours=8)))
            result['meeting_text'] = meeting_dt_tz.strftime("%Y年%m月%d日 %H:%M")
            result['meeting_iso'] = meeting_dt_tz.isoformat()
            remaining_seconds = max(0, int((meeting_dt_tz - now_dt).total_seconds()))
            result['countdown_minutes'] = (remaining_seconds + 59) // 60
            days, rem = divmod(remaining_seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes = rem // 60
            result['countdown_text'] = f"{days}天 {hours:02d}小时 {minutes:02d}分钟"
    except Exception:
        return result

    return result


def fetch_fed_rate_monitor(opener) -> dict:
    """美联储利率观测器：多源抓取 + 优雅降级"""
    result = fetch_cme_fedwatch(opener)
    if result.get('probabilities') and result.get('meeting_iso'):
        return result

    source_url = "https://cn.investing.com/central-banks/fed-rate-monitor"
    result = {
        "source_url": source_url,
        "meeting_text": "2026年10月29日 02:00",
        "meeting_iso": "2026-10-29T02:00:00+08:00",
        "countdown_minutes": None,
        "countdown_text": "暂无倒计时",
        "futures_price": "96.105",
        "probabilities": [],
        "table_rows": [],
        "update_text": f"{datetime.now().strftime('%Y年%m月%d日 %H:%M')} CST",
        "source_name": "Investing.com",
    }

    try:
        req = urllib.request.Request(source_url, headers={
            **DEFAULT_HEADERS,
            "Referer": "https://cn.investing.com/"
        })
        with opener.open(req, timeout=6) as resp:
            html_content = resp.read().decode('utf-8', errors='ignore')

        m = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*(\d{1,2}:\d{2})', html_content)
        if m:
            y, mo, d = map(int, m.group(1, 2, 3))
            hh, mm = map(int, m.group(4).split(':'))
            result['meeting_text'] = f'{y}年{mo:02d}月{d:02d}日 {hh:02d}:{mm:02d}'
            result['meeting_iso'] = f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:00+08:00"

        fm = re.search(r'期货价格\s*[:：]?\s*([0-9]+(?:\.\d+)?)', html_content)
        if fm:
            result['futures_price'] = fm.group(1)

        up_m = re.search(r'更新[:：]\s*([^\r\n<]+)', html_content)
        if up_m:
            result['update_text'] = f"更新: {up_m.group(1).strip()}"

        tables = _cme_html_tables(html_content)
        for tbl in tables:
            rows = []
            for r in tbl:
                if len(r) >= 4 and re.search(r'\d+\.\d+\s*-\s*\d+\.\d+', r[0]):
                    curr_val = r[1].replace('%', '').strip()
                    prev_d = r[2].replace('%', '').strip()
                    prev_w = r[3].replace('%', '').strip()
                    rows.append({
                        'rate': r[0].strip(),
                        'current': curr_val if curr_val not in ['', '-'] else '—',
                        'prev_day': prev_d if prev_d not in ['', '-'] else '—',
                        'prev_week': prev_w if prev_w not in ['', '-'] else '—',
                    })
            if rows:
                result['table_rows'] = rows
                for item in rows:
                    if item['current'] not in ['—', '-', '']:
                        try:
                            result['probabilities'].append({
                                'rate': item['rate'],
                                'pct': float(item['current'])
                            })
                        except Exception:
                            pass
                break
    except Exception:
        pass

    if not result['table_rows']:
        result['meeting_text'] = "2026年10月29日 02:00"
        result['meeting_iso'] = "2026-10-29T02:00:00+08:00"
        result['futures_price'] = "96.105"
        result['table_rows'] = [
            {"rate": "3.50 - 3.75", "current": "—", "prev_day": "—", "prev_week": "28.0"},
            {"rate": "3.75 - 4.00", "current": "42.6", "prev_day": "44.9", "prev_week": "54.1"},
            {"rate": "4.00 - 4.25", "current": "57.4", "prev_day": "55.1", "prev_week": "18.0"}
        ]
        result['probabilities'] = [
            {"rate": "3.75 - 4.00", "pct": 42.6},
            {"rate": "4.00 - 4.25", "pct": 57.4}
        ]

    try:
        from datetime import timezone
        dt_target = datetime.fromisoformat(result['meeting_iso'])
        now_dt = datetime.now(timezone(timedelta(hours=8)))
        sec = max(0, int((dt_target - now_dt).total_seconds()))
        result['countdown_minutes'] = (sec + 59) // 60
        days, rem = divmod(sec, 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        result['countdown_text'] = f"{days}天 {hours:02d}小时 {mins:02d}分钟"
    except Exception:
        pass

    return result

def analyze_fund_metrics(valid_data, end_date, cutoff_date, is_qdii=False):
    data_all = sorted(valid_data, key=lambda x: x["date"])
    if not data_all: return None
    data_cutoff = [item for item in data_all if item["date"] >= cutoff_date]
    if not data_cutoff: data_cutoff = data_all

    latest_nav = data_all[-1]["nav"]
    latest_date = data_all[-1]["date"]

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    if weekday == 5: target_friday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    elif weekday == 6: target_friday = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    else: target_friday = today_str

    is_weekend = (weekday >= 5)
    today_gain = None

    if is_qdii:
        if len(data_all) >= 2 and data_all[-2]["nav"] > 0:
            today_gain = ((latest_nav / data_all[-2]["nav"]) - 1) * 100.0
    else:
        if is_weekend:
            if len(data_all) >= 2 and latest_date <= target_friday and data_all[-2]["nav"] > 0:
                today_gain = ((latest_nav / data_all[-2]["nav"]) - 1) * 100.0
        else:
            if len(data_all) >= 2 and data_all[-2]["nav"] > 0:
                today_gain = ((latest_nav / data_all[-2]["nav"]) - 1) * 100.0

    max_drawdown = 0.0
    peak_nav = data_cutoff[0]["nav"]
    trough_nav = data_cutoff[0]["nav"]
    peak_date = data_cutoff[0]["date"]
    trough_date = data_cutoff[0]["date"]
    temp_peak = data_cutoff[0]["nav"]
    temp_peak_date = data_cutoff[0]["date"]

    for item in data_cutoff:
        nav = item["nav"]
        date = item["date"]
        if nav > temp_peak:
            temp_peak = nav
            temp_peak_date = date
        drawdown = (temp_peak - nav) / temp_peak if temp_peak > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            peak_nav = temp_peak
            peak_date = temp_peak_date
            trough_nav = nav
            trough_date = date

    if max_drawdown == 0: recovery_rate = 100.0
    elif peak_nav == trough_nav: recovery_rate = 0.0
    else: recovery_rate = ((latest_nav - trough_nav) / (peak_nav - trough_nav)) * 100.0

    min_dt = datetime.strptime(trough_date, '%Y-%m-%d')
    latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
    recovery_days = (latest_dt - min_dt).days
    rebound_gain = ((latest_nav - trough_nav) / trough_nav) * 100.0 if trough_nav > 0 else 0.0

    def add_months(d, months):
        month = d.month - 1 + months
        year = d.year + month // 12
        month = month % 12 + 1
        day = min(d.day, monthrange(year, month)[1])
        return d.replace(year=year, month=month, day=day)

    def calc_gain(days=None, months=None, ytd=False):
        latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
        if ytd: target_dt = latest_dt.replace(month=1, day=1)
        elif days: target_dt = latest_dt - timedelta(days=days)
        elif months: target_dt = add_months(latest_dt, -months)
        else: return None
            
        target_date_str = target_dt.strftime('%Y-%m-%d')
        base_nav = None
        for item in data_all:
            if item['date'] >= target_date_str:
                base_nav = item['nav']
                break
        if base_nav is not None and base_nav > 0:
            return ((latest_nav / base_nav) - 1) * 100.0
        return None

    return {
        "max_nav": peak_nav, "max_nav_date": peak_date, "min_nav": trough_nav, "min_nav_date": trough_date,
        "latest_nav": latest_nav, "latest_date": latest_date, "max_drawdown": max_drawdown * 100.0,
        "recovery_rate": recovery_rate, "recovery_days": recovery_days, "rebound_gain": rebound_gain,
        "today_gain": today_gain, "week_gain": calc_gain(days=7), "month_gain": calc_gain(months=1),
        "quarter_gain": calc_gain(months=3), "half_year_gain": calc_gain(months=6), "year_gain": calc_gain(months=12),
        "ytd_gain": calc_gain(ytd=True)
    }

def generate_html_report(results, start_date, end_date, today_str, metrics, index_valuations, fed_monitor=None, is_debug_mode=False, filename="fund_drawdown_dashboard.html", index_annual_data=None):
    CPO_CODES = {"022365", "540010", "002112", "011892", "021528", "009645", "011370", "011452", "016371", "001956", "016234", "016173", "006616", "018291", "020661", "017462", "001438", "008984", "180031", "004320", "027063"}
    STORAGE_CODES = {"025500", "025209", "018816", "014320"}
    SEMICONDUCTOR_CODES = {"024418", "024975", "020640", "019633", "024424", "017811", "013841", "007491", "020629", "017747", "026633", "162214", "007343", "018777"}
    AI_CODES = {"024663", "024726", "023286", "023408", "025506", "025493", "025653", "005963", "014162", "011840", "024412", "024775", "026613", "023551", "024561"}
    GRID_CODES = {"025857", "023639", "023675", "019411", "167002", "020425", "002164", "017133", "017042", "026681", "016387", "025833", "011172", "001665", "018919"}
    ROBOT_CODES = {"016531", "018345", "020482", "018125", "007519", "014243", "018957", "003835", "014939", "008998", "004233", "008182", "017968", "024648"}
    INDEX_SET_LOCAL = {"NDX", "SPX", "SOX", "SOXL", "XLK"}
    COMMODITIES_LOCAL = {"XAU", "AUM", "XAG", "BRENT", "CAD"}
    CRYPTO_LOCAL = {"BTC", "ETH", "SOL", "BNB"}
    col_count = 22

    # ================= 【新增】止盈三信号逻辑计算 =================
    vix_val = metrics['vix']['val']
    fng_val = metrics['fng']['score']
    
    qqq_pe_val = 0.0
    for item in index_valuations:
        if item['name'] == '纳指100':
            try:
                qqq_pe_val = float(item['pe'])
            except (ValueError, TypeError):
                qqq_pe_val = 0.0
            break

    vix_trigger = (0 < vix_val < 14)
    pe_trigger = (qqq_pe_val > 35)
    fng_trigger = (fng_val > 80)
    trigger_count = sum([vix_trigger, pe_trigger, fng_trigger])

    if trigger_count == 3:
        risk_level = "💣 极度疯狂"
        risk_color = "#d93025"
        strategy = "执行大额止盈。至少将仓位降至 50% 以下，或通过定投式分批卖出，保留大量现金等待暴跌后的抄底机会。"
    elif trigger_count == 2:
        risk_level = "🚨 中度危险"
        risk_color = "#e67e22"
        strategy = "执行一档止盈。比如减掉 20% 仓位，锁定部分利润。"
    elif trigger_count == 1:
        risk_level = "⚠️ 轻度过热"
        risk_color = "#fbbc04"
        strategy = "持股不动，或者仅对涨幅过夸张的个股进行微调。"
    else:
        risk_level = "🟢 相对安全"
        risk_color = "#188038"
        strategy = "尚未触发止盈信号，正常持有或逢低买入。"

    # 生成止盈信号面板的 HTML（默认折叠）
    stop_profit_html = f"""
    <div class="metric-card" style="grid-column: 1 / -1; margin-top: 10px; border-left: 4px solid {risk_color};">
        <div class="metric-header" id="stopProfitHeader" style="border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 0; cursor: pointer; user-select: none;">
            <span style="font-size: 16px; font-weight: bold; color: var(--header-text); display: flex; align-items: center; gap: 8px;">
                <span id="stopProfitToggleIcon" style="font-size: 11px; color: var(--footer-text); transition: transform 0.2s;">▶</span>
                🚦 美股止盈三信号共振监控
            </span>
            <span class="metric-tag" style="background: {risk_color}20; color: {risk_color}; border: 1px solid {risk_color}80;">
                {risk_level} (触发 {trigger_count}/3 指标)
            </span>
        </div>

        <div id="stopProfitBody" style="display: none; margin-top: 12px;">
            <div class="stop-profit-grid">
                <div class="stop-profit-item">
                    <div class="stop-profit-title">VIX 标普恐慌指数</div>
                    <div class="stop-profit-value" style="color: {risk_color if vix_trigger else 'var(--link-color)'};">
                        {vix_val if vix_val > 0 else '--'}
                    </div>
                    <div class="stop-profit-rules">
                        <div style="color: {risk_color if vix_trigger else 'inherit'}; font-weight: { 'bold' if vix_trigger else 'normal' };">VIX &lt; 14: 开始关注止盈</div>
                        <div>VIX 15-20: 正常持有</div>
                        <div>VIX &gt; 30: 重点考虑买入</div>
                    </div>
                </div>

                <div class="stop-profit-item">
                    <div class="stop-profit-title">QQQ 纳指100市盈率</div>
                    <div class="stop-profit-value" style="color: {risk_color if pe_trigger else 'var(--link-color)'};">
                        {qqq_pe_val if qqq_pe_val > 0 else '--'}
                    </div>
                    <div class="stop-profit-rules">
                        <div style="color: {risk_color if pe_trigger else 'inherit'}; font-weight: { 'bold' if pe_trigger else 'normal' };">PE &gt; 35: 进入止盈区</div>
                        <div>PE 30-35: 偏贵</div>
                        <div>PE &lt; 30: 估值合理</div>
                    </div>
                </div>

                <div class="stop-profit-item">
                    <div class="stop-profit-title">Fear &amp; Greed 恐惧贪婪</div>
                    <div class="stop-profit-value" style="color: {risk_color if fng_trigger else 'var(--link-color)'};">
                        {fng_val if fng_val > 0 else '--'}
                    </div>
                    <div class="stop-profit-rules">
                        <div style="color: {risk_color if fng_trigger else 'inherit'}; font-weight: { 'bold' if fng_trigger else 'normal' };">&gt; 80: 考虑分批止盈</div>
                        <div>50-75: 正常持有</div>
                        <div>&lt; 25: 重点寻找机会</div>
                    </div>
                </div>
            </div>

            <div style="font-size: 12px; color: var(--footer-text); margin: 16px 0 8px 0;">
                💡 单一指标有时会出现“钝化”（比如 CNN 指数在贪婪区卡了一个月，股市还在涨）。为了提高准确率，建议使用三共振法则：
            </div>

            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; min-width: 600px;">
                    <thead>
                        <tr style="background: var(--header-bg); color: var(--header-text);">
                            <th style="padding: 10px; border-bottom: 1px solid var(--border); width: 20%;">触发条件数量</th>
                            <th style="padding: 10px; border-bottom: 1px solid var(--border); width: 20%;">风险等级</th>
                            <th style="padding: 10px; border-bottom: 1px solid var(--border);">对应操作策略</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: { 'rgba(251, 188, 4, 0.1)' if trigger_count == 1 else 'transparent' }; border-left: 3px solid {'#fbbc04' if trigger_count == 1 else 'transparent'}; transition: all 0.3s ease;">
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: var(--text);">仅 1 个指标触发止盈区</td>
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: #fbbc04; font-weight: bold;">⚠️ 轻度过热</td>
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: var(--text);">持股不动，或者仅对涨幅过夸张的个股进行微调。</td>
                        </tr>
                        <tr style="background: { 'rgba(230, 126, 34, 0.1)' if trigger_count == 2 else 'transparent' }; border-left: 3px solid {'#e67e22' if trigger_count == 2 else 'transparent'}; transition: all 0.3s ease;">
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: var(--text);">有 2 个指标同时触发</td>
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: #e67e22; font-weight: bold;">🚨 中度危险</td>
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: var(--text);">执行一档止盈。比如减掉 20% 仓位，锁定部分利润。</td>
                        </tr>
                        <tr style="background: { 'rgba(217, 48, 37, 0.1)' if trigger_count == 3 else 'transparent' }; border-left: 3px solid {'#d93025' if trigger_count == 3 else 'transparent'}; transition: all 0.3s ease;">
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: var(--text);">3 个指标全满 (VIX &lt; 14 + QQQ PE &gt; 35 + CNN &gt; 80)</td>
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: #d93025; font-weight: bold;">💣 极度疯狂</td>
                            <td style="padding: 10px; border-bottom: 1px solid var(--border); color: var(--text);">执行大额止盈。至少将仓位降至 50% 以下，或通过定投式分批卖出，保留大量现金等待暴跌后的抄底机会。</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div style="background: {risk_color}15; border: 1px dashed {risk_color}; border-radius: 8px; padding: 12px; text-align: center; margin-top: 16px;">
                <div style="font-weight: bold; color: {risk_color}; font-size: 14px;">
                    📢 当前市场诊断：触发 <span style="font-size: 18px;">{trigger_count}</span> 个止盈信号 ➔ <span style="font-size: 18px;">{risk_level}</span>
                </div>
                <div style="font-weight: normal; font-size: 12px; color: var(--text); margin-top: 6px;">
                    操作建议：{strategy}
                </div>
            </div>
        </div>
    </div>
    """
    # ================= 止盈三信号逻辑结束 =================

    def date_to_label(date_str):
        if 'Q' in date_str: return date_str
        if date_str.isdigit() and len(date_str) == 4: return f"{date_str}年报"
        try:
            year, month, _ = date_str.split('-')
            return f"{year}Q{(int(month) - 1) // 3 + 1}"
        except Exception: return date_str

    def quarter_to_end_date(date_str):
        if not date_str: return ""
        if re.match(r'^\d{4}-\d{2}-\d{2}$', str(date_str)): return date_str
        m = re.match(r'^(\d{4})Q([1-4])$', str(date_str), re.I)
        if m:
            end_map = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
            return f"{m.group(1)}-{end_map[int(m.group(2))]}"
        return ""

    nav_data_json = {}
    fund_names_json = {}
    for r in results:
        fund_names_json[r['code']] = r['name']
        if 'nav_data' in r and r['nav_data']:
            nav_data_json[r['code']] = {
                'dates': [item['date'] for item in r['nav_data']],
                'navs': [item['nav'] for item in r['nav_data']]
            }

    rows_html = ""
    for r in results:
        INDEX_URL_MAP = {
            "NDX":  "https://quote.eastmoney.com/gb/zsNDX100.html",
            "SPX":  "https://quote.eastmoney.com/gb/zsSPX.html",
            "SOX":  "https://cn.investing.com/indices/phlx-semiconductor",
            "SOXL": "https://quote.eastmoney.com/us/SOXL.html",
            "XLK":  "https://quote.eastmoney.com/us/XLK.html",
            "XAU":  "https://cn.investing.com/currencies/xau-usd",
            "AUM":  "https://quote.eastmoney.com/qihuo/aum.html",
            "XAG":  "https://cn.investing.com/currencies/xag-usd",
            "BTC":  "https://www.tradingview.com/symbols/BTCUSD/",
            "ETH":  "https://www.tradingview.com/symbols/ETHUSD/",
            "SOL":  "https://www.tradingview.com/symbols/SOLUSD/",
            "BNB":  "https://www.tradingview.com/symbols/BNBUSD/"
        }
        fund_url = INDEX_URL_MAP.get(r['code'], f"https://fund.eastmoney.com/{r['code']}.html")

        max_dd_pct = min(max(r['max_drawdown'], 0), 100)
        rec_pct = max(0, min(r['recovery_rate'], 100))
        reb_pct = min(r['rebound_gain'], 100)
        limit_display = r.get('buy_limit', '无限额')
        limit_val = r.get('buy_limit_val', -1)
        max_nav_display = f"{r['max_nav']:.4f} ({r['max_nav_date']})"
        min_nav_display = f"{r['min_nav']:.4f} ({r['min_nav_date']})"

        redemption_text = r.get('fee_redemption', '未知')
        if redemption_text and redemption_text != "未知":
            parts = redemption_text.split(" | ")
            highlighted_parts = [re.sub(r'(\d+\.\d+%)', r'<span class="highlight-rate">\1</span>', p) for p in parts]
            redemption_lines = "<br>".join(highlighted_parts)
        else:
            redemption_lines = redemption_text or "未知"

        def format_gain(val): return f"{val:.2f}%" if val is not None else '-'
        def gain_class(val): return 'gain-positive' if (val and val > 0) else ('gain-negative' if (val and val < 0) else '')

        if r['code'] in CPO_CODES: group = "cpo"; macro_category = "a_share"
        elif r['code'] in STORAGE_CODES: group = "storage"; macro_category = "a_share"
        elif r['code'] in SEMICONDUCTOR_CODES: group = "semiconductor"; macro_category = "a_share"
        elif r['code'] in AI_CODES: group = "ai"; macro_category = "a_share"
        elif r['code'] in GRID_CODES: group = "grid"; macro_category = "a_share"
        elif r['code'] in ROBOT_CODES: group = "robot"; macro_category = "a_share"
        elif r['code'] in COMMODITIES_LOCAL: group = "commodities"; macro_category = "other"
        elif r['code'] in CRYPTO_LOCAL: group = "crypto"; macro_category = "other"
        elif r['code'] in INDEX_SET_LOCAL: group = "index"; macro_category = "other"
        elif r['code'] in NDX_PASSIVE_CODES: group = "ndx_passive"; macro_category = "us_share"
        elif r['code'] in SPX_PASSIVE_CODES: group = "spx_passive"; macro_category = "us_share"
        else: group = "us_active"; macro_category = "us_share"

        nav_display_html = f'<span class="highlight-special-nav">{r["latest_nav"]:.4f}</span>' if group in ["commodities", "currency", "crypto", "index"] else f'{r["latest_nav"]:.4f}'
        holdings_history = r.get('holdings', [])
        today_gain_val = r.get('today_gain', None)
        latest_date = r['latest_date']
        if today_gain_val is not None:
            today_gain_display = format_gain(today_gain_val) + f' <span class="gain-date">({latest_date})</span>'
            today_gain_class = gain_class(today_gain_val)
            today_data_val = today_gain_val
        else:
            today_gain_display = "--"
            today_gain_class = ''
            today_data_val = -9999

        fee_src = str(r.get('fee_source', ''))
        fee_pur = str(r.get('fee_purchase', ''))
        if fee_src and "%" not in fee_src and fee_src != "0.00": fee_src += "%"
        if fee_pur and "%" not in fee_pur and fee_pur != "0.00": fee_pur += "%"

        if fee_src and fee_pur and fee_src != fee_pur:
            fee_purchase_html = f'<s style="color:var(--footer-text); font-size:10px;">{fee_src}</s><br><span style="color:#d93025; font-weight:600;">{fee_pur}</span>'
            clean_pur = fee_pur.strip('%')
            fee_pur_val = float(clean_pur) if clean_pur.replace('.', '', 1).isdigit() else 999.0
        else:
            fee_purchase_html = fee_pur if fee_pur else '--'
            clean_pur = fee_pur.strip('%') if fee_pur else ''
            fee_pur_val = float(clean_pur) if clean_pur.replace('.', '', 1).isdigit() else 999.0

        rows_html += f"""
        <tr data-group="{group}" data-macro="{macro_category}" data-buy-status="{r.get('buy_status', '')}" class="fund-row" data-code="{r['code']}">
            <td class="fav-col" data-val="0"><button class="star-btn" data-code="{r['code']}" title="点击添加/取消自选">☆</button></td>
            <td class="code" data-val="{r['code']}">{r['code']}</td>
            <td class="name" data-val="{r['name']}">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
                    <a href="{fund_url}" target="_blank" title="点击查看行情/概况" style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{r['name']}</a>
                    <button class="dca-btn" data-code="{r['code']}" title="启动定投回测测算小工具">📊 定投</button>
                </div>
                <div class="redemption-sub" style="white-space: normal; line-height: 1.6;">赎回:<br><span class="highlight-redemption">{redemption_lines}</span></div>
            </td>
            <td data-val="{r['scale_val']}" class="highlight-val">{r['scale']}</td>
            <td data-val="{r['fee_val']}">{r['fee_total']} <span class="fee-sub">(管:{r['fee_manage']}/托:{r['fee_custody']}/销:{r['fee_sales']})</span></td>
            <td data-val="{fee_pur_val}">{fee_purchase_html}</td>
            <td data-val="{limit_val}">{r.get('buy_status', '--')}<div class="fee-sub">{limit_display}</div></td>
            <td data-val="{r['max_nav']}">{max_nav_display}</td>
            <td data-val="{r['min_nav']}">{min_nav_display}</td>
            <td data-val="{r['latest_nav']}">{nav_display_html}</td>
            <td class="metric-red" data-val="{r['max_drawdown']}">
                <div class="progress-container">
                    <div class="progress-bar bar-red" style="width: {max_dd_pct}%;">
                        <span>{r['max_drawdown']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td class="metric-green" data-val="{r['rebound_gain']}">
                <div class="progress-container">
                    <div class="progress-bar bar-green" style="width: {reb_pct}%;">
                        <span>{r['rebound_gain']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td data-val="{r['recovery_rate']}">
                <div class="progress-container">
                    <div class="progress-bar bar-blue" style="width: {rec_pct}%;">
                        <span>{r['recovery_rate']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td data-val="{r['recovery_days']}">{r['recovery_days']} 天</td>
            <td data-val="{today_data_val}" class="{today_gain_class}">{today_gain_display}</td>
            <td data-val="{r['week_gain'] if r['week_gain'] is not None else -9999}" class="{gain_class(r['week_gain'])}">{format_gain(r['week_gain'])}</td>
            <td data-val="{r['month_gain'] if r['month_gain'] is not None else -9999}" class="{gain_class(r['month_gain'])}">{format_gain(r['month_gain'])}</td>
            <td data-val="{r['quarter_gain'] if r['quarter_gain'] is not None else -9999}" class="{gain_class(r['quarter_gain'])}">{format_gain(r['quarter_gain'])}</td>
            <td data-val="{r['half_year_gain'] if r['half_year_gain'] is not None else -9999}" class="{gain_class(r['half_year_gain'])}">{format_gain(r['half_year_gain'])}</td>
            <td data-val="{r['year_gain'] if r['year_gain'] is not None else -9999}" class="{gain_class(r['year_gain'])}">{format_gain(r['year_gain'])}</td>
            <td data-val="{r['ytd_gain'] if r['ytd_gain'] is not None else -9999}" class="{gain_class(r['ytd_gain'])}">{format_gain(r['ytd_gain'])}</td>
            <td class="dca-col" data-val="-9999">--</td>
        </tr>
        """

        if holdings_history:
            sorted_holdings = sorted(holdings_history, key=lambda x: x['date'], reverse=True)
            display_holdings = sorted_holdings[:3]
            holdings_html = ""
            for i, period in enumerate(display_holdings):
                date_str = period['date']
                holdings_list = period['holdings']
                label = date_to_label(date_str)
                end_date_str = quarter_to_end_date(date_str)
                end_date_html = f'<span class="quarter-end">截止至：{end_date_str}</span>' if end_date_str else ""
                prev_period = sorted_holdings[i+1] if i+1 < len(sorted_holdings) else None
                prev_holdings_dict = {h['name']: h['ratio'] for h in prev_period['holdings']} if prev_period else {}
                stocks_html = ""
                total_ratio = 0.0
                if holdings_list:
                    for h in holdings_list:
                        name = h['name']
                        ratio = h['ratio']
                        total_ratio += ratio
                        change_text = ''
                        change_class = ''
                        if name in prev_holdings_dict:
                            diff = ratio - prev_holdings_dict[name]
                            if abs(diff) < 0.01: change_text = '持平'; change_class = ''
                            elif diff > 0.3: change_text = f'加仓 {diff:.2f}%'; change_class = 'change-add'
                            elif diff > 0: change_text = f'↑{diff:.2f}%'; change_class = 'change-up'
                            elif diff < -0.3: change_text = f'减仓 {abs(diff):.2f}%'; change_class = 'change-sub'
                            else: change_text = f'↓{abs(diff):.2f}%'; change_class = 'change-down'
                        else:
                            change_text = '新增'; change_class = 'change-new'
                        stocks_html += f'''
                        <div class="stock-item">
                            <span class="stock-name">{name}</span>
                            <span class="stock-ratio">{ratio:.2f}%</span>
                            <span class="stock-change {change_class}">{change_text}</span>
                        </div>
                        '''
                    stocks_html += f'''
                    <div class="stock-item stock-total">
                        <span class="stock-name">前十大合计</span>
                        <span class="stock-ratio">{total_ratio:.2f}%</span>
                        <span class="stock-change"></span>
                    </div>
                    '''
                else:
                    stocks_html = '<div style="color: var(--footer-text); padding: 10px 0;">暂无持仓明细</div>'
                holdings_html += f"""
                <div class="quarter-card">
                    <div class="quarter-label">
                        <span class="quarter-title">{label}</span>
                        {end_date_html}
                    </div>
                    <div class="quarter-stocks">{stocks_html}</div>
                </div>
                """
        else:
            holdings_html = """
            <div class="quarter-card empty-holdings-placeholder" style="grid-column: span 3;">
                <div class="quarter-label"><span class="quarter-title">前十大持仓</span></div>
                <div style="flex:1; display:flex; align-items:center; justify-content:center; color:var(--footer-text); font-size:12px;">
                    暂无持仓披露数据
                </div>
            </div>
            """

        holder_data = r.get("holder_struct")
        if holder_data and ("inst" in holder_data) and ("indiv" in holder_data):
            inst_r = holder_data["inst"]
            indiv_r = holder_data["indiv"]
            h_date = holder_data.get("date", "--")
            
            holders_arr = [
                {"name": "机构持有", "ratio": inst_r},
                {"name": "个人持有", "ratio": indiv_r}
            ]
            holders_json_str = json.dumps(holders_arr, ensure_ascii=False)
            
            pie_card_html = f"""
            <div class="quarter-card holder-card" style="grid-column: span 1;">
                <div class="quarter-label"><span class="quarter-title">持有人结构</span></div>
                <div class="holder-pie-wrapper">
                    <canvas id="holder-chart-{r['code']}" data-holders='{holders_json_str}'></canvas>
                </div>
                <div class="holder-date-sub">披露日期: {h_date}</div>
            </div>
            """
        else:
            pie_card_html = f"""
            <div class="quarter-card holder-card" style="grid-column: span 1;">
                <div class="quarter-label"><span class="quarter-title">持有人结构</span></div>
                <div style="flex:1; display:flex; align-items:center; justify-content:center; color:var(--footer-text); font-size:11px;">
                    暂无结构数据
                </div>
                <div class="holder-date-sub">披露日期: --</div>
            </div>
            """

        c_info = r.get("countries_info", {})
        countries_data = c_info.get("countries", [])
        c_date = c_info.get("date", "--")
        countries_json_str = json.dumps(countries_data, ensure_ascii=False)
        if countries_data:
            country_card_html = f"""
            <div class="quarter-card country-card">
                <div class="quarter-label"><span class="quarter-title">国家/地区分布</span></div>
                <div class="country-pie-wrapper">
                    <canvas id="country-chart-{r['code']}" data-countries='{countries_json_str}'></canvas>
                </div>
                <div class="country-date-sub">披露日期: {c_date}</div>
            </div>
            """
        else:
            country_card_html = f"""
            <div class="quarter-card country-card">
                <div class="quarter-label"><span class="quarter-title">国家/地区分布</span></div>
                <div style="flex:1; display:flex; align-items:center; justify-content:center; color:var(--footer-text); font-size:11px;">
                    暂无配置数据
                </div>
                <div class="country-date-sub">披露日期: --</div>
            </div>
            """

        chart_html = f"""
        <div class="chart-container" id="chart-container-{r['code']}">
            <div class="chart-controls">
                <button class="period-btn active" data-period="week" data-code="{r['code']}">近一周</button>
                <button class="period-btn" data-period="month" data-code="{r['code']}">近一月</button>
                <button class="period-btn" data-period="quarter" data-code="{r['code']}">近三月</button>
                <button class="period-btn" data-period="half" data-code="{r['code']}">近半年</button>
                <button class="period-btn" data-period="year" data-code="{r['code']}">近一年</button>
                <button class="period-btn" data-period="ytd" data-code="{r['code']}">今年内</button>
            </div>
            <canvas id="chart-{r['code']}" width="400" height="200"></canvas>
        </div>
        """

        rows_html += f"""
        <tr class="holding-row" data-code="{r['code']}">
            <td colspan="{col_count}" style="padding: 8px 20px; background-color: var(--hover-bg); font-size: 12px; color: var(--footer-text);">
                <div class="holdings-wrapper">
                    <div class="holdings-container">
                        {holdings_html}
                        {pie_card_html}
                    </div>
                    <div class="right-chart-wrapper">
                        {country_card_html}
                        {chart_html}
                    </div>
                </div>
            </td>
        </tr>
        """

    empty_row = f"""
        <tr id="empty-row" style="display:none;">
            <td colspan="{col_count}" style="text-align:center; padding:30px; color: var(--footer-text);">
                该分类暂无基金，敬请期待
            </td>
        </tr>
    """

    friend_link_categories = [
        {
            "category": "📊 估值与数据",
            "links": [
                {"name": "蛋卷估值中心", "url": "https://danjuanfunds.com/djmodule/value-center?channel=1300100141", "desc": "全市场指数估值与定投参考"},
                {"name": "History of Market", "url": "https://historyofmarket.com/", "desc": "美股百年历史数据与市场统计"},
                {"name": "Morningstar 晨星中国", "url": "https://www.morningstar.cn/", "desc": "全球权威基金评级与研究报告"},
                {"name": "WiseETF", "url": "https://www.wise-etf.com/", "desc": "美股ETF/QDII基金估值与溢价监控"},
                {"name": "纳指估值助手", "url": "https://nsdk.top/", "desc": "纳指基金估值与持仓参考"},
            ]
        },
        {
            "category": "🔬 基金分析与工具",
            "links": [
                {"name": "基金决策宝", "url": "https://jjpro.cn/", "desc": "基金组合分析与投研决策辅助工具"},
                {"name": "QDII申购限额监控", "url": "https://pmtools.com.cn/qdii", "desc": "QDII基金数据分析与投资参考"},
                {"name": "定投估值计算机", "url": "https://btcdca.me/", "desc": "多资产定投策略与估值评分"},
                {"name": "股查查", "url": "https://guchacha.com/", "desc": "专业的企业/股票基本面查询工具"},
                {"name": "WISE HOLD", "url": "https://www.wise-hold.com/", "desc": "追踪机构持仓与政商名人投资动向"},
            ]
        },
        {
            "category": "📰 资讯与行情",
            "links": [
                {"name": "FiNews 美股日报", "url": "https://finews.elsetech.app/", "desc": "每日美股盘后总结与新闻聚合"},
                {"name": "Yahoo 财经香港", "url": "https://hk.finance.yahoo.com/", "desc": "港股/美股实时行情与财经资讯"},
            ]
        },
    ]
    
    friend_cards_html = ""
    for cat in friend_link_categories:
        cards_list = []
        for link in cat['links']:
            try:
                _domain = urllib.parse.urlparse(link['url']).netloc
            except Exception:
                _domain = ""
            _icon_url = f"https://www.google.com/s2/favicons?domain={_domain}&sz=64" if _domain else ""
            cards_list.append(f"""
        <a href="{link['url']}" target="_blank" class="metric-card friend-card" style="text-decoration: none; display: flex; flex-direction: column; justify-content: center; cursor: pointer;">
            <div class="friend-card-head">
                <img src="{_icon_url}" alt="{link['name']}" class="friend-logo" loading="lazy" onerror="this.style.display='none';">
                <span class="friend-name">{link['name']}</span>
                <span class="friend-arrow">↗</span>
            </div>
            <div class="metric-desc" style="border-top: none; padding-top: 0; margin-top: 4px; font-size: 11px; color: var(--footer-text);">
                {link['desc']}
            </div>
        </a>
        """)
        links_html = "".join(cards_list)
        friend_cards_html += f"""
        <div class="friend-category-block">
            <h4 class="friend-category-title">{cat['category']}</h4>
            <div class="friend-links-grid">{links_html}</div>
        </div>
        """

    index_source_url = "https://danjuanfunds.com/screw/valuation-table"
    index_source_link_html = (
        f'<a href="{index_source_url}" target="_blank" '
        f'style="color:var(--link-color); text-decoration:none;" '
        f'title="点击跳转至蛋卷指数估值表">（数据源：蛋卷）↗</a>'
    )
    index_cards_html = ""
    for item in index_valuations:
        ticker_html = f'<span style="font-size: 13px; color: var(--footer-text); font-weight: normal; margin-left: 4px;">({item["ticker"]})</span>' if item["ticker"] else ""
        index_cards_html += f"""
        <div class="metric-card">
            <div class="metric-header">
                <span style="font-size: 18px; font-weight: 800; color: var(--text); display: flex; align-items: baseline;">
                    {item['name'].split('（')[0]} {ticker_html}
                </span>
                <span class="metric-tag" style="background:rgba(0,0,0,0.05); color:{item['color']};">{item['status']}</span>
            </div>
            <div class="metric-body" style="margin: 12px 0 6px 0;">
                <span class="metric-value" style="color:var(--link-color); font-size:22px;">PE: {item['pe']}</span>
            </div>
            <div class="metric-desc" style="border-top: none; padding-top: 0;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px;">
                    <span>历史分位</span>
                    <strong style="color:var(--text);">{item['pct']}</strong>
                </div>
                <div style="width: 100%; height: 6px; background-color: var(--progress-track); border-radius: 3px; overflow: hidden;">
                    <div style="width: {item['pct_raw']}%; height: 100%; background-color: {item['color']}; border-radius: 3px; transition: width 1s ease-in-out;"></div>
                </div>

            </div>
        </div>
        """

    # ===== 计算指数历年回报数据的更新时间（优先取缓存文件 mtime）=====
    _index_annual_cache_file = os.path.join(CACHE_DIR, "index_annual.json")
    if os.path.exists(_index_annual_cache_file):
        try:
            _mtime = os.path.getmtime(_index_annual_cache_file)
            index_annual_update_time = ts_to_beijing(_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            index_annual_update_time = now_beijing().strftime("%Y-%m-%d %H:%M")
    else:
        index_annual_update_time = now_beijing().strftime("%Y-%m-%d %H:%M")

    # ===== 生成指数历年回报 HTML (优化版 v3) =====
    index_annual_html = ""
    if index_annual_data and isinstance(index_annual_data, dict):
        index_order = ANNUAL_INDEX_TARGETS
        index_annual_html = '<div class="index-annual-grid" style="margin: 20px 0; display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">'
        index_annual_html += '<div style="grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 0;">'
        index_annual_html += '<h3 style="margin: 0; font-size: 16px; color: var(--header-text); border-left: 4px solid var(--link-color); padding-left: 8px;">📈 指数历年回报 (2000年至今)</h3>'
        index_annual_html += '<span style="font-size: 12px; color: var(--footer-text);">数据来源: historyofmarket.com / 搜狐财经 / 腾讯财经</span>'
        index_annual_html += '</div>'

        for idx_name in index_order:
            idx_data = index_annual_data.get(idx_name)
            if not idx_data or not idx_data.get("data"):
                continue
            ticker = idx_data.get("ticker", "")
            yearly_data = idx_data["data"]
            if not yearly_data:
                continue

            max_abs_pct = max([abs(r.get("pct", 0)) for r in yearly_data] + [1.0])

            # ===== 计算统计信息 =====
            returns = [r.get("pct", 0) for r in yearly_data]
            max_gain = max(returns) if returns else 0.0
            max_loss = min(returns) if returns else 0.0
            pos_years = sum(1 for r in returns if r > 0)
            neg_years = sum(1 for r in returns if r < 0)
            cum = 1.0
            for r in returns:
                cum *= (1 + r / 100.0)
            n_years = len(returns)
            if n_years > 0 and cum > 0:
                ann_return = ((cum ** (1.0 / n_years)) - 1) * 100.0
            else:
                ann_return = 0.0
            ann_color = "#d93025" if ann_return >= 0 else "#188038"

            stats_html = f'''
            <div class="annual-stats-footer">
                <div class="annual-stat-item"><span class="annual-stat-label">最大涨幅</span><span class="annual-stat-value" style="color:#d93025;">+{max_gain:.2f}%</span></div>
                <div class="annual-stat-item"><span class="annual-stat-label">最大跌幅</span><span class="annual-stat-value" style="color:#188038;">{max_loss:.2f}%</span></div>
                <div class="annual-stat-item"><span class="annual-stat-label">正收益年份</span><span class="annual-stat-value">{pos_years} 年</span></div>
                <div class="annual-stat-item"><span class="annual-stat-label">负收益年份</span><span class="annual-stat-value">{neg_years} 年</span></div>
                <div class="annual-stat-item"><span class="annual-stat-label">年化收益率</span><span class="annual-stat-value" style="color:{ann_color};">{ann_return:+.2f}%</span></div>
            </div>
            '''

            bar_data_json = json.dumps(
                [{"year": r.get("year"), "pct": r.get("pct"), "close": r.get("close")} for r in yearly_data],
                ensure_ascii=False
            )

            index_annual_html += f'''
            <div class="metric-card" style="margin-bottom:0; padding: 16px; display: flex; flex-direction: column;">
                <div class="metric-header" style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:10px; margin-bottom:15px; flex-shrink: 0; flex-wrap: wrap; gap: 8px;">
                    <span style="font-size:15px; font-weight:700; color:var(--text);">
                        {idx_name} <span style="font-size:12px; color:var(--footer-text); font-weight:normal;">({ticker})</span>
                    </span>
                    <div style="display:flex; gap:6px;">
                        <button class="mode-toggle-btn" data-idx="{idx_name}" data-mode="card" onclick="toggleAnnualView('{idx_name}', 'card')">📋 卡片</button>
                        <button class="mode-toggle-btn active" data-idx="{idx_name}" data-mode="heatmap" onclick="toggleAnnualView('{idx_name}', 'heatmap')">🔥 热力图</button>
                        <button class="mode-toggle-btn" data-idx="{idx_name}" data-mode="bar" onclick="toggleAnnualView('{idx_name}', 'bar')">📊 柱状图</button>
                    </div>
                </div>
                <div id="annual-view-{idx_name}" class="annual-view-container" style="flex: 1; min-height: 0;">
            '''

            # --- 视图 1：卡片布局 (默认隐藏) ---
            index_annual_html += f'<div id="annual-card-{idx_name}" class="annual-mode-content" style="display:none;">'
            index_annual_html += '<div class="annual-card-grid">'
            for row in yearly_data:
                year = row.get("year", "")
                close_val = row.get("close")
                close_display = f"{close_val:,.2f}" if close_val is not None else "--"
                pct_val = row.get("pct", 0)
                if pct_val > 0:
                    pct_color = "#d93025"; pct_sign = "+"; bar_color = "#d93025"
                elif pct_val < 0:
                    pct_color = "#188038"; pct_sign = ""; bar_color = "#188038"
                else:
                    pct_color = "var(--text)"; pct_sign = "+"; bar_color = "#aaa"
                bar_width_half = min(abs(pct_val) / max_abs_pct * 50, 50)
                index_annual_html += f'''
                <div class="annual-year-row">
                    <span class="annual-year-col">{year}</span>
                    <span class="annual-points-col">{close_display}</span>
                    <span class="annual-pct-col" style="color: {pct_color};">{pct_sign}{pct_val:.2f}%</span>
                    <div class="annual-bar-col">
                        <div class="annual-zero-line"></div>
                        <div class="annual-bar-fill" style="background: {bar_color}; { 'left: 50%;' if pct_val >= 0 else 'right: 50%;' } width: {bar_width_half}%;"></div>
                    </div>
                </div>
                '''
            index_annual_html += '</div>'
            index_annual_html += stats_html
            index_annual_html += '</div>'

            # --- 视图 2：热力图布局 (默认显示) ---
            index_annual_html += f'<div id="annual-heatmap-{idx_name}" class="annual-mode-content" style="display:block;">'
            index_annual_html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(70px, 1fr)); gap: 6px;">'
            for row in yearly_data:
                year = row.get("year", "")
                close_val = row.get("close")
                close_heatmap_display = f"{close_val:,.2f}" if close_val is not None else "--"
                pct_val = row.get("pct", 0)
                # 提高最小 alpha，让文字始终有足够对比度
                if pct_val > 0:
                    alpha = min(0.72 + abs(pct_val) / 100.0 * 0.8, 0.98)
                    bg_color = f"rgba(190, 30, 30, {alpha:.2f})"
                elif pct_val < 0:
                    alpha = min(0.72 + abs(pct_val) / 100.0 * 0.8, 0.98)
                    bg_color = f"rgba(15, 110, 45, {alpha:.2f})"
                else:
                    bg_color = "rgba(110, 110, 110, 0.9)"
                # 去掉 text-shadow，改用更清晰的字重与颜色
                index_annual_html += f'''
                <div class="annual-heatmap-cell" style="background:{bg_color}; border-radius:4px; padding:6px 2px; text-align:center; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); cursor: default;">
                    <div style="font-size:10px; font-weight:600; color:#ffffff;">{year}</div>
                    <div style="font-size:13px; font-weight:800; color:#ffffff; letter-spacing: 0.2px;">{pct_val:+.2f}%</div>
                    <div style="font-size:9px; font-weight:500; color:rgba(255,255,255,0.92);">{close_heatmap_display}</div>
                </div>
                '''
            index_annual_html += '</div>'
            index_annual_html += stats_html
            index_annual_html += '</div>'

            # --- 视图 3：柱状图布局 (默认隐藏) ---
            index_annual_html += f'<div id="annual-bar-{idx_name}" class="annual-mode-content" style="display:none;">'
            index_annual_html += f'<div style="height: 280px; width: 100%; position: relative;"><canvas id="annual-bar-chart-{idx_name}" data-bar=\'{bar_data_json}\'></canvas></div>'
            index_annual_html += stats_html
            index_annual_html += '</div>'

            index_annual_html += '</div>'  # 关闭 annual-view-container
            index_annual_html += f'<div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--border); text-align: right; font-size: 11px; color: var(--footer-text);">📅 数据更新于: {index_annual_update_time}</div>'
            index_annual_html += '</div>'  # 关闭 metric-card
        index_annual_html += '</div>'
    else:
        index_annual_html = '<div style="margin:20px 0;"><div class="metric-card"><div class="metric-body"><span style="color:var(--footer-text);">暂无指数年度数据</span></div></div></div>'


    fed_monitor = fed_monitor or {}
    fed_source_url = fed_monitor.get("source_url", "https://www.cmegroup.com/cn-s/markets/interest-rates/cme-fedwatch-tool.html")
    fed_meeting_text = fed_monitor.get("meeting_text", "--")
    fed_meeting_iso = fed_monitor.get("meeting_iso", "")
    fed_countdown_text = fed_monitor.get("countdown_text", "暂无倒计时")
    fed_futures_price = fed_monitor.get("futures_price", "--")
    fed_probabilities = fed_monitor.get("probabilities", [])
    fed_table_rows = fed_monitor.get("table_rows", [])
    fed_update_text = fed_monitor.get("update_text", "--")

    fed_bar_html = ""
    for i, prob in enumerate(fed_probabilities):
        bar_class = "blue" if i == 0 else ("grey" if i == 1 else "green")
        pct = max(0.0, min(float(prob["pct"]), 100.0))
        fed_bar_html += f"""
        <div class="fed-bar-row">
            <div class="fed-bar-label">{prob['rate']}</div>
            <div class="fed-bar-track" style="background: transparent; display: flex; align-items: center; margin: 0;">
                <div class="fed-bar-fill {bar_class}" style="width: {pct:.1f}%;"></div>
                <span class="fed-bar-pct">{pct:.1f}%</span>
            </div>
        </div>
        """

    if fed_table_rows:
        fed_table_body = "".join(
            f"""<tr>
                <td>{row['rate']} <span style="color:#aaa;">📈</span></td>
                <td>{row['current']}{'' if row['current'] in ['—', '-'] else '%'}</td>
                <td>{row['prev_day']}{'' if row['prev_day'] in ['—', '-'] else '%'}</td>
                <td>{row['prev_week']}{'' if row['prev_week'] in ['—', '-'] else '%'}</td>
            </tr>"""
            for row in fed_table_rows
        )
    else:
        fed_table_body = '<tr><td colspan="4" style="text-align:center;">暂无历史概率数据</td></tr>'

    fed_countdown_js = ""
    if fed_meeting_iso:
        fed_countdown_js = f"""
        <script>
        (function() {{
            const meetingMs = new Date("{fed_meeting_iso}").getTime();
            const el = document.getElementById("fedCountdown");
            function updateFedCountdown() {{
                if (!el || !meetingMs) return;
                const diff = Math.max(0, meetingMs - Date.now());
                const totalMinutes = Math.ceil(diff / 60000);
                if (diff <= 0) {{
                    el.textContent = "会议已开始/已结束";
                    return;
                }}
                const days = Math.floor(diff / 86400000);
                const hours = Math.floor((diff % 86400000) / 3600000);
                const minutes = Math.floor((diff % 3600000) / 60000);
                el.textContent = `剩余 ${{days}}天 ${{String(hours).padStart(2, '0')}}小时 ${{String(minutes).padStart(2, '0')}}分钟（${{totalMinutes.toLocaleString()}} 分钟）`;
            }}
            updateFedCountdown();
            setInterval(updateFedCountdown, 1000);
        }})();
        </script>
        """

    fed_monitor_html = f"""
    <div class="fed-card">
        <div class="fed-title">
            下一次美国利率决议：{fed_meeting_text}
            <a href="{fed_source_url}" target="_blank" style="float:right; color:var(--link-color); font-size: 13px; font-weight: 500; text-decoration: none;">🔗 源数据直达 ↗</a>
        </div>
        <div style="text-align:center; margin: 4px 0 12px; padding: 8px 10px; background: var(--hover-bg); border-radius: 8px;">
            <div style="font-size: 11px; color: var(--footer-text); margin-bottom: 3px;">距离美国利率决议会议</div>
            <strong id="fedCountdown" style="font-size: 18px; color: var(--link-color);">{fed_countdown_text}</strong>
        </div>
        <div class="fed-info">
            会议时间: <strong>{fed_meeting_text}</strong><br>
            期货价格: <strong>{fed_futures_price}</strong>
        </div>
        {fed_bar_html if fed_bar_html else '<div style="padding: 12px 0; color: var(--footer-text);">暂无当前市场概率数据</div>'}

        <table class="fed-table" style="width: 100%; table-layout: fixed;">
            <thead>
                <tr>
                    <th style="width: 40%;">目标利率</th>
                    <th style="width: 20%;">目前</th>
                    <th style="width: 20%;">上一日</th>
                    <th style="width: 20%;">上一周</th>
                </tr>
            </thead>
            <tbody>
                {fed_table_body}
            </tbody>
        </table>

        <div style="text-align: right; font-size: 11px; color: var(--footer-text); margin-top: 12px;">更新: {fed_update_text}</div>
    </div>
    {fed_countdown_js}
    """


    now_dt = now_beijing()
    update_time_str = now_dt.strftime("%Y-%m-%d %H:%M") + " (北京时间)"

    if now_dt.weekday() == 5:
        fri_dt = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        col_today_title = f"今日涨幅 (基准周五: {fri_dt})"
    elif now_dt.weekday() == 6:
        fri_dt = (now_dt - timedelta(days=2)).strftime("%Y-%m-%d")
        col_today_title = f"今日涨幅 (基准周五: {fri_dt})"
    else:
        col_today_title = f"今日涨幅 ({today_str})"

    mode_badge = '<span style="background:#e67e22; color:#fff; font-size:11px; padding:2px 8px; border-radius:10px; margin-left:6px;">🛠️ 调试测试模式</span>' if is_debug_mode else '<span style="background:#188038; color:#fff; font-size:11px; padding:2px 8px; border-radius:10px; margin-left:6px;">🚀 正式发布版本</span>'

    fng = metrics["fng"]
    vix = metrics["vix"]
    usdcny = metrics["usdcny"]
    vxn = metrics["vxn"]
    skew = metrics["skew"]
    brent = metrics["brent"]

    gold_london = metrics.get("gold_london", {"val": 0.0, "status": "数据暂缺", "source": "获取失败", "url": "#", "desc": ""})
    gold_shfe = metrics.get("gold_shfe", {"val": 0.0, "status": "数据暂缺", "source": "获取失败", "url": "#", "desc": ""})
    silver_london = metrics.get("silver_london", {"val": 0.0, "status": "数据暂缺", "source": "获取失败", "url": "#", "desc": ""})
    copper_lme = metrics.get("copper_lme", {"val": 0.0, "status": "数据暂缺", "source": "获取失败", "url": "#", "desc": ""})
    btc = metrics.get("btc", {"val": 0.0, "status": "数据暂缺", "source": "获取失败", "url": "#", "desc": ""})

    brent_tag_color = "#70757a" if brent['val'] <= 0 else ("#d93025" if brent['val'] >= 95 else ("#e67e22" if brent['val'] >= 80 else ("#188038" if brent['val'] >= 65 else "#1a73e8")))
    gold_tag_color = "#70757a" if gold_london['val'] <= 0 else ("#d93025" if gold_london['val'] >= 2500 else ("#e67e22" if gold_london['val'] >= 2000 else ("#188038" if gold_london['val'] >= 1500 else "#1a73e8")))
    gold_shfe_tag_color = "#70757a" if gold_shfe['val'] <= 0 else ("#d93025" if gold_shfe['val'] >= 700 else ("#e67e22" if gold_shfe['val'] >= 600 else ("#188038" if gold_shfe['val'] >= 500 else "#1a73e8")))
    silver_tag_color = "#70757a" if silver_london['val'] <= 0 else ("#d93025" if silver_london['val'] >= 35 else ("#e67e22" if silver_london['val'] >= 28 else ("#188038" if silver_london['val'] >= 20 else "#1a73e8")))
    copper_tag_color = "#70757a" if copper_lme['val'] <= 0 else ("#d93025" if copper_lme['val'] >= 10000 else ("#e67e22" if copper_lme['val'] >= 8500 else ("#188038" if copper_lme['val'] >= 7000 else "#1a73e8")))
    btc_tag_color = "#70757a" if btc['val'] <= 0 else ("#d93025" if btc['val'] >= 100000 else ("#e67e22" if btc['val'] >= 70000 else ("#188038" if btc['val'] >= 40000 else "#1a73e8")))

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>场外基金量化与资产配置看板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #f8f9fa;
            --text: #333;
            --border: #e0e0e0;
            --header-bg: #f1f3f4;
            --header-text: #3c4043;
            --hover-bg: #f8f9fa;
            --table-bg: #fff;
            --progress-track: #e5e7eb;
            --footer-bg: #fff;
            --footer-text: #70757a;
            --btn-bg: #e8eaed;
            --btn-text: #3c4043;
            --btn-active-bg: #1a73e8;
            --btn-active-text: #fff;
            --input-bg: #fff;
            --input-border: #ddd;
            --card-bg: #f0f2f5;
            --link-color: #1a73e8;
            --card-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        [data-theme="dark"] {{
            --bg: #1a1a1a;
            --text: #e0e0e0;
            --border: #444;
            --header-bg: #2d2d2d;
            --header-text: #ccc;
            --hover-bg: #2a2a2a;
            --table-bg: #252525;
            --progress-track: #3a3a3a;
            --footer-bg: #2d2d2d;
            --footer-text: #aaa;
            --btn-bg: #3d3d3d;
            --btn-text: #ccc;
            --btn-active-bg: #1a73e8;
            --btn-active-text: #fff;
            --input-bg: #333;
            --input-border: #555;
            --card-bg: #2a2a2a;
            --link-color: #4a9eff;
            --card-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}
        body {{ 
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif; 
            background-color: var(--bg);
            color: var(--text);
            margin: 0; 
            padding: 0; 
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
            transition: background-color 0.3s, color 0.3s;
        }}
        
        .main-navbar {{
            background: var(--table-bg);
            border-bottom: 1px solid var(--border);
            padding: 0 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 52px;
            flex-shrink: 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            z-index: 100;
        }}
        .nav-brand {{
            font-size: 16px;
            font-weight: 700;
            color: var(--link-color);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .nav-tabs-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .nav-tab-btn {{
            background: transparent;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            color: var(--header-text);
            transition: all 0.2s;
        }}
        .nav-tab-btn:hover {{ background: var(--hover-bg); color: var(--link-color); }}
        .nav-tab-btn.active {{ background: var(--btn-active-bg); color: #fff; }}
        .nav-right-tools {{ display: flex; align-items: center; gap: 12px; }}
        .theme-toggle {{
            background: var(--header-bg);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 4px 10px;
            font-size: 11px;
            cursor: pointer;
        }}

        .views-container {{
            flex: 1;
            min-height: 0;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 12px 20px;
        }}
        .view-pane {{ display: none; flex-direction: column; height: 100%; min-height: 0; }}
        .view-pane.active {{ display: flex; }}

        .home-container {{
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px 5%;
            width: 100%;
            box-sizing: border-box;
        }}
        
        .macro-metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
        }}

        /* 止盈信号面板专用样式 */
        .stop-profit-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        .stop-profit-item {{
            background: var(--hover-bg);
            border-radius: 8px;
            padding: 14px;
            border: 1px solid var(--border);
            transition: transform 0.2s;
        }}
        .stop-profit-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .stop-profit-title {{
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 10px;
            color: var(--text);
            border-bottom: 1px dashed var(--border);
            padding-bottom: 6px;
        }}
        .stop-profit-value {{
            font-size: 24px;
            font-weight: 800;
            font-family: "SFMono-Regular", Consolas, monospace;
            margin-bottom: 12px;
            line-height: 1;
        }}
        .stop-profit-rules {{
            font-size: 12px;
            color: var(--footer-text);
            line-height: 1.8;
        }}
        @media (max-width: 768px) {{
            .stop-profit-grid {{ grid-template-columns: 1fr; }}
        }}

        .index-metrics-grid, .friend-links-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
        }}

        .friend-category-block {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .friend-category-title {{
            margin: 8px 0 4px 0;
            font-size: 13px;
            font-weight: 700;
            color: var(--header-text);
            padding-left: 4px;
            border-left: 3px solid var(--link-color);
        }}
        .friend-card-head {{
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px dashed var(--border);
            padding-bottom: 6px;
            margin-bottom: 6px;
        }}
        .friend-logo {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
            flex-shrink: 0;
            object-fit: contain;
            background: var(--bg);
        }}
        .friend-name {{
            color: var(--link-color);
            font-size: 14px;
            font-weight: 700;
            flex: 1;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .friend-arrow {{
            color: var(--link-color);
            flex-shrink: 0;
        }}
        .metric-card {{
            background: var(--table-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 14px;
            box-shadow: var(--card-shadow);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .metric-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 700;
            color: var(--header-text);
        }}
        .metric-body {{
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin: 8px 0;
        }}
        .metric-value {{
            font-size: 26px;
            font-weight: 800;
            font-family: "SFMono-Regular", Consolas, monospace;
            line-height: 1;
        }}
        .metric-tag {{
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .metric-desc {{
            font-size: 11px;
            color: var(--footer-text);
            line-height: 1.4;
            border-top: 1px dashed var(--border);
            padding-top: 6px;
            margin-top: 4px;
        }}
        .metric-source-link {{
            font-size: 11px;
            color: var(--link-color);
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 3px;
            margin-top: 6px;
            padding-top: 4px;
            border-top: 1px solid var(--border);
            word-break: break-all;
        }}
        .metric-source-link:hover {{ text-decoration: underline; }}

        .fng-bar-track {{
            height: 6px;
            background: linear-gradient(to right, #d93025, #ea8600, #fbbc04, #34a853, #188038);
            border-radius: 3px;
            position: relative;
            margin: 6px 0 2px 0;
        }}
        .fng-bar-pointer {{
            width: 3px;
            height: 10px;
            background: #000;
            position: absolute;
            top: -2px;
            transform: translateX(-50%);
            border-radius: 1px;
        }}
        [data-theme="dark"] .fng-bar-pointer {{ background: #fff; }}

        /* Fed Monitor specific styles */
        .fed-card {{
            background: var(--table-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            box-shadow: var(--card-shadow);
            margin-bottom: 12px;
        }}
        .fed-title {{
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 12px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            color: var(--header-text);
        }}
        .fed-info {{
            font-size: 13px;
            color: var(--text);
            margin-bottom: 16px;
            line-height: 1.6;
        }}
        .fed-bar-row {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            font-size: 13px;
        }}
        .fed-bar-label {{
            width: 80px;
            font-weight: 600;
            color: var(--text);
        }}
        .fed-bar-track {{
            flex: 1;
            height: 24px;
            background: var(--progress-track);
            position: relative;
            margin: 0 12px;
        }}
        .fed-bar-fill {{
            height: 100%;
            display: flex;
            align-items: center;
            padding-left: 8px;
            color: #fff;
            font-weight: bold;
            font-size: 12px;
            box-sizing: border-box;
            border-radius: 2px;
        }}
        .fed-bar-fill.blue {{ background: #5c8bb5; }}
        .fed-bar-fill.grey {{ background: #a6a6a6; }}
        .fed-bar-pct {{
            margin-left: 6px;
            font-weight: 600;
            color: var(--text);
            font-size: 13px;
        }}
        .fed-table {{
            width: 100%;
            min-width: 0 !important;
            max-width: 100%;
            box-sizing: border-box;
            border-collapse: collapse;
            margin-top: 16px;
            font-size: 13px;
            text-align: right;
            table-layout: fixed;
        }}
        .fed-table th,
        .fed-table td {{
            min-width: 0;
            box-sizing: border-box;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .fed-table th, .fed-table td {{
            padding: 10px;
            border-bottom: 1px solid var(--border);
            color: var(--text);
        }}
        .fed-table th {{
            color: var(--footer-text);
            font-weight: 500;
        }}
        .fed-table td:first-child, .fed-table th:first-child {{
            text-align: left;
            font-weight: 600;
        }}

        .home-card-box {{
            background: var(--table-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            box-shadow: var(--card-shadow);
        }}
        .home-card-title {{
            font-size: 14px;
            font-weight: 700;
            color: var(--header-text);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .home-card-body {{ font-size: 12px; color: var(--footer-text); line-height: 1.6; }}

        .sub-filter-bar {{
            background: var(--table-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
            flex-shrink: 0;
            box-sizing: border-box;
        }}

        /* 移动端折叠开关（桌面端默认隐藏） */
        .mobile-filter-toggle,
        .dca-toggle-btn,
        .mobile-panel-switches {{
            display: none;
        }}

        /* 桌面端：申购状态主行样式 */
        .buy-status-main-row {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }}

        /* 桌面端：sub-filter-bar 进入 dca-mobile-row 后占满整行 */
        .dca-mobile-row .sub-filter-bar {{
            flex: 0 0 100%;
            order: -1;
        }}
        
        .category-nav {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
        .category-title {{ font-size: 11px; font-weight: 700; color: var(--footer-text); margin-right: 4px; }}
        .cat-btn {{
            background: var(--btn-bg);
            color: var(--btn-text);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 3px 10px;
            font-size: 11px;
            cursor: pointer;
            transition: all .2s;
            font-weight: 500;
        }}
        .cat-btn:hover {{ background: var(--btn-active-bg); color: var(--btn-active-text); }}
        .cat-btn.active {{ background: var(--btn-active-bg); color: var(--btn-active-text); border-color: var(--btn-active-bg); }}
        .cat-btn.fav-filter {{
            background: rgba(230,126,34,0.15);
            color: #e67e22;
            border-color: #e67e22;
            font-weight: 700;
        }}
        .cat-btn.fav-filter.active {{
            background: #e67e22;
            color: #fff;
            border-color: #e67e22;
        }}
        .search-box-wrap {{ width: 260px; flex-shrink: 0; }}
        .search-box-wrap input {{
            width: 100%;
            height: 28px;
            padding: 4px 10px;
            border-radius: 14px;
            border: 1px solid #35a853;
            background: var(--input-bg);
            color: var(--text);
            font-size: 12px;
            outline: none;
            box-sizing: border-box;
        }}

        .global-dca-filter-card {{
            background: var(--table-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 6px 12px;
            box-sizing: border-box;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
            font-size: 11px;
            flex-shrink: 0;
            transition: all 0.3s ease;
        }}
        .global-dca-filter-header {{
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            user-select: none;
        }}
        .global-dca-filter-title {{
            font-weight: 700;
            color: var(--link-color);
        }}
        #gDcaToggleIcon {{
            font-size: 9px;
            color: var(--footer-text);
            transition: transform 0.2s;
        }}
        .global-dca-filter-body {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .global-dca-filter-card.collapsed .global-dca-filter-body {{ display: flex; }}
        .global-dca-filter-card select {{
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid var(--input-border);
            background: var(--input-bg);
            color: var(--text);
            font-size: 11px;
            outline: none;
        }}
        .global-dca-filter-card button {{
            background: var(--btn-active-bg);
            color: #fff;
            border: none;
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .global-dca-filter-card button:hover {{ opacity: 0.9; }}

        .table-container {{ 
            width: 100%; 
            flex: 1 1 0; 
            min-height: 0; 
            overflow-y: auto; 
            overflow-x: auto; 
            -webkit-overflow-scrolling: touch;
            box-sizing: border-box; 
            background: var(--table-bg);
            border-radius: 10px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.06); 
            padding: 8px; 
            border: 1px solid var(--border);
            margin-bottom: 6px;
        }}
        #fundTable {{ width: 100%; min-width: 2550px; border-collapse: collapse; font-size: 12px; text-align: right; table-layout: fixed; }}
        th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--border); line-height: 1.4; overflow: hidden; text-overflow: ellipsis; box-sizing: border-box; }}
        #fundTable thead th {{ position: sticky; top: 0; z-index: 10; background-color: var(--header-bg); border-bottom: 2px solid var(--border); }}
        th:nth-child(1), td:nth-child(1) {{ width: 45px; text-align: center; white-space: nowrap; }}
        th:nth-child(2), td:nth-child(2) {{ width: 65px; text-align: left; white-space: nowrap; }}
        th:nth-child(3), td:nth-child(3) {{ width: 250px; min-width: 200px; text-align: left; white-space: normal; word-break: break-word; vertical-align: middle; }}
        th:nth-child(4), td:nth-child(4) {{ width: 80px; text-align: left; white-space: nowrap; }}
        th:nth-child(5), td:nth-child(5) {{ width: 130px; text-align: left; white-space: normal; word-break: break-word; }}
        th:nth-child(6), td:nth-child(6) {{ width: 70px; text-align: left; white-space: nowrap; }}
        th:nth-child(7), td:nth-child(7) {{ width: 100px; text-align: left; white-space: nowrap; }}
        th:nth-child(8), td:nth-child(8), th:nth-child(9), td:nth-child(9) {{ width: 128px; white-space: nowrap; }}
        th:nth-child(10), td:nth-child(10) {{ width: 85px; white-space: nowrap; }}
        th:nth-child(11), td:nth-child(11), th:nth-child(12), td:nth-child(12), th:nth-child(13), td:nth-child(13) {{ width: 300px; white-space: nowrap; }}
        th:nth-child(14), td:nth-child(14) {{ width: 80px; white-space: nowrap; }}
        th:nth-child(15), td:nth-child(15) {{ width: 155px; min-width: 90px; white-space: normal; }}
        th:nth-child(16), td:nth-child(16), th:nth-child(17), td:nth-child(17), th:nth-child(18), td:nth-child(18), th:nth-child(19), td:nth-child(19), th:nth-child(20), td:nth-child(20), th:nth-child(21), td:nth-child(21), th:nth-child(22), td:nth-child(22) {{ width: 80px; white-space: nowrap; }}
        th {{ background-color: var(--header-bg); color: var(--header-text); font-weight: 600; text-align: right; user-select: none; cursor: pointer; white-space: normal; word-break: keep-all; line-height: 1.25; height: 38px; vertical-align: middle; position: relative; }}
        th:hover {{ background-color: #e4e7eb; }}
        [data-theme="dark"] th:hover {{ background-color: #3d3d3d; }}
        th:nth-child(1) {{ text-align: center; }}
        th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5), th:nth-child(6), th:nth-child(7) {{ text-align: left; }}
        tr:hover {{ background-color: var(--hover-bg); }}
        
        .resizer {{
            position: absolute;
            right: 0;
            top: 0;
            bottom: 0;
            width: 7px;
            cursor: col-resize;
            user-select: none;
            touch-action: none;
            z-index: 20;
        }}
        .resizer:hover, th.resizing .resizer {{
            background-color: var(--link-color);
        }}

        .star-btn {{
            background: transparent;
            border: none;
            font-size: 16px;
            color: #aaa;
            cursor: pointer;
            padding: 0;
            line-height: 1;
            transition: all 0.2s;
        }}
        .star-btn:hover {{ transform: scale(1.2); color: #f39c12; }}
        .star-btn.starred {{ color: #f39c12; font-weight: bold; text-shadow: 0 0 2px rgba(243,156,18,0.5); }}

        .code {{ font-family: "SFMono-Regular", Consolas, monospace; font-weight: bold; color: #1a73e8; }}
        .name a {{ font-weight: 500; color: #1a73e8; text-decoration: none; }}
        .redemption-sub {{ font-size: 10px; color: var(--footer-text); margin-top: 2px; }}
        .highlight-rate {{ color: #d93025; font-weight: bold; }}
        .highlight-val {{ font-weight: 600; color: #e67e22; }}
        .fee-sub {{ font-size: 10px; color: var(--footer-text); }}

        .dca-btn {{
            background: #e8f0fe;
            color: #1a73e8;
            border: 1px solid #dadce0;
            border-radius: 10px;
            padding: 1px 5px;
            font-size: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            display: inline-flex;
            align-items: center;
        }}
        .dca-btn:hover {{
            background: #1a73e8;
            color: #fff;
            border-color: #1a73e8;
            transform: scale(1.05);
        }}
        [data-theme="dark"] .dca-btn {{
            background: #2a3b50;
            color: #8ab4f8;
            border-color: #3c4043;
        }}

        /* --- 进度条样式 --- */
        .progress-container {{ 
            background-color: var(--progress-track); 
            border-radius: 6px; 
            overflow: hidden; 
            height: 20px; 
            width: 100%; 
            position: relative; 
            display: block;
        }}
        .progress-bar {{ 
            height: 100%; 
            border-radius: 6px; 
            min-width: 42px; 
            display: flex; 
            align-items: center; 
            justify-content: flex-end; 
            padding-right: 6px; 
            box-sizing: border-box; 
            transition: width .2s ease;
        }}
        .progress-bar span {{ 
            color: #fff; 
            font-size: 11px; 
            font-weight: 600; 
            text-shadow: 0 1px 1px rgba(0,0,0,.25);
            white-space: nowrap;
        }}
        .bar-red {{ background-color: #d93025; }}
        .bar-blue {{ background-color: #1a73e8; }}
        .bar-green {{ background-color: #188038; }}
        .metric-red {{ color: #d93025; font-weight: 600; }}
        .metric-green {{ color: #188038; font-weight: 600; }}
        .gain-positive {{ color: #d93025; font-weight: bold; }}
        .gain-negative {{ color: #188038; font-weight: bold; }}
        .gain-date {{ font-size: 10px; color: var(--footer-text); font-weight: normal; }}

        /* --- 贵金属、加密货币等最新净值高亮 --- */
        .highlight-special-nav {{
            font-weight: bold;
            color: #d93025;
            background-color: rgba(217, 48, 37, 0.12);
            padding: 2px 6px;
            border-radius: 4px;
            display: inline-block;
        }}
        [data-theme="dark"] .highlight-special-nav {{
            color: #ff8a65;
            background-color: rgba(255, 138, 101, 0.2);
        }}

        .fund-row {{ cursor: pointer; }}
        .holding-row td {{ background-color: var(--hover-bg) !important; border-top: 1px dashed var(--border); }}
        .holding-row {{ display: none; }}
        .holding-row.show {{ display: table-row; }}
        .holdings-wrapper {{ display: flex; flex-wrap: nowrap; gap: 14px; align-items: stretch; width: 100%; }}
        .holdings-container {{ flex: 0 0 calc(50% - 7px); width: calc(50% - 7px); display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; align-items: stretch; min-width: 0; }}
        .quarter-card {{ min-width: 0; background: var(--card-bg); border-radius: 8px; padding: 10px 8px; box-shadow: var(--card-shadow); box-sizing: border-box; display: flex; flex-direction: column; }}
        .empty-holdings-placeholder {{ grid-column: span 3; }}
        .quarter-label {{ font-weight: bold; font-size: 12px; margin-bottom: 8px; color: var(--header-text); border-bottom: 1px solid var(--border); padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }}
        .quarter-title {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .quarter-end {{ font-size: 10px; color: var(--footer-text); }}
        .quarter-stocks {{ display: flex; flex-direction: column; gap: 4px; flex: 1; }}
        .stock-item {{ display: grid; grid-template-columns: minmax(0, 1fr) 50px 56px; gap: 3px; font-size: 11px; align-items: center; }}
        .stock-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: left; }}
        .stock-ratio {{ text-align: right; font-weight: 500; }}
        .stock-change {{ text-align: right; font-size: 10px; white-space: nowrap; }}
        .change-add {{ color: #d93025; }}
        .change-sub {{ color: #188038; }}
        .change-up {{ color: #d93025; }}
        .change-down {{ color: #188038; }}
        .change-new {{ color: #1a73e8; }}
        .stock-total {{ margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--border); font-weight: 600; }}
        .stock-total .stock-ratio {{ color: #e67e22; }}
        
        .holder-card {{ display: flex; flex-direction: column; justify-content: space-between; }}
        .holder-pie-wrapper {{ flex: 1; display: flex; align-items: center; justify-content: center; position: relative; min-height: 140px; max-height: 180px; padding: 4px 0; }}
        .holder-date-sub {{ font-size: 10px; color: var(--footer-text); text-align: center; border-top: 1px dashed var(--border); padding-top: 6px; margin-top: 4px; }}

        /* 右侧 1:3 结构布局容器 (国家占比 1/4，折线图 3/4) */
        .right-chart-wrapper {{
            flex: 0 0 calc(50% - 7px);
            width: calc(50% - 7px);
            display: flex;
            gap: 10px;
            align-items: stretch;
            min-width: 0;
        }}
        .country-card {{
            flex: 1 1 0;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .country-pie-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            min-height: 140px;
            max-height: 180px;
            padding: 4px 0;
        }}
        .country-date-sub {{
            font-size: 10px;
            color: var(--footer-text);
            text-align: center;
            border-top: 1px dashed var(--border);
            padding-top: 6px;
            margin-top: 4px;
        }}
        .chart-container {{
            flex: 3 1 0;
            min-width: 0;
            background: var(--card-bg);
            border-radius: 8px;
            padding: 10px;
            box-shadow: var(--card-shadow);
            display: flex;
            flex-direction: column;
            min-height: 200px;
        }}
        .chart-controls {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }}
        .chart-controls button {{ background: var(--btn-bg); border: 1px solid var(--border); border-radius: 12px; padding: 2px 10px; font-size: 11px; cursor: pointer; color: var(--btn-text); }}
        .chart-controls button.active {{ background: var(--btn-active-bg); color: var(--btn-active-text); }}
        .chart-container canvas {{ width: 100% !important; height: auto !important; max-height: 200px; flex: 1; }}
        
        .footer-note {{ font-size: 11px; color: var(--footer-text); background: var(--footer-bg); padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
        
        /* 定投回测模态弹窗 */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.45);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            backdrop-filter: blur(2px);
        }}
        .modal-overlay.show {{ display: flex; }}
        .modal-card {{
            background: var(--table-bg);
            color: var(--text);
            width: 92%;
            max-width: 820px;
            border-radius: 14px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.25);
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            animation: modalFadeIn 0.2s ease;
        }}
        @keyframes modalFadeIn {{
            from {{ transform: scale(0.96); opacity: 0; }}
            to {{ transform: scale(1); opacity: 1; }}
        }}
        .modal-header {{
            padding: 12px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--header-bg);
        }}
        .modal-header h3 {{
            margin: 0;
            font-size: 15px;
            color: var(--link-color);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .modal-close {{
            background: transparent;
            border: none;
            font-size: 20px;
            color: var(--footer-text);
            cursor: pointer;
            line-height: 1;
        }}
        .modal-close:hover {{ color: #d93025; }}
        .modal-body {{
            padding: 14px 18px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .dca-controls {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
            background: var(--card-bg);
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .dca-field {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            font-size: 11px;
            font-weight: 500;
        }}
        .dca-field select, .dca-field input {{
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid var(--input-border);
            background: var(--input-bg);
            color: var(--text);
            font-size: 12px;
            outline: none;
        }}
        .dca-run-btn {{
            grid-column: 1 / -1;
            background: var(--btn-active-bg);
            color: #fff;
            border: none;
            border-radius: 6px;
            padding: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
            margin-top: 2px;
        }}
        .dca-run-btn:hover {{ opacity: 0.9; }}
        
        .dca-results-grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
        }}
        .dca-result-card {{
            background: var(--hover-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 10px;
            text-align: center;
        }}
        .dca-result-title {{
            font-size: 10px;
            color: var(--footer-text);
            margin-bottom: 2px;
        }}
        .dca-result-value {{
            font-size: 14px;
            font-weight: 700;
            font-family: "SFMono-Regular", Consolas, monospace;
        }}
        .dca-chart-box {{
            height: 230px;
            width: 100%;
            position: relative;
            background: var(--card-bg);
            border-radius: 8px;
            padding: 8px;
            border: 1px solid var(--border);
            box-sizing: border-box;
        }}

        @media (max-width: 1200px) {{
            .index-metrics-grid, .friend-links-grid {{ grid-template-columns: repeat(3, 1fr); }}
        }}
        @media (max-width: 992px) {{
            body {{
                height: auto;
                min-height: 100dvh;
                overflow-y: auto;
                overflow-x: hidden;
                padding: 0;
            }}
            .main-navbar {{
                padding: 10px 12px;
                height: auto;
                flex-wrap: wrap;
                gap: 8px;
            }}
            .nav-brand {{ font-size: 15px; }}
            .views-container {{ padding: 8px 10px; height: auto; overflow: visible; }}
            .view-pane {{ height: auto; overflow: visible; }}
            
            .home-container {{ padding: 10px 16px; gap: 10px; }}
            .macro-metrics-grid {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
            .index-metrics-grid, .friend-links-grid {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
            
            .home-grid-section {{ grid-template-columns: 1fr; gap: 10px; }}
            /* ===== 移动端：申购状态栏作为统一工具栏（一行布局） ===== */
            .dca-mobile-row {{
                flex-direction: column;
                gap: 8px;
            }}

            /* 申购状态栏：内部改为横向单行 —— 左申购 / 右切换 */
            .dca-mobile-row .buy-status-filter-card {{
                order: 1;
                width: 100%;
                flex-basis: 100%;
                flex-direction: row !important;
                align-items: center !important;
                justify-content: space-between !important;
                flex-wrap: nowrap !important;
                gap: 6px !important;
                padding: 5px 8px !important;
                min-height: 36px !important;
                overflow: hidden;
            }}

            /* 左侧：申购状态组 */
            .dca-mobile-row .buy-status-main-row {{
                display: flex;
                align-items: center;
                gap: 3px;
                flex-wrap: nowrap;
                flex-shrink: 1;
                min-width: 0;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                padding-bottom: 0;
                border-bottom: none;
                scrollbar-width: none;
            }}
            .dca-mobile-row .buy-status-main-row::-webkit-scrollbar {{
                display: none;
            }}

            /* 移动端隐藏"申购状态:"文字标签，节省横向空间 */
            .dca-mobile-row .buy-status-main-row .category-title {{
                display: none;
            }}

            /* 申购状态按钮压缩到最小 */
            .dca-mobile-row .buy-status-main-row .cat-btn {{
                padding: 2px 7px;
                font-size: 10px;
                flex-shrink: 0;
                line-height: 1.4;
                border-radius: 10px;
            }}

            /* 右侧：面板切换按钮组 */
            .mobile-panel-switches {{
                display: flex;
                gap: 4px;
                flex-shrink: 0;
                width: auto;
            }}

            .mobile-panel-switches .mobile-filter-toggle,
            .mobile-panel-switches .dca-toggle-btn {{
                flex: none;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 3px;
                padding: 4px 7px;
                font-size: 10px;
                font-weight: 600;
                line-height: 1.4;
                color: var(--btn-text);
                background: var(--btn-bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                cursor: pointer;
                box-sizing: border-box;
                -webkit-tap-highlight-color: transparent;
                user-select: none;
                white-space: nowrap;
                transition: background 0.15s, color 0.15s, border-color 0.15s;
            }}

            .mobile-panel-switches .mobile-filter-toggle:active,
            .mobile-panel-switches .dca-toggle-btn:active {{
                background: rgba(26,115,232,0.12);
            }}

            .mobile-panel-switches .mobile-filter-toggle.expanded,
            .mobile-panel-switches .dca-toggle-btn.active {{
                background: var(--btn-active-bg);
                color: #fff;
                border-color: var(--btn-active-bg);
            }}

            .mobile-panel-switches .mobile-filter-current {{
                color: var(--link-color);
                font-weight: 700;
                max-width: 44px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-size: 10px;
            }}

            .mobile-panel-switches .mobile-filter-toggle.expanded .mobile-filter-current {{
                color: #fff;
            }}

            .mobile-panel-switches .mobile-filter-arrow,
            .mobile-panel-switches #dcaToggleArrow {{
                font-size: 8px;
                transition: transform 0.2s;
            }}

            /* 市场大类面板 */
            .dca-mobile-row .sub-filter-bar {{
                order: 2;
                display: none;
                margin-bottom: 0;
                max-height: 55vh;
                overflow-y: auto;
            }}
            .dca-mobile-row .sub-filter-bar.mobile-expanded {{
                display: flex;
                flex-direction: column;
                align-items: stretch;
                gap: 8px;
                animation: mobileFilterSlide 0.18s ease;
            }}

            /* 定投参数面板 */
            .dca-mobile-row .global-dca-filter-card {{
                order: 3;
                display: none;
            }}
            .dca-mobile-row .global-dca-filter-card.mobile-expanded {{
                display: flex;
                animation: mobileFilterSlide 0.18s ease;
            }}

            @keyframes mobileFilterSlide {{
                from {{ opacity: 0; transform: translateY(-6px); }}
                to   {{ opacity: 1; transform: translateY(0); }}
            }}

            .search-box-wrap {{ width: 100%; }}
            .search-box-wrap input {{ height: 32px; font-size: 13px; }}
            .global-dca-filter-card {{ flex-direction: column; align-items: stretch; padding: 10px; gap: 8px; }}
            .buy-status-filter-card {{ width: 100%; flex-basis: 100%; }}
            .global-dca-filter-body {{ flex-direction: column; align-items: stretch; width: 100%; }}
            .global-dca-filter-card select, .global-dca-filter-card button {{ width: 100%; height: 32px; font-size: 12px; }}
            .table-container {{ height: auto; flex: none; max-height: 70vh; padding: 4px; }}

            /* ===== 移动端保持与桌面端一致：展开行仍为左右各 50% 的单行布局 ===== */
            .holdings-wrapper {{
                flex-direction: row;
                flex-wrap: nowrap;
                gap: 14px;
                align-items: stretch;
                width: 100%;
            }}
            .holdings-container {{
                flex: 0 0 calc(50% - 7px);
                width: calc(50% - 7px);
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 8px;
                align-items: stretch;
                min-width: 0;
            }}
            .empty-holdings-placeholder {{ grid-column: span 3; }}
            .right-chart-wrapper {{
                flex: 0 0 calc(50% - 7px);
                width: calc(50% - 7px);
                flex-direction: row;
                gap: 10px;
                align-items: stretch;
                min-width: 0;
            }}
            .country-card {{ flex: 1 1 0; width: auto; min-width: 0; }}
            .chart-container {{ flex: 3 1 0; width: auto; min-width: 0; }}
            .modal-card {{ width: 95%; max-height: 90vh; }}
            .modal-body {{ padding: 10px 12px; }}
            .dca-controls {{ grid-template-columns: 1fr; }}
            .dca-results-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .dca-result-card:last-child {{ grid-column: span 2; }}
            .footer-note {{ flex-direction: column; align-items: flex-start; gap: 6px; margin-bottom: 12px; }}
            .annual-card-grid {{ grid-template-columns: 1fr !important; }}

            /* ===== 简洁模式：移动端列宽优化（仅窄屏生效） ===== */
            #fundView.simple-mode {{
                padding-left: 2%;
                padding-right: 2%;
            }}
            #fundView.simple-mode .table-container {{
                padding: 4px 6px;
                overflow-x: auto;
            }}
            #fundView.simple-mode #fundTable {{
                min-width: 720px !important;
                table-layout: fixed !important;
                font-size: 11px;
            }}
            #fundView.simple-mode #fundTable th,
            #fundView.simple-mode #fundTable td {{
                padding: 4px 2px !important;
                font-size: 10px !important;
                line-height: 1.3;
            }}

            /* 收藏列 */
            #fundView.simple-mode #fundTable th:nth-child(1),
            #fundView.simple-mode #fundTable td:nth-child(1) {{
                width: 40px !important;
                min-width: 40px !important;
            }}

            /* 代码列 */
            #fundView.simple-mode #fundTable th:nth-child(2),
            #fundView.simple-mode #fundTable td:nth-child(2) {{
                width: 62px !important;
                min-width: 62px !important;
                font-size: 10px !important;
            }}

            /* 名称列 */
            #fundView.simple-mode #fundTable th:nth-child(3),
            #fundView.simple-mode #fundTable td:nth-child(3) {{
                width: 130px !important;
                min-width: 130px !important;
                white-space: normal !important;
                word-break: break-word !important;
                font-size: 10px !important;
            }}

            /* 规模列 */
            #fundView.simple-mode #fundTable th:nth-child(4),
            #fundView.simple-mode #fundTable td:nth-child(4) {{
                width: 60px !important;
                min-width: 60px !important;
                font-size: 10px !important;
            }}

            /* 状态列（宽度与近一周一致） */
            #fundView.simple-mode #fundTable th:nth-child(7),
            #fundView.simple-mode #fundTable td:nth-child(7) {{
                width: 62px !important;
                min-width: 62px !important;
                white-space: normal !important;
                font-size: 10px !important;
            }}

            /* 6 个数值列 */
            #fundView.simple-mode #fundTable th:nth-child(16),
            #fundView.simple-mode #fundTable td:nth-child(16),
            #fundView.simple-mode #fundTable th:nth-child(17),
            #fundView.simple-mode #fundTable td:nth-child(17),
            #fundView.simple-mode #fundTable th:nth-child(18),
            #fundView.simple-mode #fundTable td:nth-child(18),
            #fundView.simple-mode #fundTable th:nth-child(19),
            #fundView.simple-mode #fundTable td:nth-child(19),
            #fundView.simple-mode #fundTable th:nth-child(20),
            #fundView.simple-mode #fundTable td:nth-child(20),
            #fundView.simple-mode #fundTable th:nth-child(21),
            #fundView.simple-mode #fundTable td:nth-child(21) {{
                width: 62px !important;
                min-width: 62px !important;
                font-size: 10px !important;
            }}

            /* 简洁模式展开行：图表高度适配小屏 */
            #fundView.simple-mode .holding-row .chart-container {{
                min-height: 220px;
            }}
        }}
        @media (max-width: 480px) {{
            .macro-metrics-grid {{ grid-template-columns: 1fr; }}
            .index-metrics-grid, .friend-links-grid {{ grid-template-columns: 1fr; }}
        }}

        /* ===== 指数历年回报表格/卡片样式 ===== */
        .annual-card-grid {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        .annual-year-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 4px;
            border-bottom: 1px dashed var(--border);
            font-size: 12px;
            transition: background 0.2s;
            cursor: default;
        }}
        .annual-year-row:hover {{
            background: var(--hover-bg);
            box-shadow: inset 3px 0 0 var(--link-color);
        }}
        .annual-year-col {{
            width: 12%;
            font-weight: 600;
            color: var(--header-text);
            text-align: left;
        }}
        .annual-points-col {{
            width: 28%;
            text-align: right;
            font-family: "SFMono-Regular", Consolas, monospace;
            color: var(--text);
        }}
        .annual-pct-col {{
            width: 20%;
            text-align: right;
            font-weight: 600;
        }}
        .annual-bar-col {{
            width: 40%;
            position: relative;
            height: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .annual-zero-line {{
            position: absolute;
            left: 50%;
            top: 0;
            bottom: 0;
            width: 1px;
            background: var(--border);
            z-index: 2;
        }}
        .annual-bar-fill {{
            position: absolute;
            height: 10px;
            border-radius: 2px;
            transition: width 0.3s ease;
        }}
        @media (max-width: 992px) {{
            .index-annual-grid {{
                grid-template-columns: 1fr !important;
            }}
        }}

        /* 指数历年回报模式切换按钮 */
        .mode-toggle-btn {{
            background: var(--btn-bg);
            color: var(--btn-text);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .mode-toggle-btn.active {{
            background: var(--btn-active-bg);
            color: var(--btn-active-text);
            border-color: var(--btn-active-bg);
        }}
        /* ===== 指数历年回报统计信息条 ===== */
        .annual-stats-footer {{
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 6px;
            padding: 10px 4px 2px 4px;
            margin-top: 10px;
            border-top: 1px solid var(--border);
        }}
        .annual-stat-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            min-width: 60px;
        }}
        .annual-stat-label {{
            color: var(--footer-text);
            font-size: 10px;
        }}
        .annual-stat-value {{
            font-weight: 700;
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 13px;
            color: var(--text);
        }}
        .annual-mode-content {{
            padding-top: 4px;
        }}
        /* ===== 指数历年回报 - 热力图单格悬停高亮 ===== */
        .annual-heatmap-cell {{
            transition: transform 0.15s ease, outline 0.15s ease;
            position: relative;
            z-index: 1;
        }}
        .annual-heatmap-cell:hover {{
            transform: scale(1.10);
            outline: 2px solid var(--link-color);
            outline-offset: 1px;
            z-index: 5;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}

        /* ===== 基金看板：默认 / 简洁 视图模式 ===== */
        .view-mode-btn.active {{
            background: #e67e22 !important;
            color: #fff !important;
            border-color: #e67e22 !important;
            font-weight: 700;
        }}

        /* ===== 简洁模式：表头精简 ===== */
        .th-simple {{ display: none; }}
        #fundView.simple-mode .th-full {{ display: none; }}
        #fundView.simple-mode .th-simple {{ display: inline; }}

        /* 简洁模式：整体布局参照首页 —— 两侧各留 5% 空白 */
        #fundView.simple-mode {{
            padding-left: 5%;
            padding-right: 5%;
            box-sizing: border-box;
            max-width: 1440px;
            margin: 0 auto;
            width: 100%;
        }}

        /* 简洁模式：搜索栏缩短 */
        #fundView.simple-mode .search-box-wrap {{
            width: 180px;
        }}

        /* 简洁模式：隐藏不需要的列（保留 1,2,3,4,7,16,17,18,19,20,21） */
        #fundView.simple-mode #fundTable th:nth-child(5),
        #fundView.simple-mode #fundTable th:nth-child(6),
        #fundView.simple-mode #fundTable th:nth-child(8),
        #fundView.simple-mode #fundTable th:nth-child(9),
        #fundView.simple-mode #fundTable th:nth-child(10),
        #fundView.simple-mode #fundTable th:nth-child(11),
        #fundView.simple-mode #fundTable th:nth-child(12),
        #fundView.simple-mode #fundTable th:nth-child(13),
        #fundView.simple-mode #fundTable th:nth-child(14),
        #fundView.simple-mode #fundTable th:nth-child(15),
        #fundView.simple-mode #fundTable th:nth-child(22),
        #fundView.simple-mode #fundTable td:nth-child(5),
        #fundView.simple-mode #fundTable td:nth-child(6),
        #fundView.simple-mode #fundTable td:nth-child(8),
        #fundView.simple-mode #fundTable td:nth-child(9),
        #fundView.simple-mode #fundTable td:nth-child(10),
        #fundView.simple-mode #fundTable td:nth-child(11),
        #fundView.simple-mode #fundTable td:nth-child(12),
        #fundView.simple-mode #fundTable td:nth-child(13),
        #fundView.simple-mode #fundTable td:nth-child(14),
        #fundView.simple-mode #fundTable td:nth-child(15),
        #fundView.simple-mode #fundTable td:nth-child(22) {{
            display: none !important;
        }}

        /* 简洁模式：表头固定布局、解除 min-width、按比例分配列宽 */
        #fundView.simple-mode #fundTable {{
            min-width: 0 !important;
            table-layout: fixed !important;
            width: 100%;
        }}

        /* 简洁模式：收藏列（窄） */
        #fundView.simple-mode #fundTable th:nth-child(1),
        #fundView.simple-mode #fundTable td:nth-child(1) {{
            width: 5%;
            min-width: 40px;
            text-align: center;
        }}

        /* 简洁模式：代码列（窄） */
        #fundView.simple-mode #fundTable th:nth-child(2),
        #fundView.simple-mode #fundTable td:nth-child(2) {{
            width: 7%;
            min-width: 65px;
            text-align: left;
        }}

        /* 简洁模式：基金名称列（宽，主信息） */
        #fundView.simple-mode #fundTable th:nth-child(3),
        #fundView.simple-mode #fundTable td:nth-child(3) {{
            width: 22%;
            min-width: 150px;
            text-align: left;
            white-space: normal;
            word-break: break-word;
        }}

        /* 简洁模式：最新规模列 */
        #fundView.simple-mode #fundTable th:nth-child(4),
        #fundView.simple-mode #fundTable td:nth-child(4) {{
            width: 8%;
            min-width: 70px;
            text-align: left;
        }}

        /* 简洁模式：申购状态/限额列（宽度与近一周一致） */
        #fundView.simple-mode #fundTable th:nth-child(7),
        #fundView.simple-mode #fundTable td:nth-child(7) {{
            width: 8.5%;
            min-width: 80px;
            text-align: left;
        }}

        /* 简洁模式：近一周/近一月/近三月/近半年/近一年/今年内（6 个数值列，统一宽度） */
        #fundView.simple-mode #fundTable th:nth-child(16),
        #fundView.simple-mode #fundTable td:nth-child(16),
        #fundView.simple-mode #fundTable th:nth-child(17),
        #fundView.simple-mode #fundTable td:nth-child(17),
        #fundView.simple-mode #fundTable th:nth-child(18),
        #fundView.simple-mode #fundTable td:nth-child(18),
        #fundView.simple-mode #fundTable th:nth-child(19),
        #fundView.simple-mode #fundTable td:nth-child(19),
        #fundView.simple-mode #fundTable th:nth-child(20),
        #fundView.simple-mode #fundTable td:nth-child(20),
        #fundView.simple-mode #fundTable th:nth-child(21),
        #fundView.simple-mode #fundTable td:nth-child(21) {{
            width: 8.5%;
            min-width: 80px;
            text-align: right;
        }}

        /* 简洁模式：展开行只保留折线图 */
        #fundView.simple-mode .holding-row .holdings-container,
        #fundView.simple-mode .holding-row .country-card {{
            display: none !important;
        }}
        #fundView.simple-mode .holding-row .right-chart-wrapper {{
            flex: 0 0 100% !important;
            width: 100% !important;
        }}
        #fundView.simple-mode .holding-row .chart-container {{
            flex: 1 1 100% !important;
            min-height: 260px;
        }}


    </style>
</head>
<body>
    <header class="main-navbar">
        <div class="nav-brand">
            <span>📈 资产量化与策略看板</span>
            {mode_badge}
        </div>
        <div class="nav-tabs-group">
            <button class="nav-tab-btn active" data-view="homeView">🏠 首页概览</button>
            <button class="nav-tab-btn" data-view="fundView">📊 基金量化看板</button>
        </div>
        <div class="nav-right-tools">
            <button class="theme-toggle" id="themeToggle">🌓 切换主题</button>
        </div>
    </header>

    <main class="views-container">
        <!-- 视图 1：首页 -->
        <section id="homeView" class="view-pane active">
            <div class="home-container">
                
                <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
                    <h3 style="margin: 0; font-size: 16px; color: var(--header-text); border-left: 4px solid var(--link-color); padding-left: 8px;">🌐 核心宏观风向标</h3>
                    <span style="font-size: 12px; color: var(--footer-text);">更新时间: {update_time_str}</span>
                </div>
                <div class="macro-metrics-grid">
                    <div class="metric-card">
                        <div class="metric-header">
                            <span>CNN 恐慌贪婪指数</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#1a73e8;">{fng['score']}</span>
                            <span class="metric-tag" style="background:rgba(26,115,232,0.12); color:#1a73e8;">{fng['rating']}</span>
                        </div>
                        <div class="fng-bar-track">
                            <div class="fng-bar-pointer" style="left: {fng['score']}%;"></div>
                        </div>
                        <div class="metric-desc">
                            0~25 极恐 | 26~45 恐惧 | 46~54 中性 | 55~75 贪婪 | 76~100 极贪
                        </div>
                        <a href="{fng['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {fng['source']} ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>VIX 恐慌指数</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#d93025;">{vix['val']}</span>
                            <span class="metric-tag" style="background:rgba(217,48,37,0.12); color:#d93025;">{vix['status']}</span>
                        </div>
                        <div class="metric-desc">
                            &lt;15 平稳低波 | 15~20 正常震荡 | 20~30 警惕波动 | &gt;30 极度恐慌
                        </div>
                        <a href="{vix['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: CBOE 官方 (_VIX) ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>USD/CNY 汇率</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#188038;">{usdcny['val']}</span>
                            <span class="metric-tag" style="background:rgba(24,128,56,0.12); color:#188038;">{usdcny['status']}</span>
                        </div>
                        <div class="metric-desc">
                            美元兑人民币汇率，QDII换汇成本及折溢价关键锚
                        </div>
                        <a href="{usdcny['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: 新浪外汇 (实时) ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>VXN 纳指波动率</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#34a853;">{vxn['val']}</span>
                            <span class="metric-tag" style="background:rgba(52,168,83,0.12); color:#34a853;">波动平缓</span>
                        </div>
                        <div class="metric-desc">
                            纳斯达克100期权隐波，监测科技成长股杀估值抛压
                        </div>
                        <a href="{vxn['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: CBOE 官方 (_VXN) ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>SKEW 黑天鹅偏斜</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#e67e22;">{skew['val']}</span>
                            <span class="metric-tag" style="background:rgba(230,126,34,0.12); color:#e67e22;">尾部黑天鹅预警</span>
                        </div>
                        <div class="metric-desc">
                            基准100。&gt;135提示期权市场尾部极度对冲成本升高
                        </div>
                        <a href="{skew['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: CBOE 官方 (_SKEW) ↗
                        </a>
                    </div>

                    <!-- 【新增】止盈三信号面板（默认折叠） -->
                    {stop_profit_html}
                </div>

                <!-- ===== 大宗商品风向标 ===== -->
                <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                    <h3 style="margin: 0; font-size: 16px; color: var(--header-text); border-left: 4px solid var(--link-color); padding-left: 8px;">🛢️ 大宗商品风向标</h3>
                    <span style="font-size: 12px; color: var(--footer-text);">更新时间: {update_time_str}</span>
                </div>
                <div class="macro-metrics-grid">
                    <div class="metric-card">
                        <div class="metric-header">
                            <span>伦敦金 (XAU/USD)</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#f39c12;">{gold_london['val']}</span>
                            <span class="metric-tag" style="background:rgba(243,156,18,0.12); color:{gold_tag_color};">{gold_london['status']}</span>
                        </div>
                        <div class="metric-desc">
                            {gold_london['desc']}
                        </div>
                        <a href="{gold_london['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {gold_london['source']} ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>沪金主连 (AUM / AU0)</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#e67e22;">{gold_shfe['val']}</span>
                            <span class="metric-tag" style="background:rgba(230,126,34,0.12); color:{gold_shfe_tag_color};">{gold_shfe['status']}</span>
                        </div>
                        <div class="metric-desc">
                            {gold_shfe['desc']}
                        </div>
                        <a href="{gold_shfe['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {gold_shfe['source']} ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>伦敦银 (XAG/USD)</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#95a5a6;">{silver_london['val']}</span>
                            <span class="metric-tag" style="background:rgba(149,165,166,0.12); color:{silver_tag_color};">{silver_london['status']}</span>
                        </div>
                        <div class="metric-desc">
                            {silver_london['desc']}
                        </div>
                        <a href="{silver_london['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {silver_london['source']} ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>LME铜 (CAD)</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#b87333;">{copper_lme['val']}</span>
                            <span class="metric-tag" style="background:rgba(184,115,51,0.12); color:{copper_tag_color};">{copper_lme['status']}</span>
                        </div>
                        <div class="metric-desc">
                            {copper_lme['desc']}
                        </div>
                        <a href="{copper_lme['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {copper_lme['source']} ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>布伦特原油 (BZ=F)</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#2c3e50;">{brent['val']}</span>
                            <span class="metric-tag" style="background:rgba(44,62,80,0.12); color:{brent_tag_color};">{brent['status']}</span>
                        </div>
                        <div class="metric-desc">
                            {brent['desc']}
                        </div>
                        <a href="{brent['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {brent['source']} ↗
                        </a>
                    </div>

                    <div class="metric-card">
                        <div class="metric-header">
                            <span>比特币 (BTC/USDT)</span>
                        </div>
                        <div class="metric-body">
                            <span class="metric-value" style="color:#f7931a;">{btc['val']}</span>
                            <span class="metric-tag" style="background:rgba(247,147,26,0.12); color:{btc_tag_color};">{btc['status']}</span>
                        </div>
                        <div class="metric-desc">
                            {btc['desc']}
                        </div>
                        <a href="{btc['url']}" target="_blank" class="metric-source-link" title="点击跳转至源数据官方网页">
                            🔗 来源: {btc['source']} ↗
                        </a>
                    </div>
                </div>

                <!-- ===== 宽基指数估值 ===== -->
                <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                    <h3 style="margin: 0; font-size: 16px; color: var(--header-text); border-left: 4px solid var(--link-color); padding-left: 8px;">📊 宽基指数估值 {index_source_link_html}</h3>
                    <span style="font-size: 12px; color: var(--footer-text);">更新时间: {update_time_str}</span>
                </div>
                <div class="index-metrics-grid">
                    {index_cards_html}
                </div>

                {index_annual_html}

                <h3 style="margin: 0; font-size: 16px; color: var(--header-text); border-left: 4px solid var(--link-color); padding-left: 8px;">🏛️ 美联储利率观测器</h3>
                {fed_monitor_html}

                <h3 style="margin: 0; font-size: 16px; color: var(--header-text); border-left: 4px solid var(--link-color); padding-left: 8px;">🔗 研投工具导航</h3>
                {friend_cards_html}
            </div>
        </section>

        <!-- 视图 2：基金量化看板 -->
        <section id="fundView" class="view-pane">
            <div class="dca-mobile-row" style="display: flex; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; align-items: stretch;">

                <!-- 申购状态栏（移动端同时作为统一工具栏） -->
                <div class="buy-status-filter-card" style="background: var(--table-bg); border: 1px solid var(--border); border-radius: 8px; padding: 6px 12px; display: flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); flex-wrap: wrap; min-height: 42px; box-sizing: border-box; align-self: stretch;">
                    <div class="buy-status-main-row">
                        <span class="category-title" style="margin-right: 4px;">申购状态:</span>
                        <button class="cat-btn buy-filter active" data-buy="all">全部</button>
                        <button class="cat-btn buy-filter" data-buy="open">仅开放申购</button>
                        <button class="cat-btn buy-filter" data-buy="closed">暂停申购</button>
                    </div>

                    <!-- 移动端专用：面板切换按钮（桌面端隐藏） -->
                    <div class="mobile-panel-switches">
                        <button type="button" class="mobile-filter-toggle" id="mobileFilterToggle" title="展开/收起市场大类">
                            <span>📂 大类</span>
                            <span class="mobile-filter-current" id="mobileFilterCurrent">全部</span>
                            <span class="mobile-filter-arrow">▼</span>
                        </button>
                        <button type="button" class="dca-toggle-btn" id="dcaToggleBtn" title="展开/收起定投参数">
                            <span>📊 定投</span>
                            <span id="dcaToggleArrow">▼</span>
                        </button>
                    </div>
                </div>

                <!-- 市场大类面板（移动端默认隐藏，桌面端占满整行显示） -->
                <div class="sub-filter-bar" id="subFilterBar" style="margin-bottom: 0;">
                    <div class="category-nav">
                        <button class="cat-btn macro-filter fav-filter" data-macro="favorites" data-sub="favorites">⭐ 我的自选</button>
                        <span class="category-title" style="margin-left: 6px;">市场大类:</span>
                        <button class="cat-btn macro-filter active" data-macro="all" data-sub="all">全部展示</button>

                        <span class="category-title" style="margin-left: 8px;">美股:</span>
                        <button class="cat-btn macro-filter" data-macro="us_share" data-sub="all">美股全量</button>
                        <button class="cat-btn macro-filter" data-macro="us_share" data-sub="us_active">美股主动</button>
                        <button class="cat-btn macro-filter" data-macro="us_share" data-sub="ndx_passive">纳指被动</button>
                        <button class="cat-btn macro-filter" data-macro="us_share" data-sub="spx_passive">标普被动</button>

                        <span class="category-title" style="margin-left: 8px;">A股板块:</span>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="all">A股全量</button>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="cpo">CPO</button>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="storage">存储芯片</button>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="semiconductor">半导体材料</button>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="ai">人工智能</button>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="grid">电网设备</button>
                        <button class="cat-btn macro-filter" data-macro="a_share" data-sub="robot">机器人</button>

                        <span class="category-title" style="margin-left: 8px;">其他:</span>
                        <button class="cat-btn macro-filter" data-macro="other" data-sub="commodities">大宗商品</button>
                        <button class="cat-btn macro-filter" data-macro="other" data-sub="crypto">加密货币</button>
                        <button class="cat-btn macro-filter" data-macro="other" data-sub="index">主流指数</button>
                        
                        <span class="category-title" style="margin-left: 8px;">视图:</span>
                        <button class="cat-btn view-mode-btn active" data-view-mode="default" title="默认模式：完整列 + 持仓/持有人/国家/图表">📋 默认</button>
                        <button class="cat-btn view-mode-btn" data-view-mode="simple" title="简洁模式：精简列 + 仅折线图">⚡ 简洁</button>
                    </div>

                    <div class="search-box-wrap">
                        <input type="text" id="searchInput" placeholder="🔍 搜索代码或名称...">
                    </div>
                </div>

                <!-- 定投参数面板（移动端默认隐藏，桌面端与原申购状态并排） -->
                <div class="global-dca-filter-card" id="gDcaCard" style="margin-bottom: 0; flex: 1; min-width: 320px; align-self: stretch;">
                    <div class="global-dca-filter-header" style="cursor: default;">
                        <span class="global-dca-filter-title">📊 动态定投参数配置</span>
                    </div>
                    <div class="global-dca-filter-body" id="gDcaBody">
                        <select id="gDcaFreq">
                            <option value="daily">每日定投</option>
                            <option value="weekly">每周定投</option>
                            <option value="biweekly">双周定投</option>
                            <option value="monthly" selected>每月定投</option>
                        </select>
                        <select id="gDcaDaySelect"></select>
                        <select id="gDcaRange">
                            <option value="half">近半年内</option>
                            <option value="year" selected>近一年内</option>
                            <option value="ytd">今年以来</option>
                            <option value="all">统计区间全序列</option>
                        </select>
                        <button id="gDcaApplyBtn">计算并刷新排序</button>
                    </div>
                </div>
            </div>

            <div class="table-container">
                <table id="fundTable">
                    <thead>
                        <tr>
                            <th data-col="0" onclick="handleHeaderClick(0)"><span class="th-full">收藏</span><span class="th-simple">★</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="1" onclick="handleHeaderClick(1)"><span class="th-full">代码</span><span class="th-simple">代码</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="2" onclick="handleHeaderClick(2)"><span class="th-full">基金名称 / 赎回费率阶梯</span><span class="th-simple">名称</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="3" onclick="handleHeaderClick(3)"><span class="th-full">最新规模</span><span class="th-simple">规模</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="4" onclick="handleHeaderClick(4)">运作费(管/托/销) <span class="sort-icon">⇅</span></th>
                            <th data-col="5" onclick="handleHeaderClick(5)">申购费率 <span class="sort-icon">⇅</span></th>
                            <th data-col="6" onclick="handleHeaderClick(6)"><span class="th-full">申购状态/限额</span><span class="th-simple">状态</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="7" onclick="handleHeaderClick(7)">最高净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="8" onclick="handleHeaderClick(8)">最低净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="9" onclick="handleHeaderClick(9)">最新净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="10" onclick="handleHeaderClick(10)">最大回撤 <span class="sort-icon">⇅</span></th>
                            <th data-col="11" onclick="handleHeaderClick(11)">自低点反弹 <span class="sort-icon">⇅</span></th>
                            <th data-col="12" onclick="handleHeaderClick(12)">修复程度 <span class="sort-icon">⇅</span></th>
                            <th data-col="13" onclick="handleHeaderClick(13)">修复时间 <span class="sort-icon">⇅</span></th>
                            <th data-col="14" onclick="handleHeaderClick(14)">{col_today_title} <span class="sort-icon">⇅</span></th>
                            <th data-col="15" onclick="handleHeaderClick(15)"><span class="th-full">近一周</span><span class="th-simple">近一周</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="16" onclick="handleHeaderClick(16)"><span class="th-full">近一月</span><span class="th-simple">近一月</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="17" onclick="handleHeaderClick(17)"><span class="th-full">近三月</span><span class="th-simple">近三月</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="18" onclick="handleHeaderClick(18)"><span class="th-full">近半年</span><span class="th-simple">近半年</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="19" onclick="handleHeaderClick(19)"><span class="th-full">近一年</span><span class="th-simple">近一年</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="20" onclick="handleHeaderClick(20)"><span class="th-full">今年内</span><span class="th-simple">今年内</span> <span class="sort-icon">⇅</span></th>
                            <th data-col="21" onclick="handleHeaderClick(21)"><span class="th-full"><span id="dcaHeaderTitle">月定投</span>收益</span><span class="th-simple">定投</span> <span class="sort-icon">⇅</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                        {empty_row}
                    </tbody>
                </table>
            </div>

            <div class="footer-note">
                <div class="footer-left">
                    <span>💡 <strong>使用提示：</strong> 点击首列 ☆ 添加自选；点击行内「📊 定投」呼出单只回测小工具；点击基金行展开左侧持仓及持有人结构，右侧查看国家资产分布环状图(1/4)与双轴走势图(3/4)。</span>
                </div>
                <div class="footer-right">
                    <span>⏱️ 统计更新于: <strong>{update_time_str}</strong></span>
                </div>
            </div>
        </section>
    </main>

    <!-- 定投独立测算弹窗 -->
    <div class="modal-overlay" id="dcaModal">
        <div class="modal-card">
            <div class="modal-header">
                <h3 id="dcaModalTitle">📊 智能定投/回测测算小工具</h3>
                <button class="modal-close" id="closeDcaModal">&times;</button>
            </div>
            <div class="modal-body">
                <div class="dca-controls">
                    <div class="dca-field">
                        <label>定投频次</label>
                        <select id="dcaFreq">
                            <option value="daily">每日定投</option>
                            <option value="weekly">每周定投</option>
                            <option value="biweekly">每两周定投</option>
                            <option value="monthly" selected>每月定投</option>
                        </select>
                    </div>
                    <div class="dca-field" id="dcaDayField">
                        <label id="dcaDayLabel">扣款日 (每月几号)</label>
                        <select id="dcaDaySelect"></select>
                    </div>
                    <div class="dca-field">
                        <label>每期金额 (元)</label>
                        <input type="number" id="dcaAmount" value="1000" min="10" step="100">
                    </div>
                    <div class="dca-field">
                        <label>测算周期</label>
                        <select id="dcaRange">
                            <option value="half">近半年内</option>
                            <option value="year" selected>近一年内</option>
                            <option value="ytd">今年以来</option>
                            <option value="all">统计区间全序列</option>
                        </select>
                    </div>
                    <button class="dca-run-btn" id="dcaRunBtn">🚀 刷新测算图表</button>
                </div>

                <div class="dca-results-grid">
                    <div class="dca-result-card">
                        <div class="dca-result-title">累计投入期数 / 本金</div>
                        <div class="dca-result-value" id="resTotalInvest">--</div>
                    </div>
                    <div class="dca-result-card">
                        <div class="dca-result-title">定投期末总资产</div>
                        <div class="dca-result-value" id="resTotalAsset" style="color: var(--link-color);">--</div>
                    </div>
                    <div class="dca-result-card">
                        <div class="dca-result-title">总收益额 (元)</div>
                        <div class="dca-result-value" id="resProfit">--</div>
                    </div>
                    <div class="dca-result-card">
                        <div class="dca-result-title">定投总收益率</div>
                        <div class="dca-result-value" id="resReturnRate">--</div>
                    </div>
                    <div class="dca-result-card">
                        <div class="dca-result-title">持仓均价 / 最新价</div>
                        <div class="dca-result-value" id="resAvgPrice">--</div>
                    </div>
                </div>

                <div class="dca-chart-box">
                    <canvas id="dcaChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        var fundNavData = {json.dumps(nav_data_json, ensure_ascii=False)};
        var fundNames = {json.dumps(fund_names_json, ensure_ascii=False)};
        var fundParsedDates = {{}};

        // Tab 切换
        document.querySelectorAll('.nav-tab-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
                this.classList.add('active');
                const targetView = document.getElementById(this.dataset.view);
                if (targetView) targetView.classList.add('active');
            }});
        }});

        // 主题切换
        (function() {{
            const toggle = document.getElementById('themeToggle');
            const currentTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', currentTheme);
            toggle.textContent = currentTheme === 'dark' ? '☀️ 亮色' : '🌓 暗色';
            toggle.addEventListener('click', function() {{
                const current = document.documentElement.getAttribute('data-theme');
                const next = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                localStorage.setItem('theme', next);
                toggle.textContent = next === 'dark' ? '☀️ 亮色' : '🌓 暗色';
                window._crosshairLineColor = null;
            }});
        }})();

        // 【新增】美股止盈三信号面板折叠切换
        (function() {{
            const header = document.getElementById('stopProfitHeader');
            const body = document.getElementById('stopProfitBody');
            const icon = document.getElementById('stopProfitToggleIcon');
            if (header && body && icon) {{
                header.addEventListener('click', function() {{
                    const isCollapsed = body.style.display === 'none';
                    body.style.display = isCollapsed ? 'block' : 'none';
                    icon.textContent = isCollapsed ? '▼' : '▶';
                }});
            }}
        }})();

        // 【改造】指数历年回报视图模式切换 + 柱状图支持
        function toggleAnnualView(idxName, mode) {{
            const container = document.getElementById('annual-view-' + idxName);
            if (!container) return;
            const cardView = document.getElementById('annual-card-' + idxName);
            const heatmapView = document.getElementById('annual-heatmap-' + idxName);
            const barView = document.getElementById('annual-bar-' + idxName);
            const buttons = container.parentElement.querySelectorAll('.mode-toggle-btn');

            buttons.forEach(btn => {{
                if (btn.getAttribute('data-mode') === mode) {{
                    btn.classList.add('active');
                }} else {{
                    btn.classList.remove('active');
                }}
            }});

            if (cardView) cardView.style.display = (mode === 'card') ? 'block' : 'none';
            if (heatmapView) heatmapView.style.display = (mode === 'heatmap') ? 'block' : 'none';
            if (barView) barView.style.display = (mode === 'bar') ? 'block' : 'none';

            if (mode === 'bar') {{
                setTimeout(() => initAnnualBarChart(idxName), 60);
            }}
        }}

        // 【新增】柱状图初始化（参考 Yahoo Finance 风格）
        function initAnnualBarChart(idxName) {{
            const canvas = document.getElementById('annual-bar-chart-' + idxName);
            if (!canvas) return;
            if (canvas._chartInstance) {{
                try {{ canvas._chartInstance.destroy(); }} catch(e) {{}}
                canvas._chartInstance = null;
            }}

            let data = [];
            try {{
                data = JSON.parse(canvas.getAttribute('data-bar')) || [];
            }} catch(e) {{ return; }}
            if (!data.length) return;

            const labels = data.map(d => String(d.year));
            const values = data.map(d => d.pct);
            const closes = data.map(d => d.close);
            const avg = values.reduce((a, b) => a + b, 0) / values.length;

            const avgLinePlugin = {{
                id: 'avgLinePlugin_' + idxName,
                afterDatasetsDraw(chart) {{
                    const ctx = chart.ctx;
                    const chartArea = chart.chartArea;
                    const yScale = chart.scales.y;
                    if (!yScale || !chartArea) return;
                    const yPos = yScale.getPixelForValue(avg);
                    if (yPos < chartArea.top || yPos > chartArea.bottom) return;

                    ctx.save();
                    ctx.strokeStyle = '#f39c12';
                    ctx.setLineDash([5, 4]);
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.moveTo(chartArea.left, yPos);
                    ctx.lineTo(chartArea.right, yPos);
                    ctx.stroke();
                    ctx.restore();

                    ctx.save();
                    ctx.fillStyle = '#f39c12';
                    ctx.font = 'bold 10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto';
                    ctx.textAlign = 'left';
                    ctx.textBaseline = 'bottom';
                    ctx.fillText(`均值 ${{avg >= 0 ? '+' : ''}}${{avg.toFixed(2)}}%`, chartArea.left + 6, yPos - 3);
                    ctx.restore();
                }}
            }};

            const ctx = canvas.getContext('2d');
            canvas._chartInstance = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: '年度收益',
                        data: values,
                        backgroundColor: values.map(v => v >= 0 ? 'rgba(38, 166, 154, 0.85)' : 'rgba(239, 83, 80, 0.85)'),
                        borderColor: values.map(v => v >= 0 ? '#26a69a' : '#ef5350'),
                        borderWidth: 1,
                        borderRadius: 2,
                        barPercentage: 0.75,
                        categoryPercentage: 0.9
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: 'rgba(30, 30, 30, 0.92)',
                            padding: 10,
                            cornerRadius: 6,
                            callbacks: {{
                                title: (items) => `年份: ${{items[0].label}}`,
                                label: (c) => {{
                                    const val = c.parsed.y;
                                    const sign = val >= 0 ? '+' : '';
                                    return [
                                        `涨跌幅: ${{sign}}${{val.toFixed(2)}}%`,
                                        `年末收盘: ${{closes[c.dataIndex] != null ? Number(closes[c.dataIndex]).toLocaleString() : '--'}}`
                                    ];
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ font: {{ size: 9 }}, maxRotation: 0, autoSkip: true, maxTicksLimit: 20 }},
                            grid: {{ display: false }}
                        }},
                        y: {{
                            ticks: {{
                                font: {{ size: 9 }},
                                callback: (v) => v + '%'
                            }},
                            grid: {{ color: 'rgba(0,0,0,0.05)' }}
                        }}
                    }}
                }},
                plugins: [avgLinePlugin]
            }});
        }}

        // 自选管理模块 (Local Storage)
        const FavManager = {{
            STORAGE_KEY: 'fav_funds_list',
            getFavs: function() {{
                try {{
                    return JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
                }} catch (e) {{
                    return [];
                }}
            }},
            isFav: function(code) {{
                return this.getFavs().includes(code);
            }},
            toggleFav: function(code) {{
                let favs = this.getFavs();
                if (favs.includes(code)) {{
                    favs = favs.filter(c => c !== code);
                }} else {{
                    favs.push(code);
                }}
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify(favs));
                return favs.includes(code);
            }}
        }};

        // 定投回测计算核心函数
        function computeDCA(code, freq, targetDay, perAmount, range) {{
            const raw = fundNavData[code];
            if (!raw || !raw.dates || raw.dates.length < 2) return null;

            const allDates = raw.dates;
            const allNavs = raw.navs;
            
            let parsedDates = fundParsedDates[code];
            if (!parsedDates || parsedDates.length !== allDates.length) {{
                parsedDates = allDates.map(d => new Date(d));
                fundParsedDates[code] = parsedDates;
            }}
            
            const latestDate = parsedDates[parsedDates.length - 1];
            let startDate = new Date(latestDate);

            if (range === 'half') {{
                startDate.setMonth(latestDate.getMonth() - 6);
            }} else if (range === 'year') {{
                startDate.setFullYear(latestDate.getFullYear() - 1);
            }} else if (range === 'ytd') {{
                startDate = new Date(latestDate.getFullYear(), 0, 1);
            }} else {{
                startDate = parsedDates[0];
            }}

            const filtered = [];
            for (let i = 0; i < allDates.length; i++) {{
                const d = parsedDates[i];
                if (d >= startDate) {{
                    filtered.push({{ date: allDates[i], dt: d, nav: allNavs[i] }});
                }}
            }}

            if (filtered.length < 2) return null;

            let totalInvest = 0;
            let totalShares = 0;
            let investCount = 0;
            let lastInvestKey = '';

            const timelineDates = [];
            const timelineCost = [];
            const timelineValue = [];

            filtered.forEach(item => {{
                let shouldBuy = false;
                const dayOfWeek = item.dt.getDay(); 
                const dayOfMonth = item.dt.getDate();

                if (freq === 'daily') {{
                    shouldBuy = true;
                }} else if (freq === 'weekly') {{
                    const oneJan = new Date(item.dt.getFullYear(), 0, 1);
                    const weekNum = Math.ceil((((item.dt - oneJan) / 86400000) + oneJan.getDay() + 1) / 7);
                    const weekKey = `${{item.dt.getFullYear()}}-W${{weekNum}}`;
                    if (dayOfWeek >= targetDay && lastInvestKey !== weekKey) {{
                        shouldBuy = true;
                        lastInvestKey = weekKey;
                    }}
                }} else if (freq === 'biweekly') {{
                    const oneJan = new Date(item.dt.getFullYear(), 0, 1);
                    const weekNum = Math.ceil((((item.dt - oneJan) / 86400000) + oneJan.getDay() + 1) / 7);
                    const biweekBlock = Math.floor(weekNum / 2);
                    const biweekKey = `${{item.dt.getFullYear()}}-BW${{biweekBlock}}`;
                    if (dayOfWeek >= targetDay && lastInvestKey !== biweekKey) {{
                        shouldBuy = true;
                        lastInvestKey = biweekKey;
                    }}
                }} else {{
                    const monthKey = `${{item.dt.getFullYear()}}-${{item.dt.getMonth() + 1}}`;
                    if (dayOfMonth >= targetDay && lastInvestKey !== monthKey) {{
                        shouldBuy = true;
                        lastInvestKey = monthKey;
                    }}
                }}

                if (shouldBuy) {{
                    const buyShares = perAmount / item.nav;
                    totalShares += buyShares;
                    totalInvest += perAmount;
                    investCount++;
                }}

                const currentVal = totalShares * item.nav;
                timelineDates.push(item.date);
                timelineCost.push(Number(totalInvest.toFixed(2)));
                timelineValue.push(Number(currentVal.toFixed(2)));
            }});

            const latestItem = filtered[filtered.length - 1];
            const finalAsset = totalShares * latestItem.nav;
            const profit = finalAsset - totalInvest;
            const returnRate = totalInvest > 0 ? (profit / totalInvest) * 100 : 0;
            const avgPrice = totalShares > 0 ? totalInvest / totalShares : 0;

            return {{
                investCount, totalInvest, finalAsset, profit, returnRate, avgPrice,
                latestNav: latestItem.nav, timelineDates, timelineCost, timelineValue
            }};
        }}

        function buildDayOptions(freqSelectId, daySelectId, labelId) {{
            const freq = document.getElementById(freqSelectId).value;
            const daySelect = document.getElementById(daySelectId);
            const label = labelId ? document.getElementById(labelId) : null;
            
            daySelect.innerHTML = '';
            if (freq === 'daily') {{
                if (label) label.parentElement.style.display = 'none';
                else daySelect.style.display = 'none';
            }} else if (freq === 'weekly' || freq === 'biweekly') {{
                if (label) {{
                    label.parentElement.style.display = 'flex';
                    label.textContent = freq === 'weekly' ? '扣款日 (每周几)' : '扣款日 (每两周周几)';
                }} else {{
                    daySelect.style.display = 'inline-block';
                }}
                const weeks = ['周一', '周二', '周三', '周四', '周五'];
                weeks.forEach((w, i) => {{
                    const opt = document.createElement('option');
                    opt.value = i + 1; opt.textContent = w;
                    if (i === 0) opt.selected = true;
                    daySelect.appendChild(opt);
                }});
            }} else {{
                if (label) {{
                    label.parentElement.style.display = 'flex';
                    label.textContent = '扣款日 (每月几号)';
                }} else {{
                    daySelect.style.display = 'inline-block';
                }}
                for (let i = 1; i <= 28; i++) {{
                    const opt = document.createElement('option');
                    opt.value = i; opt.textContent = i + ' 号';
                    if (i === 1) opt.selected = true;
                    daySelect.appendChild(opt);
                }}
            }}
        }}

        function updateTableDca() {{
            const freq = document.getElementById('gDcaFreq').value;
            const targetDay = parseInt(document.getElementById('gDcaDaySelect').value) || 1;
            const range = document.getElementById('gDcaRange').value;

            const headerTitle = document.getElementById('dcaHeaderTitle');
            if (headerTitle) {{
                const map = {{'daily':'日','weekly':'周','biweekly':'双周','monthly':'月'}};
                headerTitle.textContent = (map[freq] || '') + '定投';
            }}

            document.querySelectorAll('#fundTable tbody tr.fund-row').forEach(row => {{
                const code = row.getAttribute('data-code');
                const res = computeDCA(code, freq, targetDay, 1000, range);
                const dcaCell = row.querySelector('.dca-col');
                
                if (dcaCell) {{
                    if (res && res.returnRate !== undefined) {{
                        const rate = res.returnRate;
                        dcaCell.setAttribute('data-val', rate);
                        const sign = rate > 0 ? '+' : '';
                        const colorClass = rate > 0 ? 'gain-positive' : (rate < 0 ? 'gain-negative' : '');
                        dcaCell.className = `dca-col ${{colorClass}}`;
                        dcaCell.innerHTML = `${{sign}}${{rate.toFixed(2)}}%`;
                    }} else {{
                        dcaCell.setAttribute('data-val', -9999);
                        dcaCell.className = 'dca-col';
                        dcaCell.innerHTML = '--';
                    }}
                }}
            }});

            if (currentSortCol === 21) {{
                isAscending = !isAscending; 
                sortTable(21);
            }}
        }}

        let currentDcaCode = null;
        let dcaChartInstance = null;

        (function() {{
            const modal = document.getElementById('dcaModal');
            const closeBtn = document.getElementById('closeDcaModal');
            const modalTitle = document.getElementById('dcaModalTitle');
            const freqSelect = document.getElementById('dcaFreq');
            const runBtn = document.getElementById('dcaRunBtn');

            buildDayOptions('dcaFreq', 'dcaDaySelect', 'dcaDayLabel');
            freqSelect.addEventListener('change', () => buildDayOptions('dcaFreq', 'dcaDaySelect', 'dcaDayLabel'));

            buildDayOptions('gDcaFreq', 'gDcaDaySelect', null);
            document.getElementById('gDcaFreq').addEventListener('change', () => buildDayOptions('gDcaFreq', 'gDcaDaySelect', null));
            document.getElementById('gDcaApplyBtn').addEventListener('click', updateTableDca);

            window.openDcaModal = function(code) {{
                currentDcaCode = code;
                const name = fundNames[code] || code;
                modalTitle.textContent = `📊 定投测算: [${{code}}] ${{name}}`;
                modal.classList.add('show');
                runBacktestModal();
            }};

            closeBtn.addEventListener('click', () => modal.classList.remove('show'));
            modal.addEventListener('click', (e) => {{ if (e.target === modal) modal.classList.remove('show'); }});
            runBtn.addEventListener('click', runBacktestModal);

            function runBacktestModal() {{
                if (!currentDcaCode) return;
                const freq = freqSelect.value;
                const targetDay = parseInt(document.getElementById('dcaDaySelect').value) || 1;
                const perAmount = parseFloat(document.getElementById('dcaAmount').value) || 1000;
                const range = document.getElementById('dcaRange').value;

                const res = computeDCA(currentDcaCode, freq, targetDay, perAmount, range);
                if (!res) return;

                document.getElementById('resTotalInvest').innerHTML = `${{res.investCount}} 期 / <strong>${{res.totalInvest.toLocaleString()}}</strong> 元`;
                document.getElementById('resTotalAsset').innerHTML = `<strong>${{res.finalAsset.toFixed(2)}}</strong> 元`;
                
                const profitElem = document.getElementById('resProfit');
                profitElem.textContent = `${{res.profit >= 0 ? '+' : ''}}${{res.profit.toFixed(2)}}`;
                profitElem.style.color = res.profit >= 0 ? '#d93025' : '#188038';

                const rateElem = document.getElementById('resReturnRate');
                rateElem.textContent = `${{res.returnRate >= 0 ? '+' : ''}}${{res.returnRate.toFixed(2)}}%`;
                rateElem.style.color = res.returnRate >= 0 ? '#d93025' : '#188038';

                document.getElementById('resAvgPrice').innerHTML = `${{res.avgPrice.toFixed(4)}} / ${{res.latestNav.toFixed(4)}}`;

                const ctx = document.getElementById('dcaChart').getContext('2d');
                if (dcaChartInstance) dcaChartInstance.destroy();

                dcaChartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: res.timelineDates,
                        datasets: [
                            {{ label: '总资产 (元)', data: res.timelineValue, borderColor: '#1a73e8', backgroundColor: 'rgba(26, 115, 232, 0.08)', fill: true, pointRadius: 0, borderWidth: 2, tension: 0.1 }},
                            {{ label: '累计本金 (元)', data: res.timelineCost, borderColor: '#e67e22', borderDash: [4, 4], pointRadius: 0, borderWidth: 1.5, fill: false }}
                        ]
                    }},
                    options: {{
                        responsive: true, maintainAspectRatio: false, interaction: {{ mode: 'index', intersect: false }},
                        plugins: {{ legend: {{ display: true, position: 'top', labels: {{ font: {{ size: 10 }}, boxWidth: 12 }} }} }},
                        scales: {{
                            x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 9 }} }}, grid: {{ display: false }} }},
                            y: {{ ticks: {{ font: {{ size: 9 }} }}, grid: {{ color: 'rgba(0,0,0,0.05)' }} }}
                        }}
                    }}
                }});
            }}
        }})();

        document.addEventListener('DOMContentLoaded', function() {{
            const macroBtns = document.querySelectorAll('.macro-filter');
            const buyBtns = document.querySelectorAll('.buy-filter');
            const searchInput = document.getElementById('searchInput');
            const emptyRow = document.getElementById('empty-row');
            const allRows = document.querySelectorAll('#fundTable tbody tr:not(#empty-row)');
            
            let currentMacro = 'all';
            let currentSub = 'all';
            let currentBuyStatus = 'all';
            let searchKeyword = '';

            setTimeout(updateTableDca, 100);

            function syncFavDisplay() {{
                document.querySelectorAll('.star-btn').forEach(btn => {{
                    const code = btn.getAttribute('data-code');
                    const isF = FavManager.isFav(code);
                    const td = btn.closest('td');
                    if (isF) {{
                        btn.classList.add('starred');
                        btn.textContent = '★';
                        if (td) td.setAttribute('data-val', '1');
                    }} else {{
                        btn.classList.remove('starred');
                        btn.textContent = '☆';
                        if (td) td.setAttribute('data-val', '0');
                    }}
                }});
            }}
            syncFavDisplay();

            document.getElementById('fundTable').addEventListener('click', function(e) {{
                const starBtn = e.target.closest('.star-btn');
                if (starBtn) {{
                    e.stopPropagation();
                    const code = starBtn.getAttribute('data-code');
                    FavManager.toggleFav(code);
                    syncFavDisplay();
                    if (currentMacro === 'favorites') {{
                        applyFilters();
                    }}
                }}
            }});

            function applyFilters() {{
                let hasVisible = false;
                const keyword = searchKeyword.trim().toLowerCase();
                const favList = FavManager.getFavs();

                allRows.forEach(row => {{
                    if (row.classList.contains('holding-row')) return;
                    const macro = row.getAttribute('data-macro');
                    const sub = row.getAttribute('data-group');
                    const buyStatus = row.getAttribute('data-buy-status') || '';
                    const nameCell = row.querySelector('.name a');
                    const name = nameCell ? nameCell.textContent.toLowerCase() : '';
                    const codeCell = row.querySelector('.code');
                    const code = codeCell ? codeCell.textContent.toLowerCase() : '';

                    let matchCategory = false;
                    if (currentMacro === 'favorites') {{
                        matchCategory = favList.includes(code.toUpperCase()) || favList.includes(code.toLowerCase());
                    }} else if (currentMacro === 'all') {{
                        matchCategory = true;
                    }} else if (currentSub === 'all') {{
                        matchCategory = (macro === currentMacro);
                    }} else {{
                        matchCategory = (sub === currentSub);
                    }}

                    let matchBuy = false;
                    if (currentBuyStatus === 'all') {{
                        matchBuy = true;
                    }} else if (currentBuyStatus === 'open') {{
                        matchBuy = !buyStatus.includes('暂停申购') && !buyStatus.includes('封闭');
                    }} else if (currentBuyStatus === 'closed') {{
                        matchBuy = buyStatus.includes('暂停申购') || buyStatus.includes('封闭');
                    }}

                    const matchSearch = keyword === '' || name.includes(keyword) || code.includes(keyword);
                    const visible = matchCategory && matchSearch && matchBuy;

                    if (visible) {{
                        row.style.display = '';
                        hasVisible = true;
                        const code = row.getAttribute('data-code');
                        const hRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                        if (hRow && hRow.classList.contains('show')) hRow.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                        const code = row.getAttribute('data-code');
                        const hRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                        if (hRow) hRow.style.display = 'none';
                    }}
                }});

                if (emptyRow) {{
                    emptyRow.style.display = hasVisible ? 'none' : '';
                    if (!hasVisible) {{
                        if (currentMacro === 'favorites') {{
                            emptyRow.querySelector('td').textContent = '您尚未收藏任何基金，请点击表格首列 ☆ 进行添加';
                        }} else {{
                            emptyRow.querySelector('td').textContent = keyword ? '未找到匹配基金' : '当前分类与状态暂无数据';
                        }}
                    }}
                }}
            }}

            macroBtns.forEach(btn => {{
                btn.addEventListener('click', function() {{
                    macroBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    currentMacro = this.dataset.macro;
                    currentSub = this.dataset.sub;
                    applyFilters();
                }});
            }});

            buyBtns.forEach(btn => {{
                btn.addEventListener('click', function() {{
                    buyBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    currentBuyStatus = this.dataset.buy;
                    applyFilters();
                }});
            }});

            if (searchInput) {{
                searchInput.addEventListener('input', function() {{
                    searchKeyword = this.value;
                    applyFilters();
                }});
            }}
        }});

        var chartInstances = {{}};
        var holderChartInstances = {{}};
        var countryChartInstances = {{}};

        const pieLabelsPlugin = {{
            id: 'pieLabels',
            afterDraw(chart) {{
                if (chart.config.type !== 'doughnut' && chart.config.type !== 'pie') return;
                const ctx = chart.ctx;
                chart.data.datasets.forEach((dataset, i) => {{
                    const meta = chart.getDatasetMeta(i);
                    meta.data.forEach((element, index) => {{
                        const val = dataset.data[index];
                        if (val <= 8) return;
                        const {{ x, y }} = element.tooltipPosition();
                        ctx.save();
                        ctx.fillStyle = '#ffffff';
                        ctx.font = 'bold 10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
                        ctx.shadowBlur = 3;
                        ctx.fillText(`${{val.toFixed(1)}}%`, x, y);
                        ctx.restore();
                    }});
                }});
            }}
        }};
        Chart.register(pieLabelsPlugin);

        const fundCrosshairPlugin = {{
            id: 'fundCrosshairPlugin',
            afterDraw(chart) {{
                if (!chart._crosshair) return;
                const ctx = chart.ctx;
                const {{ left, right, top, bottom }} = chart.chartArea;
                const {{ x, y }} = chart._crosshair;
                if (x < left || x > right || y < top || y > bottom) return;
                ctx.save();
                ctx.beginPath();
                ctx.setLineDash([4, 4]);
                ctx.lineWidth = 1;
                if (!window._crosshairLineColor) {{
                    window._crosshairLineColor = getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a';
                }}
                ctx.strokeStyle = window._crosshairLineColor;
                ctx.moveTo(x, top);
                ctx.lineTo(x, bottom);
                ctx.moveTo(left, y);
                ctx.lineTo(right, y);
                ctx.stroke();
                ctx.restore();
            }}
        }};
        Chart.register(fundCrosshairPlugin);

        function filterNavData(data, period) {{
            if (!data || !data.dates || data.dates.length === 0) return {{ dates: [], navs: [] }};
            const dates = data.dates;
            const navs = data.navs;
            const latest = new Date(dates[dates.length - 1]);
            let startDate = new Date(latest);
            if (period === 'week') startDate.setDate(latest.getDate() - 7);
            else if (period === 'month') startDate.setMonth(latest.getMonth() - 1);
            else if (period === 'quarter') startDate.setMonth(latest.getMonth() - 3);
            else if (period === 'half') startDate.setMonth(latest.getMonth() - 6);
            else if (period === 'year') startDate.setFullYear(latest.getFullYear() - 1);
            else if (period === 'ytd') startDate = new Date(latest.getFullYear(), 0, 1);

            const indices = [];
            for (let i = 0; i < dates.length; i++) {{
                if (new Date(dates[i]) >= startDate) indices.push(i);
            }}
            if (indices.length === 0) return {{ dates: dates, navs: navs }};
            return {{ dates: indices.map(i => dates[i]), navs: indices.map(i => navs[i]) }};
        }}

        function initHolderChart(code) {{
            const canvas = document.getElementById(`holder-chart-${{code}}`);
            if (!canvas) return;

            if (holderChartInstances[code]) {{
                if (typeof holderChartInstances[code].destroy === 'function') {{
                    holderChartInstances[code].destroy();
                    delete holderChartInstances[code];
                }} else return;
            }}
            
            let holders = [];
            try {{
                holders = JSON.parse(canvas.getAttribute('data-holders')) || [];
            }} catch(e) {{ holders = []; }}
            if (!holders.length) return;

            const labels = holders.map(h => h.name);
            const dataValues = holders.map(h => h.ratio);
            
            const colorPalette = ['#1a73e8', '#ff9800'];

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            const sliceBorderColor = isDark ? '#2a2a2a' : '#f0f2f5';
            const textColor = isDark ? '#e0e0e0' : '#3c4043';

            const ctx = canvas.getContext('2d');
            holderChartInstances[code] = new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: labels,
                    datasets: [{{
                        data: dataValues,
                        backgroundColor: colorPalette.slice(0, labels.length),
                        borderColor: sliceBorderColor,
                        borderWidth: 1.5,
                        borderRadius: 4,
                        hoverOffset: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '58%',
                    animation: {{
                        animateRotate: true,
                        animateScale: true,
                        duration: 900,
                        easing: 'easeOutQuart'
                    }},
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'bottom',
                            labels: {{
                                font: {{ size: 9, weight: '500' }},
                                boxWidth: 7,
                                boxHeight: 7,
                                usePointStyle: true,
                                padding: 5,
                                color: textColor,
                                generateLabels: function(chart) {{
                                    const data = chart.data;
                                    if (data.labels.length && data.datasets.length) {{
                                        return data.labels.map((label, i) => {{
                                            const val = data.datasets[0].data[i];
                                            return {{
                                                text: `${{label}}: ${{val.toFixed(1)}}%`,
                                                fillStyle: data.datasets[0].backgroundColor[i],
                                                strokeStyle: 'transparent',
                                                pointStyle: 'circle',
                                                index: i
                                            }};
                                        }});
                                    }}
                                    return [];
                                }}
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(30, 30, 30, 0.85)',
                            padding: 8,
                            cornerRadius: 6,
                            callbacks: {{
                                label: function(context) {{
                                    return ` ${{context.label}}: ${{context.parsed}}%`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}

        function initCountryChart(code) {{
            const canvas = document.getElementById(`country-chart-${{code}}`);
            if (!canvas) return;
            if (countryChartInstances[code]) {{
                if (typeof countryChartInstances[code].destroy === 'function') {{
                    countryChartInstances[code].destroy();
                    delete countryChartInstances[code];
                }} else return;
            }}
            let countries = [];
            try {{
                countries = JSON.parse(canvas.getAttribute('data-countries')) || [];
            }} catch(e) {{ countries = []; }}
            if (!countries.length) return;

            const labels = countries.map(c => c.country);
            const dataValues = countries.map(c => c.ratio);
            
            const colorPalette = [
                '#1a73e8', '#34a853', '#ea4335', '#fbbc04', 
                '#9c27b0', '#00acc1', '#ff7043', '#5c6bc0',
                '#26a69a', '#8d6e63', '#78909c'
            ];

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            const sliceBorderColor = isDark ? '#2a2a2a' : '#f0f2f5';
            const textColor = isDark ? '#e0e0e0' : '#3c4043';

            const ctx = canvas.getContext('2d');
            countryChartInstances[code] = new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: labels,
                    datasets: [{{
                        data: dataValues,
                        backgroundColor: colorPalette.slice(0, labels.length),
                        borderColor: sliceBorderColor,
                        borderWidth: 1.5,
                        borderRadius: 4,
                        hoverOffset: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '58%',
                    animation: {{
                        animateRotate: true,
                        animateScale: true,
                        duration: 900,
                        easing: 'easeOutQuart'
                    }},
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'bottom',
                            labels: {{
                                font: {{ size: 9, weight: '500' }},
                                boxWidth: 7,
                                boxHeight: 7,
                                usePointStyle: true,
                                padding: 5,
                                color: textColor,
                                generateLabels: function(chart) {{
                                    const data = chart.data;
                                    if (data.labels.length && data.datasets.length) {{
                                        return data.labels.map((label, i) => {{
                                            const val = data.datasets[0].data[i];
                                            return {{
                                                text: `${{label}}: ${{val.toFixed(1)}}%`,
                                                fillStyle: data.datasets[0].backgroundColor[i],
                                                strokeStyle: 'transparent',
                                                pointStyle: 'circle',
                                                index: i
                                            }};
                                        }});
                                    }}
                                    return [];
                                }}
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(30, 30, 30, 0.85)',
                            padding: 8,
                            cornerRadius: 6,
                            callbacks: {{
                                label: function(context) {{
                                    return ` ${{context.label}}: ${{context.parsed}}%`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}

        function initChart(code) {{
            const canvas = document.getElementById(`chart-${{code}}`);
            if (!canvas) return;
            if (chartInstances[code]) {{
                if (typeof chartInstances[code].destroy === 'function') {{
                    chartInstances[code].destroy();
                    delete chartInstances[code];
                }}
            }}
            const data = fundNavData[code];
            if (!data || !data.dates || data.dates.length === 0) return;
            
            const container = document.getElementById(`chart-container-${{code}}`);
            let currentPeriod = 'month';
            if (container) {{
                const activeBtn = container.querySelector('.period-btn.active');
                if (activeBtn) currentPeriod = activeBtn.dataset.period;
            }}

            const filtered = filterNavData(data, currentPeriod);
            const baseNav = filtered.navs.length > 0 ? filtered.navs[0] : 1.0;
            const textColor = getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a';
            const borderColor = getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#e0e0e0';

            const ctx = canvas.getContext('2d');
            const chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: filtered.dates,
                    datasets: [{{
                        label: '净值',
                        data: filtered.navs,
                        borderColor: '#1a73e8',
                        backgroundColor: 'rgba(26,115,232,0.1)',
                        pointRadius: 1.5,
                        pointHoverRadius: 5,
                        pointHoverBackgroundColor: '#1a73e8',
                        fill: true,
                        tension: 0.1,
                        yAxisID: 'y'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false
                    }},
                    onHover: function(event, activeElements, chart) {{
                        const rect = chart.canvas.getBoundingClientRect();
                        const x = event.native ? event.native.offsetX : (event.x - rect.left);
                        const y = event.native ? event.native.offsetY : (event.y - rect.top);
                        if (x >= chart.chartArea.left && x <= chart.chartArea.right &&
                            y >= chart.chartArea.top && y <= chart.chartArea.bottom) {{
                            chart._crosshair = {{ x, y }};
                        }} else {{
                            chart._crosshair = null;
                        }}
                        if (!chart._rafPending) {{
                            chart._rafPending = true;
                            requestAnimationFrame(() => {{
                                chart._rafPending = false;
                                chart.draw();
                            }});
                        }}
                    }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            enabled: true,
                            mode: 'index',
                            intersect: false,
                            displayColors: false,
                            callbacks: {{
                                title: function(items) {{
                                    return items.length ? `时间: ${{items[0].label}}` : '';
                                }},
                                label: function(context) {{
                                    const nav = Number(context.parsed.y);
                                    let gainText = '--';
                                    if (baseNav && baseNav > 0) {{
                                        const gain = ((nav - baseNav) / baseNav) * 100.0;
                                        const sign = gain >= 0 ? '+' : '';
                                        gainText = `${{sign}}${{gain.toFixed(2)}}%`;
                                    }}
                                    return [`净值: ${{nav.toFixed(4)}}`, `涨幅: ${{gainText}}`];
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                maxTicksLimit: 8,
                                font: {{ size: 9 }},
                                color: textColor
                            }},
                            grid: {{ display: false }}
                        }},
                        y: {{
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {{
                                font: {{ size: 9 }},
                                color: textColor,
                                callback: function(val) {{ return val.toFixed(4); }}
                            }},
                            grid: {{ color: borderColor }}
                        }},
                        y1: {{
                            type: 'linear',
                            display: true,
                            position: 'right',
                            ticks: {{
                                font: {{ size: 9 }},
                                color: textColor,
                                callback: function(val) {{
                                    if (!baseNav || baseNav <= 0) return '0.00%';
                                    const pct = ((val - baseNav) / baseNav) * 100.0;
                                    return `${{pct >= 0 ? '+' : ''}}${{pct.toFixed(2)}}%`;
                                }}
                            }},
                            grid: {{ drawOnChartArea: false }}
                        }}
                    }}
                }}
            }});

            canvas.addEventListener('mouseleave', function() {{
                if (chart) {{
                    chart._crosshair = null;
                    chart.draw();
                }}
            }});

            chartInstances[code] = chart;

            function syncYAxes(chartObj) {{
                if (!chartObj) return;
                const yScale = chartObj.scales.y;
                const y1Scale = chartObj.scales.y1;
                if (yScale && y1Scale) {{
                    y1Scale.options.min = yScale.min;
                    y1Scale.options.max = yScale.max;
                }}
            }}
            syncYAxes(chart);

            if (container && !container._eventsBound) {{
                const btns = container.querySelectorAll('.period-btn');
                btns.forEach(btn => {{
                    btn.addEventListener('click', function(e) {{
                        e.stopPropagation();
                        btns.forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        const period = this.dataset.period;
                        const fData = filterNavData(data, period);
                        if (chartInstances[code]) {{
                            const curChart = chartInstances[code];
                            curChart.data.labels = fData.dates;
                            curChart.data.datasets[0].data = fData.navs;
                            const newBaseNav = fData.navs.length > 0 ? fData.navs[0] : 1.0;
                            curChart.options.plugins.tooltip.callbacks.label = function(context) {{
                                const nav = Number(context.parsed.y);
                                let gainText = '--';
                                if (newBaseNav && newBaseNav > 0) {{
                                    const gain = ((nav - newBaseNav) / newBaseNav) * 100.0;
                                    const sign = gain >= 0 ? '+' : '';
                                    gainText = `${{sign}}${{gain.toFixed(2)}}%`;
                                }}
                                return [`净值: ${{nav.toFixed(4)}}`, `涨幅: ${{gainText}}`];
                            }};
                            curChart.options.scales.y1.ticks.callback = function(val) {{
                                if (!newBaseNav || newBaseNav <= 0) return '0.00%';
                                const pct = ((val - newBaseNav) / newBaseNav) * 100.0;
                                return `${{pct >= 0 ? '+' : ''}}${{pct.toFixed(2)}}%`;
                            }};
                            curChart.update();
                            syncYAxes(curChart);
                        }}
                    }});
                }});
                container._eventsBound = true;
            }}
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            const table = document.getElementById('fundTable');
            table.addEventListener('click', function(e) {{
                const dcaBtn = e.target.closest('.dca-btn');
                if (dcaBtn) {{
                    e.stopPropagation();
                    const code = dcaBtn.dataset.code;
                    window.openDcaModal(code);
                    return;
                }}

                const target = e.target.closest('tr.fund-row');
                if (!target || e.target.tagName === 'A' || e.target.closest('.star-btn')) return;
                const code = target.dataset.code;
                const hRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                
                if (hRow) {{
                    hRow.classList.toggle('show');
                    if (hRow.classList.contains('show')) {{
                        hRow.style.display = '';
                        window.requestAnimationFrame(() => {{
                            setTimeout(() => {{ initCountryChart(code); }}, 50);
                            setTimeout(() => {{ initHolderChart(code); }}, 150);
                            setTimeout(() => {{ initChart(code); }}, 250);
                        }});
                    }} else {{
                        hRow.style.display = 'none';
                    }}
                }}
            }});
        }});

        let currentSortCol = -1;
        let isAscending = true;

        function handleHeaderClick(colIndex) {{
            if (window._isResizingColumn) return;
            sortTable(colIndex);
        }}

        function sortTable(colIndex) {{
            document.querySelectorAll('.holding-row').forEach(row => {{
                row.classList.remove('show');
                row.style.display = 'none';
            }});
            const table = document.getElementById("fundTable");
            const tbody = table.querySelector("tbody");
            const allRows = Array.from(tbody.querySelectorAll("tr"));
            const dataRows = allRows.filter(row => row.id !== 'empty-row' && !row.classList.contains('holding-row'));
            const holdingMap = {{}};
            allRows.filter(row => row.classList.contains('holding-row')).forEach(row => {{
                holdingMap[row.getAttribute('data-code')] = row;
            }});

            isAscending = (currentSortCol === colIndex) ? !isAscending : true;
            currentSortCol = colIndex;

            dataRows.sort((a, b) => {{
                let valA = a.children[colIndex].getAttribute('data-val');
                let valB = b.children[colIndex].getAttribute('data-val');
                const numA = parseFloat(valA), numB = parseFloat(valB);
                if (!isNaN(numA) && !isNaN(numB)) return isAscending ? numA - numB : numB - numA;
                return isAscending ? valA.localeCompare(valB, 'zh-Hans-CN') : valB.localeCompare(valA, 'zh-Hans-CN');
            }});

            const fragment = document.createDocumentFragment();
            dataRows.forEach(row => {{
                fragment.appendChild(row);
                const code = row.getAttribute('data-code');
                if (holdingMap[code]) fragment.appendChild(holdingMap[code]);
            }});
            const empty = document.getElementById('empty-row');
            if (empty) fragment.appendChild(empty);
            
            tbody.innerHTML = '';
            tbody.appendChild(fragment);
            
            const headers = table.querySelectorAll("th");
            headers.forEach((th, idx) => {{
                const icon = th.querySelector(".sort-icon");
                if (icon) {{
                    if (idx === colIndex) {{
                        icon.textContent = isAscending ? "▲" : "▼";
                        th.style.color = "#1a73e8";
                    }} else {{
                        icon.textContent = "⇅";
                        th.style.color = "";
                    }}
                }}
            }});
        }}

        document.addEventListener("DOMContentLoaded", function () {{
            const table = document.getElementById("fundTable");
            const headers = table.querySelectorAll("thead th");
            window._isResizingColumn = false;

            headers.forEach((th) => {{
                const resizer = document.createElement("div");
                resizer.classList.add("resizer");
                th.appendChild(resizer);

                let startX = 0;
                let startW = 0;

                resizer.addEventListener("mousedown", function (e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    window._isResizingColumn = true;
                    startX = e.clientX;
                    startW = th.getBoundingClientRect().width;
                    th.classList.add("resizing");

                    function onMouseMove(e) {{
                        const diff = e.clientX - startX;
                        const newWidth = Math.max(35, startW + diff);
                        th.style.width = newWidth + "px";
                    }}

                    function onMouseUp() {{
                        th.classList.remove("resizing");
                        document.removeEventListener("mousemove", onMouseMove);
                        document.removeEventListener("mouseup", onMouseUp);
                        setTimeout(() => {{
                            window._isResizingColumn = false;
                        }}, 60);
                    }}

                    document.addEventListener("mousemove", onMouseMove);
                    document.addEventListener("mouseup", onMouseUp);
                }});
            }});
        }});

        // ===== 移动端「市场大类」折叠控制 =====
        (function() {{
            function setupMobileFilterToggle() {{
                const toggle = document.getElementById('mobileFilterToggle');
                const subBar = document.getElementById('subFilterBar');
                const currentLabel = document.getElementById('mobileFilterCurrent');
                if (!toggle || !subBar) return;

                const isMobile = () => window.innerWidth <= 992;

                function expand() {{
                    // 互斥：先关闭定投参数面板
                    const dcaCardEl = document.getElementById('gDcaCard');
                    const dcaBtnEl = document.getElementById('dcaToggleBtn');
                    const dcaArrowEl = document.getElementById('dcaToggleArrow');
                    if (dcaCardEl) dcaCardEl.classList.remove('mobile-expanded');
                    if (dcaBtnEl) dcaBtnEl.classList.remove('active');
                    if (dcaArrowEl) dcaArrowEl.textContent = '▼';

                    subBar.classList.add('mobile-expanded');
                    toggle.classList.add('expanded');
                }}
                function collapse() {{
                    subBar.classList.remove('mobile-expanded');
                    toggle.classList.remove('expanded');
                }}
                function updateCurrentLabel() {{
                    const activeBtn = subBar.querySelector('.cat-btn.macro-filter.active');
                    if (activeBtn && currentLabel) {{
                        // 去掉前导 emoji/符号，只保留文字
                        const txt = activeBtn.textContent.replace(/^[^\\w\\u4e00-\\u9fa5]+/, '').trim();
                        currentLabel.textContent = txt || activeBtn.textContent.trim();
                    }}
                }}

                // 点击开关按钮：展开 / 收起
                toggle.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    if (subBar.classList.contains('mobile-expanded')) collapse();
                    else expand();
                }});

                // 点击任意大类按钮：更新标签 + 自动收起（排除视图模式按钮）
                subBar.querySelectorAll('.cat-btn:not(.view-mode-btn)').forEach(btn => {{
                    btn.addEventListener('click', function() {{
                        updateCurrentLabel();
                        if (isMobile()) {{
                            setTimeout(collapse, 160);
                        }}
                    }});
                }});

                // 点击面板外部自动收起
                document.addEventListener('click', function(e) {{
                    if (!isMobile()) return;
                    if (!subBar.classList.contains('mobile-expanded')) return;
                    if (toggle.contains(e.target) || subBar.contains(e.target)) return;
                    collapse();
                }});

                // 窗口尺寸变化到桌面端时清除展开状态
                window.addEventListener('resize', function() {{
                    if (!isMobile()) collapse();
                }});

                updateCurrentLabel();
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', setupMobileFilterToggle);
            }} else {{
                setupMobileFilterToggle();
            }}
        }})();

        // ===== 移动端「动态定投参数」折叠控制 =====
        (function() {{
            function setupDcaMobileToggle() {{
                const btn = document.getElementById('dcaToggleBtn');
                const dcaCard = document.getElementById('gDcaCard');
                const arrow = document.getElementById('dcaToggleArrow');
                if (!btn || !dcaCard) return;

                const isMobile = () => window.innerWidth <= 992;

                function expand() {{
                    // 互斥：先关闭市场大类面板
                    const subBarEl = document.getElementById('subFilterBar');
                    const filterToggleEl = document.getElementById('mobileFilterToggle');
                    if (subBarEl) subBarEl.classList.remove('mobile-expanded');
                    if (filterToggleEl) filterToggleEl.classList.remove('expanded');

                    dcaCard.classList.add('mobile-expanded');
                    btn.classList.add('active');
                    if (arrow) arrow.textContent = '▲';
                }}
                function collapse() {{
                    dcaCard.classList.remove('mobile-expanded');
                    btn.classList.remove('active');
                    if (arrow) arrow.textContent = '▼';
                }}

                btn.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    if (!isMobile()) return;   // 桌面端不响应
                    if (dcaCard.classList.contains('mobile-expanded')) collapse();
                    else expand();
                }});

                // 点击卡片/按钮外部时自动收起
                document.addEventListener('click', function(e) {{
                    if (!isMobile()) return;
                    if (!dcaCard.classList.contains('mobile-expanded')) return;
                    if (btn.contains(e.target) || dcaCard.contains(e.target)) return;
                    collapse();
                }});

                // 切换到桌面端尺寸时清除展开态
                window.addEventListener('resize', function() {{
                    if (!isMobile()) collapse();
                }});
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', setupDcaMobileToggle);
            }} else {{
                setupDcaMobileToggle();
            }}
        }})();

        // ===== 基金看板：默认 / 简洁 视图模式切换 =====
        (function() {{
            function initViewModeSwitch() {{
                const fundView = document.getElementById('fundView');
                const modeBtns = document.querySelectorAll('.view-mode-btn');
                if (!fundView || !modeBtns.length) return;

                // 展开行的 colspan 随模式动态调整（22 ↔ 8）
                function applyColspan(mode) {{
                    const span = (mode === 'simple') ? '11' : '22';
                    document.querySelectorAll('#fundTable td[colspan]').forEach(td => {{
                        td.setAttribute('colspan', span);
                    }});
                }}

                function setViewMode(mode) {{
                    if (mode === 'simple') {{
                        fundView.classList.add('simple-mode');
                    }} else {{
                        fundView.classList.remove('simple-mode');
                    }}

                    modeBtns.forEach(b => {{
                        b.classList.toggle('active', b.dataset.viewMode === mode);
                    }});

                    applyColspan(mode);
                    localStorage.setItem('fundViewMode', mode);

                    // 关键：关闭所有已展开行，避免旧图表宽度错乱
                    document.querySelectorAll('#fundTable .holding-row').forEach(row => {{
                        row.classList.remove('show');
                        row.style.display = 'none';
                    }});
                }}

                // 初始化：从 localStorage 恢复用户偏好
                const saved = localStorage.getItem('fundViewMode') || 'default';
                setViewMode(saved);

                modeBtns.forEach(btn => {{
                    btn.addEventListener('click', function(e) {{
                        e.stopPropagation();
                        setViewMode(this.dataset.viewMode);
                    }});
                }});
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initViewModeSwitch);
            }} else {{
                initViewModeSwitch();
            }}
        }})();

    </script>
</body>
</html>
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    return os.path.abspath(filename)

def fetch_crypto_data(symbol, start_date, end_date):
    cache_file = os.path.join(NAV_CACHE_DIR, f"{symbol}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('start_date', '') <= start_date and cache.get('end_date', '') >= end_date:
                return cache.get('data', [])
        except Exception: pass

    pair = f"{symbol}USDT"
    data = []
    try:
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={pair}&interval=1d&startTime={start_ts}&endTime={end_ts}&limit=1000"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            klines = json.loads(resp.read().decode('utf-8'))
            for item in klines:
                d_str = datetime.fromtimestamp(item[0] / 1000).strftime('%Y-%m-%d')
                nav = float(item[4])
                if nav > 0: data.append({"date": d_str, "nav": nav})
    except Exception: pass

    if data:
        data = sorted(data, key=lambda x: x['date'])
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'start_date': start_date, 'end_date': end_date, 'data': data}, f, ensure_ascii=False, indent=2)
        except Exception: pass
        return data
    return None

def fetch_precious_metals_data(symbol, start_date, end_date):
    cache_file = os.path.join(NAV_CACHE_DIR, f"{symbol}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('start_date', '') <= start_date and cache.get('end_date', '') >= end_date:
                return cache.get('data', [])
        except Exception: pass

    df = None
    data = []
    try:
        if symbol == "AUM": df = ak.futures_main_sina(symbol="AU0")
        elif symbol == "XAU":
            for sym in ["GC", "XAU"]:
                try:
                    df = ak.futures_foreign_hist(symbol=sym)
                    if df is not None and not df.empty: break
                except Exception: continue
        elif symbol == "XAG":
            for sym in ["SI", "XAG"]:
                try:
                    df = ak.futures_foreign_hist(symbol=sym)
                    if df is not None and not df.empty: break
                except Exception: continue

        if df is not None and not df.empty:
            d_col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            c_col = '收盘价' if '收盘价' in df.columns else ('close' if 'close' in df.columns else df.columns[4])
            df[d_col] = pd.to_datetime(df[d_col]).dt.strftime('%Y-%m-%d')
            df = df[(df[d_col] >= start_date) & (df[d_col] <= end_date)].sort_values(d_col)
            for _, row in df.iterrows():
                try:
                    nav = float(row[c_col])
                    if nav > 0: data.append({"date": str(row[d_col]), "nav": nav})
                except Exception: continue

        if data:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'start_date': start_date, 'end_date': end_date, 'data': data}, f, ensure_ascii=False, indent=2)
            return data
    except Exception: pass
    return None

# ==============================================================================
# 【新增】大宗商品（布伦特原油 / LME铜）与货币汇率（USD/CNY、USD/JPY、DXY）抓取
# ==============================================================================
def fetch_yahoo_history(symbol, start_date, end_date):
    """从 Yahoo Finance 抓取日线历史收盘价（通用函数，供指数/大宗商品/货币使用）。

    修复点：
    1. 先访问 finance.yahoo.com 获取 consent cookie，避免长历史请求被返回空数组。
    2. query1 / query2 双端点回退。
    3. 正确处理 result=None 或 error 字段，不再静默吞掉异常。
    4. 打印诊断日志，便于排查符号错误。
    """
    data = []
    try:
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + 86400
    except Exception as e:
        print(f"    [Yahoo] {symbol} 日期解析失败: {e}")
        return None

    encoded_symbol = urllib.parse.quote(symbol, safe='')

    # 带 cookie 的 opener
    cj = CookieJar()
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(
        proxy_handler, urllib.request.HTTPCookieProcessor(cj)
    )

    # 预热：获取 consent / session cookie（关键修复）
    try:
        warm_req = urllib.request.Request(
            "https://finance.yahoo.com/",
            headers={"User-Agent": DEFAULT_HEADERS["User-Agent"]}
        )
        opener.open(warm_req, timeout=8)
    except Exception:
        pass

    hosts = [
        "query1.finance.yahoo.com",
        "query2.finance.yahoo.com",
    ]

    from datetime import timezone as _tz

    for host in hosts:
        try:
            url = (
                f"https://{host}/v8/finance/chart/{encoded_symbol}"
                f"?period1={start_ts}&period2={end_ts}&interval=1d&events=div%2Csplit"
            )
            req = urllib.request.Request(url, headers={
                **DEFAULT_HEADERS,
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://finance.yahoo.com/",
            })
            with opener.open(req, timeout=15) as resp:
                raw_text = resp.read().decode('utf-8', errors='ignore')
            res = json.loads(raw_text)

            chart = res.get("chart") or {}
            err = chart.get("error")
            if err:
                desc = err.get("description") if isinstance(err, dict) else str(err)
                print(f"    [Yahoo] {symbol}@{host} 接口错误: {desc}")
                continue

            results = chart.get("result")
            if not results:
                continue

            result = results[0] or {}
            timestamps = result.get("timestamp") or []
            indicators = result.get("indicators") or {}
            quote_list = indicators.get("quote") or []
            if not quote_list:
                continue
            closes = quote_list[0].get("close") or []

            for ts, c in zip(timestamps, closes):
                if c is None:
                    continue
                try:
                    v = float(c)
                except (TypeError, ValueError):
                    continue
                if v <= 0:
                    continue
                d = datetime.fromtimestamp(ts, tz=_tz.utc).strftime('%Y-%m-%d')
                data.append({"date": d, "nav": round(v, 4)})

            if data:
                break
        except Exception as e:
            print(f"    [Yahoo] {symbol}@{host} 请求异常: {e}")
            continue

    if data:
        return sorted(data, key=lambda x: x['date'])

    print(f"    [Yahoo] {symbol} 未获取到任何数据")
    return None


def fetch_commodity_data(symbol, start_date, end_date):
    """抓取大宗商品历史行情（BRENT / CAD），带本地缓存。优先 AkShare 外盘期货，兜底 Yahoo Finance。"""
    cache_file = os.path.join(NAV_CACHE_DIR, f"{symbol}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('start_date', '') <= start_date and cache.get('end_date', '') >= end_date:
                return cache.get('data', [])
        except Exception: pass

    df = None
    data = []
    try:
        candidate_syms = []
        if symbol == "BRENT":
            candidate_syms = ["OIL", "BRENT"]
        elif symbol == "CAD":
            candidate_syms = ["CAD", "HG"]
        for sym in candidate_syms:
            try:
                df = ak.futures_foreign_hist(symbol=sym)
                if df is not None and not df.empty: break
            except Exception:
                continue

        if df is not None and not df.empty:
            d_col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            c_col = '收盘价' if '收盘价' in df.columns else ('close' if 'close' in df.columns else df.columns[4])
            df = df.copy()
            df[d_col] = pd.to_datetime(df[d_col], errors='coerce').dt.strftime('%Y-%m-%d')
            df = df.dropna(subset=[d_col])
            df = df[(df[d_col] >= start_date) & (df[d_col] <= end_date)].sort_values(d_col)
            for _, row in df.iterrows():
                try:
                    nav = float(row[c_col])
                    if nav > 0: data.append({"date": str(row[d_col]), "nav": round(nav, 4)})
                except Exception:
                    continue
    except Exception:
        pass

    if not data:
        yahoo_sym = "BZ=F" if symbol == "BRENT" else "HG=F"
        ydata = fetch_yahoo_history(yahoo_sym, start_date, end_date)
        if ydata:
            data = ydata

    if data:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'start_date': start_date, 'end_date': end_date, 'data': data}, f, ensure_ascii=False, indent=2)
        except Exception: pass
        return data
    return None


def fetch_currency_data(symbol, start_date, end_date):
    """抓取货币汇率历史数据（USDCNY / USDJPY / DXY），带本地缓存。"""
    cache_file = os.path.join(NAV_CACHE_DIR, f"{symbol}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('start_date', '') <= start_date and cache.get('end_date', '') >= end_date:
                return cache.get('data', [])
        except Exception: pass

    investing_urls = {
        "USDCNY": "https://cn.investing.com/currencies/usd-cny",
        "USDJPY": "https://cn.investing.com/currencies/usd-jpy",
        "DXY":    "https://cn.investing.com/indices/usdollar",
    }
    data = None
    url = investing_urls.get(symbol)
    if url:
        try:
            req = urllib.request.Request(url, headers={
                **DEFAULT_HEADERS,
                "Referer": "https://cn.investing.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html_text = resp.read().decode('utf-8', errors='ignore')
            candidates = []
            for m in re.finditer(r'"(?:date|Date)"\s*:\s*"([^"]+)"[^}]*?"(?:close|Close|last|last_close|price)"\s*:\s*([\d.]+)', html_text):
                d_str = m.group(1).strip()
                v_str = m.group(2).strip()
                try:
                    v = float(v_str)
                except ValueError:
                    continue
                if v <= 0:
                    continue
                d_norm = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        d_norm = datetime.strptime(d_str, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                if d_norm:
                    candidates.append({"date": d_norm, "nav": round(v, 4)})
            if candidates:
                uniq = {}
                for it in candidates:
                    uniq[it["date"]] = it
                data = sorted(uniq.values(), key=lambda x: x['date'])
        except Exception:
            data = None

    if not data:
        symbol_map = {
            "USDCNY": "USDCNY=X",
            "USDJPY": "USDJPY=X",
            "DXY": "DX-Y.NYB"
        }
        yahoo_symbol = symbol_map.get(symbol)
        if yahoo_symbol:
            data = fetch_yahoo_history(yahoo_symbol, start_date, end_date)

    if data:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'start_date': start_date, 'end_date': end_date, 'data': data}, f, ensure_ascii=False, indent=2)
        except Exception: pass
        return data
    return None


def _process_hist_df(df, start_date, end_date):
    """通用：从含日期/收盘列的 DataFrame 中提取 [{'date','nav'}, ...]"""
    if df is None or df.empty:
        return None
    try:
        date_col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
        close_col = '收盘' if '收盘' in df.columns else ('close' if 'close' in df.columns else df.columns[4])

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df['date_str'] = df[date_col].dt.strftime('%Y-%m-%d')
        mask = (df['date_str'] >= start_date) & (df['date_str'] <= end_date)
        df = df.loc[mask].sort_values('date_str')

        data = []
        for _, row in df.iterrows():
            try:
                nav = float(row[close_col])
                if nav > 0:
                    data.append({"date": row['date_str'], "nav": nav})
            except Exception:
                continue
        return data if data else None
    except Exception:
        return None


def fetch_index_data(symbol, start_date, end_date):
    """抓取主流指数/ETF 历史行情，带本地缓存。

    数据源优先级（与 get_meiguzhishu.py 保持一致）：
      1) 新浪美股接口 US_MinKService.getDailyK（主数据源，已实测稳定）
      2) Yahoo Finance 兜底（防止新浪偶发限流）

    缓存策略：
      - 缓存文件：cache/nav/{symbol}.json
      - 已覆盖请求区间时直接返回缓存，不再发起网络请求
    """
    cache_file = os.path.join(NAV_CACHE_DIR, f"{symbol}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('start_date', '') <= start_date and cache.get('end_date', '') >= end_date:
                return cache.get('data', [])
        except Exception:
            pass

    data = None

    # ---- 数据源 1：新浪美股接口 ----
    sina_code = SINA_US_INDEX_MAP.get(symbol)
    if sina_code:
        try:
            raw = fetch_sina_us_kline(sina_code, start_date)
            if raw:
                data = [r for r in raw if r["date"] <= end_date]
                if not data:
                    data = None
        except Exception:
            data = None

    # ---- 数据源 2：Yahoo Finance 兜底 ----
    if not data:
        yahoo_syms = {
            "NDX":  "^NDX",
            "SPX":  "^GSPC",
            "SOX":  "^SOX",
            "SOXL": "SOXL",
            "XLK":  "XLK",
        }
        ysym = yahoo_syms.get(symbol)
        if ysym:
            try:
                data = fetch_yahoo_history(ysym, start_date, end_date)
            except Exception:
                data = None

    if data:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {'start_date': start_date, 'end_date': end_date, 'data': data},
                    f, ensure_ascii=False, indent=2
                )
        except Exception:
            pass
        return data
    return None

def _test_macro_metrics():
    import time
    o = get_direct_opener()
    t0 = time.time()
    m = fetch_home_market_metrics(o)
    print(f"\n===== 总耗时: {time.time() - t0:.2f}s =====\n")
    for k, v in m.items():
        val = v.get("val", v.get("score"))
        src = v.get("source", "")
        print(f"{k:15s} {str(val):>12s}  [{src}]")

def main():
    today_str = now_beijing().strftime("%Y-%m-%d")
    default_start = "2025-01-01"
    cutoff_date = "2026-04-01"

    parser = argparse.ArgumentParser(description="场外基金量化与资产配置看板生成引擎")
    parser.add_argument("--mode", type=str, choices=["debug", "prod"], default=None,
                        help="运行模式配置：debug(快速测试少量标的) / prod(生产发布全量标的)")
    parser.add_argument("--start", type=str, default=default_start)
    parser.add_argument("--end", type=str, default=today_str)
    parser.add_argument("--out", type=str, default="fund_drawdown_dashboard.html")

    args = parser.parse_args()

    if args.mode: is_debug = (args.mode == "debug")
    else: is_debug = IS_DEBUG

    if is_debug:
        target_funds = TEST_FUNDS
        target_commodities = ["XAU", "BRENT"]
        target_cryptos = ["BTC"]
        target_indices = ["NDX"]
        print("\n=======================================================")
        print("🛠️ 当前处于【测试调试阶段 (DEBUG MODE)】")
        print(f"👉 仅抓取 {len(target_funds)} 只核心测试基金 + 极简大类资产样本")
        print("=======================================================\n")
    else:
        target_funds = PROD_FUNDS
        target_commodities = ["XAU", "AUM", "XAG", "BRENT", "CAD"]
        target_cryptos = ["BTC", "ETH", "SOL", "BNB"]
        target_indices = ["NDX", "SPX", "SOX", "SOXL", "XLK"]
        print("\n=======================================================")
        print("🚀 当前处于【正式发布阶段 (PROD MODE)】")
        print(f"👉 正在抓取全量 {len(target_funds)} 只基金与全品类宏观大类资产...")
        print("=======================================================\n")

    print(f"统计区间: {args.start} 至 {args.end}")
    print("⏳ 正在并行抓取：核心宏观指标 / 指数估值 / 指数年度数据 / 美联储利率观测器...")

    # 每个并行任务用自己独立的 opener（RequestsOpener.session 非线程安全）
    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_metrics    = ex.submit(lambda: fetch_home_market_metrics(get_direct_opener()))
        fut_valuations = ex.submit(lambda: fetch_index_valuations(get_direct_opener()))
        fut_annual     = ex.submit(fetch_index_annual_data)
        fut_fed        = ex.submit(lambda: fetch_fed_rate_monitor(get_direct_opener()))

        # 各自的默认值，用于优雅降级
        DEFAULT_METRICS = {
            "fng": {"score": 0.0, "rating": "暂无数据", "time": "", "source": "获取失败", "url": "#"},
            "vix": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "usdcny": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "vxn": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "skew": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "brent": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "gold_london": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "gold_shfe": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "silver_london": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "copper_lme": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
            "btc": {"val": 0.0, "status": "数据暂缺", "time": "", "source": "获取失败", "url": "#", "desc": ""},
        }

        try:
            home_metrics = fut_metrics.result(timeout=120)
        except Exception as e:
            print(f"⚠️ 宏观指标抓取失败: {e}")
            home_metrics = DEFAULT_METRICS

        try:
            index_valuations = fut_valuations.result(timeout=60)
        except Exception as e:
            print(f"⚠️ 指数估值抓取失败: {e}")
            index_valuations = [
                {"name": n, "ticker": "", "pe": "--", "pct": "--", "pct_raw": 0,
                 "status": "⚪ 暂无数据", "color": "#70757a"}
                for n in TARGET_INDICES
            ]

        try:
            index_annual_data = fut_annual.result(timeout=120)
        except Exception as e:
            print(f"⚠️ 指数年度数据抓取失败: {e}")
            index_annual_data = {}

        try:
            fed_monitor = fut_fed.result(timeout=60)
        except Exception as e:
            print(f"⚠️ 美联储利率观测器抓取失败: {e}")
            fed_monitor = {
                "source_url": "https://www.cmegroup.com/cn-s/markets/interest-rates/cme-fedwatch-tool.html",
                "meeting_text": "--", "meeting_iso": "", "countdown_text": "暂无倒计时",
                "futures_price": "--", "probabilities": [], "table_rows": [],
                "update_text": "--", "source_name": "CME FedWatch",
            }
    print(f"📊 核心宏观指标获取成功: 恐慌贪婪 {home_metrics['fng']['score']} | VIX {home_metrics['vix']['val']} | USD/CNY {home_metrics['usdcny']['val']} | VXN {home_metrics['vxn']['val']} | SKEW {home_metrics['skew']['val']}")
    print(f"🛢️ 大宗商品指标获取成功: 布伦特原油 {home_metrics['brent']['val']} | 伦敦金 {home_metrics['gold_london']['val']} | 沪金主连 {home_metrics['gold_shfe']['val']} | 伦敦银 {home_metrics['silver_london']['val']} | LME铜 {home_metrics['copper_lme']['val']} | BTC {home_metrics.get('btc', {}).get('val', 0.0)}")
    fed_prob_count = len(fed_monitor.get('probabilities', []))
    fed_status = "✅" if fed_monitor.get('meeting_text') != "--" and fed_prob_count > 0 else "⚠️"
    print(f"🏛️ 美联储利率观测器 {fed_status}: 下一次会议 {fed_monitor.get('meeting_text', '--')} | 期货价格 {fed_monitor.get('futures_price', '--')} | 当前概率 {fed_prob_count} 档 | 更新时间 {fed_monitor.get('update_text', '--')}")

    results = []

    def process_single_fund(code):
        t_opener = get_thread_opener()
        meta = fetch_fund_detail_meta(t_opener, code)
        raw_data = fetch_from_eastmoney(t_opener, code, args.start, args.end)
        if not raw_data:
            return code, meta["name"], None
        raw_data_sorted = sorted(raw_data, key=lambda x: x['date'])
        is_qdii = code in US_ACTIVE_CODES or code in NDX_PASSIVE_CODES or code in SPX_PASSIVE_CODES
        res = analyze_fund_metrics(raw_data_sorted, args.end, cutoff_date, is_qdii=is_qdii)
        if res:
            res.update({
                "code": code,
                "name": meta["name"],
                "scale": meta["scale"],
                "scale_val": meta["scale_val"],
                "fee_manage": meta["fee_manage"],
                "fee_custody": meta["fee_custody"],
                "fee_sales": meta["fee_sales"],
                "fee_source": meta["fee_source"],
                "fee_total": meta["fee_total"],
                "fee_val": meta["fee_val"],
                "fee_purchase": meta["fee_purchase"],
                "fee_redemption": meta["fee_redemption"],
                "buy_status": meta.get("buy_status", "--"),
                "buy_limit": meta.get("buy_limit", "无限额"),
                "buy_limit_val": meta.get("buy_limit_val", -1),
                "holdings": meta.get("holdings", []),
                "holder_struct": meta.get("holder_struct", None),
                "countries_info": meta.get("countries_info", {"date": "--", "countries": []}),
                "source": "天天基金",
                "nav_data": raw_data_sorted
            })
            results.append(res)
            return code, meta["name"], res
        return code, meta["name"], None

    max_workers = 12 if is_debug else 25            # ★ 原 3 / 10
    print(f"⚙️ 启用多线程并发抓取 (并发数: {max_workers}) ...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_fund, code) for code in target_funds]
        deadline = time.time() + (600 if is_debug else 3000)   # 全局预算：50 分钟
        for done_count, fut in enumerate(as_completed(futures), start=1):
            if time.time() > deadline:
                print("⏰ 达到总时间预算，跳过剩余基金任务（缓存已写入，下次可复用）")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            try:
                code, name, res = fut.result(timeout=180)     # 单只基金 3 分钟硬上限
            except Exception as exc:
                print(f"[{done_count}/{len(target_funds)}] 处理异常: {exc}")
                continue
            if res:
                c_date = res["countries_info"].get("date", "--")
                print(f"[{done_count}/{len(target_funds)}] {code} - {name} ... ✅ 完成 (国家披露期: {c_date})")
            else:
                print(f"[{done_count}/{len(target_funds)}] {code} - {name} ... ❌ 历史净值抓取失败")

    def _process_commodity(symbol):
        try:
            if symbol in ["XAU", "AUM", "XAG"]:
                data = fetch_precious_metals_data(symbol, args.start, args.end)
            else:
                data = fetch_commodity_data(symbol, args.start, args.end)
            if not data:
                return None, None
            meta_name = COMMODITY_NAMES.get(symbol, symbol)
            res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
            if not res:
                return None, None
            res.update({
                "code": symbol, "name": meta_name, "scale": "--", "scale_val": -1.0,
                "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                "holder_struct": None, "countries_info": {"date": "--", "countries": []},
                "source": "大宗商品行情", "nav_data": data
            })
            return res, f"大宗商品 {symbol} ({meta_name})"
        except Exception as e:
            print(f"  ✗ 大宗商品 {symbol} 异常: {e}")
            return None, None

    def _process_crypto(symbol):
        try:
            data = fetch_crypto_data(symbol, args.start, args.end)
            if not data:
                return None, None
            meta_name = CRYPTO_NAMES.get(symbol, symbol)
            res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
            if not res:
                return None, None
            res.update({
                "code": symbol, "name": meta_name, "scale": "--", "scale_val": -1.0,
                "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                "holder_struct": None, "countries_info": {"date": "--", "countries": []},
                "source": "现货行情", "nav_data": data
            })
            return res, f"加密货币 {symbol} ({meta_name})"
        except Exception as e:
            print(f"  ✗ 加密货币 {symbol} 异常: {e}")
            return None, None

    def _process_index(symbol):
        try:
            data = fetch_index_data(symbol, args.start, args.end)
            if not data:
                return None, None
            res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
            if not res:
                return None, None
            res.update({
                "code": symbol, "name": INDEX_NAMES.get(symbol, symbol),
                "scale": "--", "scale_val": -1.0,
                "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                "holder_struct": None, "countries_info": {"date": "--", "countries": []},
                "source": "指数行情", "nav_data": data
            })
            return res, f"主流指数 {symbol}"
        except Exception:
            return None, None

    # 一次性并行执行三类资产
    mixed_tasks = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        for sym in target_commodities:
            mixed_tasks.append(executor.submit(_process_commodity, sym))
        for sym in target_cryptos:
            mixed_tasks.append(executor.submit(_process_crypto, sym))
        for sym in target_indices:
            mixed_tasks.append(executor.submit(_process_index, sym))

        for fut in as_completed(mixed_tasks):
            try:
                res, label = fut.result(timeout=180)
            except Exception as e:
                print(f"  ✗ 大类资产并行任务异常: {e}")
                continue
            if res:
                results.append(res)
                print(f"  ✓ {label} 抓取成功, 数据量 {len(res.get('nav_data', []))}")
    # =====================================================================

    if results:
        abs_path = generate_html_report(
            results, args.start, args.end, today_str,
            home_metrics, index_valuations,
            fed_monitor=fed_monitor,
            is_debug_mode=is_debug,
            filename=args.out,
            index_annual_data=index_annual_data
        )
        print(f"\n🎉 升级版网页构建成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception: pass

if __name__ == "__main__":
    main()