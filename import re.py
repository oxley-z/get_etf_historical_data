import os
import re
import json
import time
import random
import argparse
import webbrowser
import urllib.request
import urllib.parse
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from calendar import monthrange

# 强制清空代理环境变量
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

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
    "017091", "016057", "160213", "019172", "019441", "018043", "019547", "016532",
    "040046", "161130", "016452", "270042", "019736", "000834", "019524", "015299",
    "539001", "018966",
    # 标普被动组
    "161125", "007721", "017028", "050025", "018064", "096001", "017641", "018738",
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
    "017091", "016057", "160213", "019172", "019441", "018043", "019547", "016532",
    "040046", "161130", "016452", "270042", "019736", "000834", "019524", "015299",
    "539001", "018966"
}

SPX_PASSIVE_CODES = {
    "161125", "007721", "017028", "050025", "018064", "096001", "017641", "018738"
}

# 分级 C 份额到主代码/A 份额映射
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
}

INDEX_NAMES = {
    "NDX": "纳斯达克100指数",
    "SPX": "标普500指数",
    "SOXX": "iShares 半导体ETF",
    "SOXL": "三倍做多半导体ETF-Direxion"
}

PRECIOUS_METALS_NAMES = {
    "XAU": "伦敦金 (XAU)",
    "AUM": "黄金连续 (AUM)",
    "XAG": "伦敦银 (XAG)"
}

CRYPTO_NAMES = {
    "BTC": "比特币 (BTC/USDT)",
    "ETH": "以太坊 (ETH/USDT)",
    "SOL": "索拉纳 (SOL/USDT)",
    "BNB": "币安币 (BNB/USDT)"
}

SINA_INDEX_MAP = {
    "NDX": ".NDX",
    "SPX": ".INX",
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

def get_direct_opener():
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

# ==============================================================================
# 多源宏观指标获取模块
# ==============================================================================
def fetch_from_yahoo_finance(opener, symbol: str, timeout: int = 5) -> float:
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
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            **DEFAULT_HEADERS,
            "Referer": "https://www.cnn.com/markets/fear-and-greed"
        })
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            score = data.get("fear_and_greed", {}).get("score")
            raw_cls = str(data.get("fear_and_greed", {}).get("rating", "neutral")).lower()
            cls_map = {
                "extreme fear": "极度恐惧", "fear": "恐惧",
                "neutral": "中性观望", "greed": "贪婪", "extreme greed": "极度贪婪"
            }
            if score is not None:
                return round(float(score), 1), cls_map.get(raw_cls, raw_cls.capitalize()), "CNN 官方接口", "https://edition.cnn.com/markets/fear-and-greed"
    except Exception: pass

    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", [])
            if items and items[0].get("value") is not None:
                score = round(float(items[0]["value"]), 1)
                rating = items[0].get("value_classification", "Neutral")
                return score, rating, "Alternative 情绪源", "https://alternative.me/crypto/fear-and-greed-index/"
    except Exception: pass
    return 0.0, "暂无数据", "获取失败", "https://edition.cnn.com/markets/fear-and-greed"

def get_usd_cny(opener) -> tuple[float, str, str]:
    try:
        url = "https://hq.sinajs.cn/list=fx_susdcny"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
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
        with opener.open(req, timeout=5) as resp:
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

def fetch_home_market_metrics(opener):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fng_score, fng_rating, fng_src, fng_url = get_cnn_fear_greed(opener)
    vix_val, vix_src, vix_url = get_vix(opener)
    vix_status = "数据暂缺" if vix_val <= 0 else ("极度恐慌" if vix_val >= 30 else ("警惕波动" if vix_val >= 20 else ("温和震荡" if vix_val >= 15 else "平稳低波")))

    usdcny_val, usdcny_src, usdcny_url = get_usd_cny(opener)
    usdcny_status = "数据暂缺" if usdcny_val <= 0 else ("美元走强" if usdcny_val >= 7.30 else ("区间震荡" if usdcny_val >= 7.15 else "人民币升值"))

    vxn_val, vxn_src, vxn_url = get_vxn(opener)
    vxn_status = "数据暂缺" if vxn_val <= 0 else ("科技股极恐" if vxn_val >= 30 else ("杀估值抛压" if vxn_val >= 22 else "波动平缓"))

    skew_val, skew_src, skew_url = get_skew(opener)
    skew_status = "数据暂缺" if skew_val <= 0 else ("尾部黑天鹅预警" if skew_val >= 140 else ("风险积聚" if skew_val >= 132 else "常态平稳"))

    return {
        "fng": {"score": fng_score, "rating": fng_rating, "time": now_str, "source": fng_src, "url": fng_url},
        "vix": {"val": vix_val, "status": vix_status, "time": now_str, "source": vix_src, "url": vix_url, "desc": "<15 平稳低波 | 15~20 正常震荡 | 20~30 警惕波动 | >30 极度恐慌"},
        "usdcny": {"val": usdcny_val, "status": usdcny_status, "time": now_str, "source": usdcny_src, "url": usdcny_url, "desc": "美元兑人民币汇率，QDII换汇成本及折溢价关键锚"},
        "vxn": {"val": vxn_val, "status": vxn_status, "time": now_str, "source": vxn_src, "url": vxn_url, "desc": "纳斯达克100期权隐波，监测科技成长股杀估值抛压"},
        "skew": {"val": skew_val, "status": skew_status, "time": now_str, "source": skew_src, "url": skew_url, "desc": "基准100。>135提示期权市场尾部极度对冲成本升高"}
    }

def fetch_fund_country_distribution(opener, code, is_qdii=False):
    """
    多源获取基金的国家/地区资产配置分布及披露日期：
    返回格式统一为: {"date": "YYYY-MM-DD", "countries": [...]}
    """
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

    # 1. 公告正文穿透解析[cite: 1]
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
                
                for cand in candidates[:3]:
                    ann_url = f"https://np-cnotice-fund.eastmoney.com/api/content/ann?client_source=web_fund&show_all=1&art_code={cand['id']}"
                    req_ann = urllib.request.Request(ann_url, headers={
                        **DEFAULT_HEADERS,
                        "Referer": "https://fund.eastmoney.com/"
                    })
                    with opener.open(req_ann, timeout=15) as resp:
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

    # 2. 国海富兰克林官网详情页
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

    # 3. 天天基金 PC 端海外资产配置接口 (gwzb)[cite: 1]
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

    # 宽基与 A 股兜底[cite: 1]
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
    url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&code={query_code}"
    headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Referer": f"https://fundf10.eastmoney.com/cyrjg_{query_code}.html",
        "Accept": "*/*"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
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
        years = [str(current_year - i) for i in range(3)]
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
        manage_match = re.search(r'管理费率?[：:]\s*([\d.]+)%', main_html)
        if manage_match: meta["fee_manage"] = manage_match.group(1)
        custody_match = re.search(r'托管费率?[：:]\s*([\d.]+)%', main_html)
        if custody_match: meta["fee_custody"] = custody_match.group(1)
        sales_match = re.search(r'销售服务费率?[：:]\s*([\d.]+)%', main_html)
        if sales_match: meta["fee_sales"] = sales_match.group(1)
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
                m = re.search(r'管理费[：:]\s*([\d.]+)%', rate_text)
                if m: meta["fee_manage"] = m.group(1)
            if meta["fee_custody"] is None:
                c = re.search(r'托管费[：:]\s*([\d.]+)%', rate_text)
                if c: meta["fee_custody"] = c.group(1)
            if meta["fee_sales"] is None:
                s = re.search(r'销售服务费[：:]\s*([\d.]+)%', rate_text)
                if s: meta["fee_sales"] = s.group(1)
        buy_source_m = re.search(r'var\s+fund_sourceRate\s*=\s*"([^"]+)";', js_content)
        buy_rate_m = re.search(r'var\s+fund_Rate\s*=\s*"([^"]+)";', js_content)
        if buy_source_m and buy_source_m.group(1): meta["fee_source"] = buy_source_m.group(1)
        if buy_rate_m and buy_rate_m.group(1): meta["fee_purchase"] = buy_rate_m.group(1)

        try:
            df_xq = ak.fund_individual_basic_info_xq(symbol=code)
            if df_xq is not None and not df_xq.empty:
                cols = df_xq.columns.tolist()
                if len(cols) >= 2:
                    info_dict = dict(zip(df_xq[cols[0]], df_xq[cols[1]]))
                    for k in ["基金规模", "资产规模", "最新规模"]:
                        if k in info_dict and info_dict[k]:
                            scale_str = str(info_dict[k])
                            unit_match = re.search(r'([\d.]+)\s*(亿|万)', scale_str)
                            if unit_match:
                                num = float(unit_match.group(1))
                                if unit_match.group(2) == '万': num /= 10000.0
                                meta["scale_val"] = num
                                meta["scale"] = f"{num:.2f} 亿"
                            break
        except Exception: pass

    f10_url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
    try:
        req = urllib.request.Request(f10_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            f10_html = resp.read().decode('utf-8', errors='ignore')
            if meta["fee_manage"] is None:
                mm = re.search(r'管理费率.*?([\d.]+)%', f10_html, re.S)
                if mm: meta["fee_manage"] = mm.group(1)
            if meta["fee_custody"] is None:
                cc = re.search(r'托管费率.*?([\d.]+)%', f10_html, re.S)
                if cc: meta["fee_custody"] = cc.group(1)
            if meta["fee_sales"] is None:
                ss = re.search(r'销售服务费率.*?([\d.]+)%', f10_html, re.S)
                if ss: meta["fee_sales"] = ss.group(1)
            if meta["scale"] == "未知":
                scale_m = re.search(r'基金规模.*?([\d.]+)\s*亿元', f10_html, re.S)
                if scale_m:
                    meta["scale_val"] = float(scale_m.group(1))
                    meta["scale"] = f"{meta['scale_val']:.2f} 亿"
            red_section = re.search(r'赎回费率.*?(?:</table>|</div>\s*</div>)', f10_html, re.S)
            if red_section:
                red_html = red_section.group(0)
                rows = re.findall(r'<tr[^>]*>(.*?)<\/tr>', red_html, re.S)
                red_tiers = []
                for row in rows:
                    cols = re.findall(r'<td[^>]*>(.*?)<\/td>', row, re.S)
                    if len(cols) >= 2:
                        period_desc = re.sub(r'<[^>]+>', '', cols[0]).strip()
                        rate_desc = re.sub(r'<[^>]+>', '', cols[1]).strip()
                        if period_desc and rate_desc and '%' in rate_desc:
                            red_tiers.append(f"{period_desc}: {rate_desc}")
                if red_tiers: meta["fee_redemption"] = " | ".join(red_tiers)
    except Exception: pass

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
    page_size = 20

    while True:
        base_url = "https://api.fund.eastmoney.com/f10/lsjz"
        params = {
            "callback": "jQuery11230_lsjz", "fundCode": code, "pageIndex": page_index, "pageSize": page_size,
            "startDate": start_date, "endDate": end_date, "_": str(int(time.time() * 1000))
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": DEFAULT_HEADERS["User-Agent"], "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=5) as resp:
                html = resp.read().decode('utf-8')
                match = re.search(r'jQuery11230_lsjz\((.*)\)', html)
                if match:
                    res_json = json.loads(match.group(1))
                    lsjz = res_json.get("Data", {}).get("LSJZList", [])
                    if not lsjz: break
                    for item in lsjz:
                        if item.get("DWJZ"): all_data.append({"date": item["FSRQ"], "nav": float(item["DWJZ"])})
                    if len(lsjz) < page_size: break
                    page_index += 1
                else: break
        except Exception: break

    if all_data:
        cache = {'start_date': start_date, 'end_date': end_date, 'data': all_data}
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception: pass

    return all_data if all_data else None

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

def generate_html_report(results, start_date, end_date, today_str, metrics, is_debug_mode=False, filename="fund_drawdown_dashboard.html"):
    CPO_CODES = {"022365", "540010", "002112", "011892", "021528", "009645", "011370", "011452", "016371", "001956", "016234", "016173", "006616", "018291", "020661", "017462", "001438", "008984", "180031", "004320", "027063"}
    STORAGE_CODES = {"025500", "025209", "018816", "014320"}
    SEMICONDUCTOR_CODES = {"024418", "024975", "020640", "019633", "024424", "017811", "013841", "007491", "020629", "017747", "026633", "162214", "007343", "018777"}
    AI_CODES = {"024663", "024726", "023286", "023408", "025506", "025493", "025653", "005963", "014162", "011840", "024412", "024775", "026613", "023551", "024561"}
    GRID_CODES = {"025857", "023639", "023675", "019411", "167002", "020425", "002164", "017133", "017042", "026681", "016387", "025833", "011172", "001665", "018919"}
    ROBOT_CODES = {"016531", "018345", "020482", "018125", "007519", "014243", "018957", "003835", "014939", "008998", "004233", "008182", "017968", "024648"}
    INDEX_SET_LOCAL = {"NDX", "SPX", "SOXX", "SOXL"}
    PRECIOUS_METALS_LOCAL = {"XAU", "AUM", "XAG"}
    CRYPTO_LOCAL = {"BTC", "ETH", "SOL", "BNB"}
    col_count = 22

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
            "SOXX": "https://quote.eastmoney.com/us/SOXX.html",
            "SOXL": "https://quote.eastmoney.com/us/SOXL.html",
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
        rec_pct = min(max(r['recovery_rate'], 0), 100)
        reb_pct = min(max(r['rebound_gain'], 0), 100)
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
        elif r['code'] in PRECIOUS_METALS_LOCAL: group = "metals"; macro_category = "other"
        elif r['code'] in CRYPTO_LOCAL: group = "crypto"; macro_category = "other"
        elif r['code'] in INDEX_SET_LOCAL: group = "index"; macro_category = "other"
        elif r['code'] in NDX_PASSIVE_CODES: group = "ndx_passive"; macro_category = "us_share"
        elif r['code'] in SPX_PASSIVE_CODES: group = "spx_passive"; macro_category = "us_share"
        else: group = "us_active"; macro_category = "us_share"

        nav_display_html = f'<span class="highlight-special-nav">{r["latest_nav"]:.4f}</span>' if group in ["metals", "crypto", "index"] else f'{r["latest_nav"]:.4f}'
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
        <tr data-group="{group}" data-macro="{macro_category}" class="fund-row" data-code="{r['code']}">
            <td class="fav-col" data-val="0"><button class="star-btn" data-code="{r['code']}" title="点击添加/取消自选">☆</button></td>
            <td class="code" data-val="{r['code']}">{r['code']}</td>
            <td class="name" data-val="{r['name']}">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
                    <a href="{fund_url}" target="_blank" title="点击查看行情/概况" style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{r['name']}</a>
                    <button class="dca-btn" data-code="{r['code']}" title="启动定投回测测算小工具">📊 定投</button>
                </div>
                <div class="redemption-sub" style="white-space: normal; line-height: 1.6;">赎回:<br>{redemption_lines}</div>
            </td>
            <td data-val="{r['scale_val']}" class="highlight-val">{r['scale']}</td>
            <td data-val="{r['fee_val']}">{r['fee_total']} <span class="fee-sub">(管:{r['fee_manage']}/托:{r['fee_custody']}/销:{r['fee_sales']})</span></td>
            <td data-val="{fee_pur_val}">{fee_purchase_html}</td>
            <td data-val="{limit_val}">{r.get('buy_status', '--')}<div class="fee-sub">{limit_display}</div></td>
            <td data-val="{r['max_nav']}">{max_nav_display}</td>
            <td data-val="{r['min_nav']}">{min_nav_display}</td>
            <td data-val="{r['latest_nav']}">{nav_display_html}</td>
            <td class="metric-red" data-val="{r['max_drawdown']}">
                <div class="progress-container progress-text">
                    <div class="progress-bar bar-red" style="width: {max_dd_pct}%;">
                        <span>{r['max_drawdown']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td class="metric-green" data-val="{r['rebound_gain']}">
                <div class="progress-container progress-text">
                    <div class="progress-bar bar-green" style="width: {reb_pct}%;">
                        <span>{r['rebound_gain']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td data-val="{r['recovery_rate']}">
                <div class="progress-container progress-text">
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

        # 左侧前十大持仓卡片构建
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
            <div class="quarter-card empty-holdings-placeholder">
                <div class="quarter-label"><span class="quarter-title">前十大持仓</span></div>
                <div style="flex:1; display:flex; align-items:center; justify-content:center; color:var(--footer-text); font-size:12px;">
                    暂无持仓披露数据
                </div>
            </div>
            """

        # 左侧持有人结构环状图卡片构建[cite: 3]
        holder_data = r.get("holder_struct")
        if holder_data and ("inst" in holder_data) and ("indiv" in holder_data):
            inst_r = holder_data["inst"]
            indiv_r = holder_data["indiv"]
            h_date = holder_data.get("date", "--")
            pie_card_html = f"""
            <div class="quarter-card holder-card">
                <div class="quarter-label"><span class="quarter-title">持有人结构</span></div>
                <div class="holder-pie-wrapper">
                    <canvas id="holder-chart-{r['code']}" data-inst="{inst_r}" data-indiv="{indiv_r}"></canvas>
                </div>
                <div class="holder-date-sub">披露日期: {h_date}</div>
            </div>
            """
        else:
            pie_card_html = f"""
            <div class="quarter-card holder-card">
                <div class="quarter-label"><span class="quarter-title">持有人结构</span></div>
                <div style="flex:1; display:flex; align-items:center; justify-content:center; color:var(--footer-text); font-size:11px;">
                    暂无结构数据
                </div>
                <div class="holder-date-sub">披露日期: --</div>
            </div>
            """

        # 右侧 1/4: 国家占比环状图卡片[cite: 3]
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

        # 右侧 3/4: 走势折线图[cite: 3]
        chart_html = f"""
        <div class="chart-container" id="chart-container-{r['code']}">
            <div class="chart-controls">
                <button class="period-btn active" data-period="month" data-code="{r['code']}">近一月</button>
                <button class="period-btn" data-period="quarter" data-code="{r['code']}">近三月</button>
                <button class="period-btn" data-period="half" data-code="{r['code']}">近半年</button>
                <button class="period-btn" data-period="year" data-code="{r['code']}">近一年</button>
                <button class="period-btn" data-period="ytd" data-code="{r['code']}">今年内</button>
                <button class="period-btn" data-period="week" data-code="{r['code']}">近一周</button>
            </div>
            <canvas id="chart-{r['code']}" width="400" height="200"></canvas>
        </div>
        """

        # 展开行组装[cite: 3]
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

    friend_links = [
        {"name": "WISE HOLD", "url": "https://www.wise-hold.com/", "desc": "追踪机构持仓与政商名人投资动向"},
        {"name": "WiseETF", "url": "https://www.wise-etf.com/", "desc": "美股ETF/QDII基金估值与溢价监控"},
        {"name": "纳指估值助手", "url": "https://nsdk.top/", "desc": "纳指基金估值与持仓参考"},
        {"name": "定投估值计算机", "url": "https://btcdca.me/", "desc": "多资产定投策略与估值评分"},
        {"name": "FiNews 美股日报", "url": "https://finews.elsetech.app/", "desc": "每日美股盘后总结与新闻聚合"}
    ]
    friend_cards_html = "".join([f"""
        <div class="friend-card">
            <a href="{link['url']}" target="_blank">{link['name']}</a>
            <span class="friend-desc">{link['desc']}</span>
        </div>
    """ for link in friend_links])

    now_dt = datetime.now()
    update_time_str = now_dt.strftime("%Y-%m-%d %H:%M")

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
            padding-right: 6px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        
        .macro-metrics-grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
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

        .home-grid-section {{ display: grid; grid-template-columns: 2fr 1fr; gap: 14px; }}
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
        .global-dca-filter-card.collapsed .global-dca-filter-body {{ display: none; }}
        .global-dca-filter-card.collapsed #gDcaToggleIcon {{ transform: rotate(-90deg); }}
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
        table {{ width: 100%; min-width: 2550px; border-collapse: collapse; font-size: 12px; text-align: right; table-layout: fixed; }}
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

        .progress-container {{ background-color: var(--progress-track); border-radius: 6px; overflow: hidden; height: 20px; width: 100%; position: relative; }}
        .progress-bar {{ height: 100%; border-radius: 6px; min-width: 42px; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; box-sizing: border-box; }}
        .progress-bar span {{ color: #fff; font-size: 11px; font-weight: 600; }}
        .bar-red {{ background-color: #d93025; }}
        .bar-blue {{ background-color: #1a73e8; }}
        .bar-green {{ background-color: #188038; }}
        .metric-red {{ color: #d93025; font-weight: 600; }}
        .metric-green {{ color: #188038; font-weight: 600; }}
        .gain-positive {{ color: #d93025; font-weight: bold; }}
        .gain-negative {{ color: #188038; font-weight: bold; }}
        .gain-date {{ font-size: 10px; color: var(--footer-text); }}

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
        .stock-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
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
        .friend-card {{ background: var(--card-bg); border-radius: 6px; padding: 8px 10px; border: 1px solid var(--border); }}
        .friend-card a {{ color: var(--link-color); text-decoration: none; font-weight: 600; font-size: 12px; display: block; }}
        .friend-desc {{ font-size: 10px; color: var(--footer-text); }}

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

        /* 移动端与平板响应式适配 */
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
            .nav-brand {{
                font-size: 15px;
            }}
            .views-container {{
                padding: 8px 10px;
                height: auto;
                overflow: visible;
            }}
            .view-pane {{
                height: auto;
                overflow: visible;
            }}
            .macro-metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 8px;
            }}
            .home-grid-section {{
                grid-template-columns: 1fr;
                gap: 10px;
            }}
            .sub-filter-bar {{
                flex-direction: column;
                align-items: stretch;
                padding: 10px;
                gap: 8px;
            }}
            .search-box-wrap {{
                width: 100%;
            }}
            .search-box-wrap input {{
                height: 32px;
                font-size: 13px;
            }}
            .global-dca-filter-card {{
                flex-direction: column;
                align-items: stretch;
                padding: 10px;
                gap: 8px;
            }}
            .global-dca-filter-body {{
                flex-direction: column;
                align-items: stretch;
                width: 100%;
            }}
            .global-dca-filter-card select,
            .global-dca-filter-card button {{
                width: 100%;
                height: 32px;
                font-size: 12px;
            }}
            .table-container {{
                height: auto;
                flex: none;
                max-height: 70vh;
                padding: 4px;
            }}
            .holdings-wrapper {{
                flex-direction: column;
                gap: 10px;
            }}
            .holdings-container {{
                width: 100%;
                flex: none;
                grid-template-columns: 1fr;
                gap: 8px;
            }}
            .empty-holdings-placeholder {{
                grid-column: span 1;
            }}
            .right-chart-wrapper {{
                width: 100%;
                flex: none;
                flex-direction: column;
                gap: 10px;
            }}
            .country-card, .chart-container {{
                width: 100%;
                flex: none;
            }}
            .modal-card {{
                width: 95%;
                max-height: 90vh;
            }}
            .modal-body {{
                padding: 10px 12px;
            }}
            .dca-controls {{
                grid-template-columns: 1fr;
            }}
            .dca-results-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .dca-result-card:last-child {{
                grid-column: span 2;
            }}
            .footer-note {{
                flex-direction: column;
                align-items: flex-start;
                gap: 6px;
                margin-bottom: 12px;
            }}
        }}
        @media (max-width: 480px) {{
            .macro-metrics-grid {{
                grid-template-columns: 1fr;
            }}
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
                <div class="macro-metrics-grid">
                    <div class="metric-card">
                        <div class="metric-header">
                            <span>CNN 恐慌贪婪指数</span>
                            <span style="font-size:10px; color:var(--footer-text);">{fng['time']}</span>
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
                            <span style="font-size:10px; color:var(--footer-text);">{vix['time']}</span>
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
                            <span style="font-size:10px; color:var(--footer-text);">{usdcny['time']}</span>
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
                            <span style="font-size:10px; color:var(--footer-text);">{vxn['time']}</span>
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
                            <span style="font-size:10px; color:var(--footer-text);">{skew['time']}</span>
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
                </div>

                <div class="home-grid-section">
                    <div class="home-card-box">
                        <div class="home-card-title">
                            <span>📌 宏观资产配置速览与逻辑备忘</span>
                            <span style="font-size:11px; font-weight:normal; color:var(--link-color);">数据源直通跳转</span>
                        </div>
                        <div class="home-card-body">
                            <p>• <strong>恐慌指标协同判断：</strong> 当 <strong>VIX 恐慌指数</strong> 显著飙升（&gt;20）且 <strong>CNN 情绪指数</strong> 步入极度恐惧（0~25）时，通常对应全市场非理性杀跌的左侧加仓与定投翻倍窗口。</p>
                            <p>• <strong>汇率对冲与折溢价：</strong> 跟踪 <strong>USD/CNY 汇率</strong> 走势，当汇率波动较大时，QDII 基金的实际净值波动将叠加汇率损益，需警惕场内溢价过高风险。</p>
                            <div style="padding: 24px; text-align: center; background: var(--hover-bg); border-radius: 8px; margin-top: 10px; border: 1px dashed var(--border);">
                                💡 每个宏观卡片底部均配有直达源头的官方链接（CNN、CBOE、新浪等），可随时点击校验一手数据。
                            </div>
                        </div>
                    </div>

                    <div class="home-card-box">
                        <div class="home-card-title">
                            <span>🔗 研投工具导航</span>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:8px;">
                            {friend_cards_html}
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 视图 2：基金量化看板 -->
        <section id="fundView" class="view-pane">
            <div class="sub-filter-bar">
                <div class="category-nav">
                    <button class="cat-btn fav-filter" data-macro="favorites" data-sub="favorites">⭐ 我的自选</button>
                    <span class="category-title" style="margin-left: 6px;">市场大类:</span>
                    <button class="cat-btn active" data-macro="all" data-sub="all">全部展示</button>
                    
                    <span class="category-title" style="margin-left: 8px;">美股:</span>
                    <button class="cat-btn" data-macro="us_share" data-sub="all">美股全量</button>
                    <button class="cat-btn" data-macro="us_share" data-sub="us_active">美股主动</button>
                    <button class="cat-btn" data-macro="us_share" data-sub="ndx_passive">纳指被动</button>
                    <button class="cat-btn" data-macro="us_share" data-sub="spx_passive">标普被动</button>
                    
                    <span class="category-title" style="margin-left: 8px;">A股板块:</span>
                    <button class="cat-btn" data-macro="a_share" data-sub="all">A股全量</button>
                    <button class="cat-btn" data-macro="a_share" data-sub="cpo">CPO</button>
                    <button class="cat-btn" data-macro="a_share" data-sub="storage">存储芯片</button>
                    <button class="cat-btn" data-macro="a_share" data-sub="semiconductor">半导体材料</button>
                    <button class="cat-btn" data-macro="a_share" data-sub="ai">人工智能</button>
                    <button class="cat-btn" data-macro="a_share" data-sub="grid">电网设备</button>
                    <button class="cat-btn" data-macro="a_share" data-sub="robot">机器人</button>
                    
                    <span class="category-title" style="margin-left: 8px;">其他:</span>
                    <button class="cat-btn" data-macro="other" data-sub="metals">贵金属</button>
                    <button class="cat-btn" data-macro="other" data-sub="crypto">加密货币</button>
                    <button class="cat-btn" data-macro="other" data-sub="index">主流指数</button>
                </div>

                <div class="search-box-wrap">
                    <input type="text" id="searchInput" placeholder="🔍 搜索代码或名称...">
                </div>
            </div>

            <!-- 全局动态定投筛选栏 -->
            <div class="global-dca-filter-card" id="gDcaCard">
                <div class="global-dca-filter-header" id="gDcaToggleBtn">
                    <span class="global-dca-filter-title">📊 动态定投参数配置</span>
                    <span id="gDcaToggleIcon">▼</span>
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

            <div class="table-container">
                <table id="fundTable">
                    <thead>
                        <tr>
                            <th data-col="0" onclick="handleHeaderClick(0)">收藏 <span class="sort-icon">⇅</span></th>
                            <th data-col="1" onclick="handleHeaderClick(1)">代码 <span class="sort-icon">⇅</span></th>
                            <th data-col="2" onclick="handleHeaderClick(2)">基金名称 / 赎回费率阶梯 <span class="sort-icon">⇅</span></th>
                            <th data-col="3" onclick="handleHeaderClick(3)">最新规模 <span class="sort-icon">⇅</span></th>
                            <th data-col="4" onclick="handleHeaderClick(4)">运作费(管/托/销) <span class="sort-icon">⇅</span></th>
                            <th data-col="5" onclick="handleHeaderClick(5)">申购费率 <span class="sort-icon">⇅</span></th>
                            <th data-col="6" onclick="handleHeaderClick(6)">申购状态/限额 <span class="sort-icon">⇅</span></th>
                            <th data-col="7" onclick="handleHeaderClick(7)">最高净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="8" onclick="handleHeaderClick(8)">最低净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="9" onclick="handleHeaderClick(9)">最新净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="10" onclick="handleHeaderClick(10)">最大回撤 <span class="sort-icon">⇅</span></th>
                            <th data-col="11" onclick="handleHeaderClick(11)">自低点反弹 <span class="sort-icon">⇅</span></th>
                            <th data-col="12" onclick="handleHeaderClick(12)">修复程度 <span class="sort-icon">⇅</span></th>
                            <th data-col="13" onclick="handleHeaderClick(13)">修复时间 <span class="sort-icon">⇅</span></th>
                            <th data-col="14" onclick="handleHeaderClick(14)">{col_today_title} <span class="sort-icon">⇅</span></th>
                            <th data-col="15" onclick="handleHeaderClick(15)">近一周 <span class="sort-icon">⇅</span></th>
                            <th data-col="16" onclick="handleHeaderClick(16)">近一月 <span class="sort-icon">⇅</span></th>
                            <th data-col="17" onclick="handleHeaderClick(17)">近三月 <span class="sort-icon">⇅</span></th>
                            <th data-col="18" onclick="handleHeaderClick(18)">近半年 <span class="sort-icon">⇅</span></th>
                            <th data-col="19" onclick="handleHeaderClick(19)">近一年 <span class="sort-icon">⇅</span></th>
                            <th data-col="20" onclick="handleHeaderClick(20)">今年内 <span class="sort-icon">⇅</span></th>
                            <th data-col="21" onclick="handleHeaderClick(21)"><span id="dcaHeaderTitle">月定投</span>收益 <span class="sort-icon">⇅</span></th>
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
            }});
        }})();

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
            const latestDate = new Date(allDates[allDates.length - 1]);
            let startDate = new Date(latestDate);

            if (range === 'half') {{
                startDate.setMonth(latestDate.getMonth() - 6);
            }} else if (range === 'year') {{
                startDate.setFullYear(latestDate.getFullYear() - 1);
            }} else if (range === 'ytd') {{
                startDate = new Date(latestDate.getFullYear(), 0, 1);
            }} else {{
                startDate = new Date(allDates[0]);
            }}

            const filtered = [];
            for (let i = 0; i < allDates.length; i++) {{
                const d = new Date(allDates[i]);
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

            document.getElementById('gDcaToggleBtn').addEventListener('click', function() {{
                document.getElementById('gDcaCard').classList.toggle('collapsed');
            }});

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
            const catBtns = document.querySelectorAll('.cat-btn');
            const searchInput = document.getElementById('searchInput');
            const emptyRow = document.getElementById('empty-row');
            const allRows = document.querySelectorAll('#fundTable tbody tr:not(#empty-row)');
            let currentMacro = 'all';
            let currentSub = 'all';
            let searchKeyword = '';

            updateTableDca();

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

                    const matchSearch = keyword === '' || name.includes(keyword) || code.includes(keyword);
                    const visible = matchCategory && matchSearch;

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
                            emptyRow.querySelector('td').textContent = keyword ? '未找到匹配基金' : '当前分类暂无数据';
                        }}
                    }}
                }}
            }}

            catBtns.forEach(btn => {{
                btn.addEventListener('click', function() {{
                    catBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    currentMacro = this.dataset.macro;
                    currentSub = this.dataset.sub;
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

        // 环形图中心百分比标签插件
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

        // 专业十字光标插件（Crosshair）
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
                ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a';
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

        // 初始化持有人结构环状图（完全对齐国家占比的打开动画与配置结构）[cite: 3]
        function initHolderChart(code) {{
            const canvas = document.getElementById(`holder-chart-${{code}}`);
            if (!canvas) return;

            if (holderChartInstances[code]) {{
                if (typeof holderChartInstances[code].destroy === 'function') {{
                    holderChartInstances[code].destroy();
                    delete holderChartInstances[code];
                }}
            }}
            const inst = parseFloat(canvas.getAttribute('data-inst'));
            const indiv = parseFloat(canvas.getAttribute('data-indiv'));
            if (isNaN(inst) || isNaN(indiv)) return;

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            const sliceBorderColor = isDark ? '#2a2a2a' : '#f0f2f5';
            const textColor = isDark ? '#e0e0e0' : '#3c4043';

            const ctx = canvas.getContext('2d');
            holderChartInstances[code] = new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: ['机构持有', '个人持有'],
                    datasets: [{{
                        data: [inst, indiv],
                        backgroundColor: ['#1a73e8', '#ff9800'],
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
                                font: {{ size: 10, weight: '500' }},
                                boxWidth: 8,
                                boxHeight: 8,
                                usePointStyle: true,
                                padding: 6,
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

        // 初始化国家资产占比环状图[cite: 3]
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

        // 双轴折线图构建函数
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
                        chart.draw();
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
                        setTimeout(() => {{
                            initChart(code);
                            initHolderChart(code);
                            initCountryChart(code);
                        }}, 50);
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
        url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1d&startTime={start_ts}&endTime={end_ts}&limit=1000"
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

def fetch_index_data(symbol, start_date, end_date):
    try:
        df = None
        if symbol in SINA_INDEX_MAP:
            sina_symbol = SINA_INDEX_MAP[symbol]
            df = ak.index_us_stock_sina(symbol=sina_symbol)
        elif symbol in ["SOXL", "SOXX"]:
            for try_symbol in [f"105.{symbol}", symbol, f"106.{symbol}"]:
                try:
                    df = ak.stock_us_hist(symbol=try_symbol, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""), adjust="")
                    if df is not None and not df.empty: break
                except Exception: continue

        if df is None or df.empty: return None

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
                if nav > 0: data.append({"date": row['date_str'], "nav": nav})
            except Exception: continue
        return data if data else None
    except Exception:
        return None

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
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
        target_metals = ["XAU"]
        target_cryptos = ["BTC"]
        target_indices = ["NDX"]
        print("\n=======================================================")
        print("🛠️ 当前处于【测试调试阶段 (DEBUG MODE)】")
        print(f"👉 仅抓取 {len(target_funds)} 只核心测试基金 + 极简大类资产样本")
        print("=======================================================\n")
    else:
        target_funds = PROD_FUNDS
        target_metals = ["XAU", "AUM", "XAG"]
        target_cryptos = ["BTC", "ETH", "SOL", "BNB"]
        target_indices = ["NDX", "SPX", "SOXX", "SOXL"]
        print("\n=======================================================")
        print("🚀 当前处于【正式发布阶段 (PROD MODE)】")
        print(f"👉 正在抓取全量 {len(target_funds)} 只基金与全品类宏观大类资产...")
        print("=======================================================\n")

    opener = get_direct_opener()
    print(f"统计区间: {args.start} 至 {args.end}")
    
    home_metrics = fetch_home_market_metrics(opener)
    print(f"📊 核心宏观指标获取成功: 恐慌贪婪 {home_metrics['fng']['score']} | VIX {home_metrics['vix']['val']} | USD/CNY {home_metrics['usdcny']['val']} | VXN {home_metrics['vxn']['val']} | SKEW {home_metrics['skew']['val']}")

    results = []
    for idx, code in enumerate(target_funds, start=1):
        meta = fetch_fund_detail_meta(opener, code)
        raw_data = fetch_from_eastmoney(opener, code, args.start, args.end)
        if not raw_data:
            print(f"[{idx}/{len(target_funds)}] {code} - {meta['name']} ... ❌ 历史净值抓取失败")
            continue
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
            c_date = meta["countries_info"].get("date", "--")
            print(f"[{idx}/{len(target_funds)}] {code} - {meta['name']} ... ✅ 完成 (国家披露期: {c_date})")
        time.sleep(random.uniform(0.05, 0.1))

    # 贵金属
    for symbol in target_metals:
        try:
            data = fetch_precious_metals_data(symbol, args.start, args.end)
            if data:
                meta_name = PRECIOUS_METALS_NAMES.get(symbol, symbol)
                res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
                if res:
                    res.update({
                        "code": symbol, "name": meta_name, "scale": "--", "scale_val": -1.0,
                        "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                        "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                        "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                        "holder_struct": None, "countries_info": {"date": "--", "countries": []}, "source": "贵金属行情", "nav_data": data
                    })
                    results.append(res)
        except Exception: pass

    # 加密货币
    for symbol in target_cryptos:
        try:
            data = fetch_crypto_data(symbol, args.start, args.end)
            if data:
                res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
                if res:
                    res.update({
                        "code": symbol, "name": CRYPTO_NAMES.get(symbol, symbol), "scale": "--", "scale_val": -1.0,
                        "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                        "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                        "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                        "holder_struct": None, "countries_info": {"date": "--", "countries": []}, "source": "现货行情", "nav_data": data
                    })
                    results.append(res)
        except Exception: pass

    # 指数
    for symbol in target_indices:
        try:
            data = fetch_index_data(symbol, args.start, args.end)
            if data:
                res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
                if res:
                    res.update({
                        "code": symbol, "name": INDEX_NAMES.get(symbol, symbol), "scale": "--", "scale_val": -1.0,
                        "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                        "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                        "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                        "holder_struct": None, "countries_info": {"date": "--", "countries": []}, "source": "指数行情", "nav_data": data
                    })
                    results.append(res)
        except Exception: pass

    if results:
        abs_path = generate_html_report(results, args.start, args.end, today_str, home_metrics, is_debug_mode=is_debug, filename=args.out)
        print(f"\n🎉 升级版网页构建成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception: pass

if __name__ == "__main__":
    main()