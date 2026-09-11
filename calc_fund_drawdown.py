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

DEFAULT_FUNDS = [
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

INDEX_SYMBOLS = ["NDX", "SPX", "SOXX", "SOXL"]
INDEX_NAMES = {
    "NDX": "纳斯达克100指数",
    "SPX": "标普500指数",
    "SOXX": "iShares 半导体ETF",
    "SOXL": "三倍做多半导体ETF-Direxion"
}

PRECIOUS_METALS_SYMBOLS = ["XAU", "AUM", "XAG"]
PRECIOUS_METALS_NAMES = {
    "XAU": "伦敦金 (XAU)",
    "AUM": "黄金连续 (AUM)",
    "XAG": "伦敦银 (XAG)"
}

CRYPTO_SYMBOLS = ["BTC", "ETH", "SOL", "BNB"]
CRYPTO_NAMES = {
    "BTC": "比特币 (BTC/USDT)",
    "ETH": "以太坊 (ETH/USDT)",
    "SOL": "索拉纳 (SOL/USDT)",
    "BNB": "币安币 (BNB/USDT)"
}

INDEX_SET = set(INDEX_SYMBOLS)
PRECIOUS_METALS_SET = set(PRECIOUS_METALS_SYMBOLS)
CRYPTO_SET = set(CRYPTO_SYMBOLS)

SINA_INDEX_MAP = {
    "NDX": ".NDX",
    "SPX": ".INX",
}

CACHE_DIR = "cache"
HOLDINGS_CACHE_DIR = os.path.join(CACHE_DIR, "holdings")
NAV_CACHE_DIR = os.path.join(CACHE_DIR, "nav")
HOLDER_CACHE_DIR = os.path.join(CACHE_DIR, "holder")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(HOLDINGS_CACHE_DIR, exist_ok=True)
os.makedirs(NAV_CACHE_DIR, exist_ok=True)
os.makedirs(HOLDER_CACHE_DIR, exist_ok=True)

def get_direct_opener():
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def fetch_fear_and_greed_index(opener):
    """抓取全网权威的市场恐慌与贪婪指数（包含美股/加密备选）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.cnn.com/markets/fear-and-greed",
        "Accept": "application/json, text/plain, */*"
    }
    # 优先请求 CNN 恐慌指数数据接口
    url_cnn = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        req = urllib.request.Request(url_cnn, headers=headers)
        with opener.open(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            score = float(data.get("fear_and_greed", {}).get("score", 50))
            rating = data.get("fear_and_greed", {}).get("rating", "neutral")
            return {
                "score": round(score, 1),
                "rating": rating,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "CNN 美股恐慌贪婪指数"
            }
    except Exception:
        pass

    # 备选：Crypto 恐慌贪婪指数
    url_crypto = "https://api.alternative.me/fng/?limit=1"
    try:
        req = urllib.request.Request(url_crypto, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            item = data.get("data", [{}])[0]
            score = float(item.get("value", 50))
            rating = item.get("value_classification", "Neutral").lower()
            return {
                "score": round(score, 1),
                "rating": rating,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "Alternative 市场情绪指数"
            }
    except Exception:
        pass

    return {"score": 50.0, "rating": "neutral", "date": datetime.now().strftime("%Y-%m-%d"), "source": "市场均值"}

def fetch_fund_holder_structure(opener, code):
    """抓取天天基金 F10 持有人结构数据"""
    cache_file = os.path.join(HOLDER_CACHE_DIR, f"{code}_holder.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and "inst" in data and "indiv" in data:
                    return data
        except Exception:
            pass

    url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&code={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://fundf10.eastmoney.com/cyrjg_{code}.html",
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
                if not date_m:
                    continue

                def clean_text(val):
                    return re.sub(r'<[^>]+>', '', val).strip()

                date_str = date_m.group(0)
                inst_text = clean_text(cols[1]).replace('%', '')
                indiv_text = clean_text(cols[2]).replace('%', '')

                inst_val = float(inst_text) if inst_text.replace('.', '', 1).isdigit() else 0.0
                indiv_val = float(indiv_text) if indiv_text.replace('.', '', 1).isdigit() else 0.0

                result = {
                    "date": date_str,
                    "inst": round(inst_val, 2),
                    "indiv": round(indiv_val, 2)
                }

                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception:
        pass

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
            try:
                os.remove(cache_file)
            except Exception:
                pass

    try:
        current_year = datetime.now().year
        years = [str(current_year - i) for i in range(3)]
        all_dfs = []
        for year in years:
            try:
                df = ak.fund_portfolio_hold_em(symbol=code, date=year)
                if df is not None and not df.empty:
                    all_dfs.append(df)
            except Exception:
                pass

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
                    else:
                        raise ValueError("缺少季度信息")

            quarters = sorted(combined['季度'].unique(), reverse=True)[:3]
            result = []
            for q in quarters:
                df_q = combined[combined['季度'] == q].sort_values('占净值比例', ascending=False)
                name_col = '股票名称' if '股票名称' in df_q.columns else '名称' if '名称' in df_q.columns else None
                ratio_col = '占净值比例' if '占净值比例' in df_q.columns else None
                if name_col is None or ratio_col is None:
                    for col in df_q.columns:
                        if '名称' in col:
                            name_col = col
                        if '比例' in col:
                            ratio_col = col
                    if name_col is None or ratio_col is None:
                        continue
                top10 = df_q.head(10)[[name_col, ratio_col]]
                holdings = []
                for _, row in top10.iterrows():
                    name = str(row[name_col])
                    if pd.isna(name) or name == 'nan':
                        continue
                    ratio = float(row[ratio_col])
                    if ratio > 0:
                        holdings.append({'name': name, 'ratio': round(ratio, 2)})
                result.append({'date': q, 'holdings': holdings})
            if result:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception:
        pass

    return []

def fetch_fund_detail_meta(opener, code):
    meta = {
        "name": f"基金_{code}",
        "scale": "未知",
        "scale_val": -1.0,
        "fee_manage": None,
        "fee_custody": None,
        "fee_sales": None,
        "fee_source": "",
        "fee_purchase": "0.00%",
        "fee_redemption": "未知",
        "buy_status": "--",
        "buy_limit": "无限额",
        "buy_limit_val": -1,
        "fee_total": "未知",
        "fee_val": -1.0,
        "holdings": [],
        "holder_struct": None
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://fund.eastmoney.com/{code}.html",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    main_url = f"https://fund.eastmoney.com/{code}.html"
    main_html = None
    try:
        req = urllib.request.Request(main_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            main_html = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    if main_html:
        name_match = re.search(r'<title>(.*?)基金', main_html)
        if name_match:
            meta["name"] = name_match.group(1).strip() + "基金"

        manage_match = re.search(r'管理费率?[：:]\s*([\d.]+)%', main_html)
        if manage_match:
            meta["fee_manage"] = manage_match.group(1)

        custody_match = re.search(r'托管费率?[：:]\s*([\d.]+)%', main_html)
        if custody_match:
            meta["fee_custody"] = custody_match.group(1)

        sales_match = re.search(r'销售服务费率?[：:]\s*([\d.]+)%', main_html)
        if sales_match:
            meta["fee_sales"] = sales_match.group(1)

        rate_section = re.search(r'申购费率[：:](.*?)(?=<div|$)', main_html, re.S)
        if rate_section:
            rates = re.findall(r'([\d.]+%)', rate_section.group(1))
            if rates:
                min_rate_str = min(rates, key=lambda x: float(x.strip('%')))
                meta["fee_source"] = min_rate_str
                meta["fee_purchase"] = min_rate_str

        trade = re.search(r"交易状态：</span>(.*?)</div>", main_html, re.S)
        if trade:
            text = re.sub(r"<.*?>", "", trade.group(1))
            text = text.replace("&nbsp;", "").strip()
            status = re.search(r"^(.*?)\s*\(", text)
            if status:
                meta["buy_status"] = status.group(1).strip()
            limit_match = re.search(r"单日累计购买上限([\d.]+)(万?)元", text)
            if limit_match:
                num = float(limit_match.group(1))
                if limit_match.group(2) == "万":
                    num *= 10000
                meta["buy_limit"] = f"{limit_match.group(1)}{limit_match.group(2)}元"
                meta["buy_limit_val"] = num
            else:
                meta["buy_limit"] = "无限额"
                meta["buy_limit_val"] = -1

    js_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    js_content = None
    try:
        req = urllib.request.Request(js_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            js_content = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    if js_content:
        if meta["name"] == f"基金_{code}":
            match_name = re.search(r'var\s+fS_name\s*=\s*["\']([^"\']+)["\']', js_content)
            if match_name:
                meta["name"] = match_name.group(1)

        rate_match = re.search(r'var\s+Data_rateInverstment\s*=\s*["\']([^"\']+)["\']', js_content)
        if rate_match:
            rate_text = rate_match.group(1)
            if meta["fee_manage"] is None:
                m = re.search(r'管理费[：:]\s*([\d.]+)%', rate_text)
                if m:
                    meta["fee_manage"] = m.group(1)
            if meta["fee_custody"] is None:
                c = re.search(r'托管费[：:]\s*([\d.]+)%', rate_text)
                if c:
                    meta["fee_custody"] = c.group(1)
            if meta["fee_sales"] is None:
                s = re.search(r'销售服务费[：:]\s*([\d.]+)%', rate_text)
                if s:
                    meta["fee_sales"] = s.group(1)

        buy_source_m = re.search(r'var\s+fund_sourceRate\s*=\s*"([^"]+)";', js_content)
        buy_rate_m = re.search(r'var\s+fund_Rate\s*=\s*"([^"]+)";', js_content)
        if buy_source_m and buy_source_m.group(1):
            meta["fee_source"] = buy_source_m.group(1)
        if buy_rate_m and buy_rate_m.group(1):
            meta["fee_purchase"] = buy_rate_m.group(1)

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
                                if unit_match.group(2) == '万':
                                    num /= 10000.0
                                meta["scale_val"] = num
                                meta["scale"] = f"{num:.2f} 亿"
                            else:
                                num_match = re.search(r'([\d.]+)', scale_str)
                                if num_match:
                                    num = float(num_match.group(1))
                                    meta["scale_val"] = num
                                    meta["scale"] = f"{num:.2f} 亿"
                            break
        except Exception:
            pass

    f10_url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
    try:
        req = urllib.request.Request(f10_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            f10_html = resp.read().decode('utf-8', errors='ignore')

            if meta["fee_manage"] is None:
                mm = re.search(r'管理费率.*?([\d.]+)%', f10_html, re.S)
                if mm:
                    meta["fee_manage"] = mm.group(1)
            if meta["fee_custody"] is None:
                cc = re.search(r'托管费率.*?([\d.]+)%', f10_html, re.S)
                if cc:
                    meta["fee_custody"] = cc.group(1)
            if meta["fee_sales"] is None:
                ss = re.search(r'销售服务费率.*?([\d.]+)%', f10_html, re.S)
                if ss:
                    meta["fee_sales"] = ss.group(1)

            if meta["scale"] == "未知":
                scale_m = re.search(r'基金规模.*?([\d.]+)\s*亿元', f10_html, re.S)
                if scale_m:
                    num = float(scale_m.group(1))
                    meta["scale_val"] = num
                    meta["scale"] = f"{num:.2f} 亿"
                else:
                    scale_m = re.search(r'基金规模.*?([\d.]+)\s*万元', f10_html, re.S)
                    if scale_m:
                        num = float(scale_m.group(1)) / 10000.0
                        meta["scale_val"] = num
                        meta["scale"] = f"{num:.2f} 亿"

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
                if red_tiers:
                    meta["fee_redemption"] = " | ".join(red_tiers)
                else:
                    red_m = re.findall(r'([\d.]+)%', red_html)
                    if red_m:
                        meta["fee_redemption"] = f"常规档: {red_m[0]}%"
    except Exception:
        pass

    if meta["fee_manage"] is None:
        meta["fee_manage"] = "--"
    else:
        meta["fee_manage"] = f"{float(meta['fee_manage']):.2f}%"

    if meta["fee_custody"] is None:
        meta["fee_custody"] = "--"
    else:
        meta["fee_custody"] = f"{float(meta['fee_custody']):.2f}%"

    if meta["fee_sales"] is None:
        meta["fee_sales"] = "0.00%"
    else:
        meta["fee_sales"] = f"{float(meta['fee_sales']):.2f}%"

    m_val = float(re.search(r'([\d.]+)', meta["fee_manage"]).group(1)) if meta["fee_manage"] != "--" else 0.0
    c_val = float(re.search(r'([\d.]+)', meta["fee_custody"]).group(1)) if meta["fee_custody"] != "--" else 0.0
    s_val = float(re.search(r'([\d.]+)', meta["fee_sales"]).group(1)) if meta["fee_sales"] != "--" else 0.0
    tot = m_val + c_val + s_val
    if tot > 0:
        meta["fee_val"] = tot
        meta["fee_total"] = f"{tot:.2f}%"
    else:
        meta["fee_total"] = "0.00%"

    meta["holdings"] = fetch_holdings(opener, code)
    meta["holder_struct"] = fetch_fund_holder_structure(opener, code)
    return meta

def fetch_from_eastmoney(opener, code, start_date, end_date):
    cache_file = os.path.join(NAV_CACHE_DIR, f"{code}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            cache_start = cache.get('start_date', '')
            cache_end = cache.get('end_date', '')
            if cache_start <= start_date and cache_end >= end_date:
                return cache.get('data', [])
        except Exception:
            pass

    all_data = []
    page_index = 1
    page_size = 20

    while True:
        base_url = "https://api.fund.eastmoney.com/f10/lsjz"
        params = {
            "callback": "jQuery11230_lsjz",
            "fundCode": code,
            "pageIndex": page_index,
            "pageSize": page_size,
            "startDate": start_date,
            "endDate": end_date,
            "_": str(int(time.time() * 1000))
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=5) as resp:
                html = resp.read().decode('utf-8')
                match = re.search(r'jQuery11230_lsjz\((.*)\)', html)
                if match:
                    res_json = json.loads(match.group(1))
                    lsjz = res_json.get("Data", {}).get("LSJZList", [])
                    if not lsjz:
                        break
                    for item in lsjz:
                        if item.get("DWJZ"):
                            all_data.append({"date": item["FSRQ"], "nav": float(item["DWJZ"])})
                    if len(lsjz) < page_size:
                        break
                    page_index += 1
                else:
                    break
        except Exception:
            break

    if all_data:
        cache = {
            'start_date': start_date,
            'end_date': end_date,
            'data': all_data
        }
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return all_data if all_data else None

def analyze_fund_metrics(valid_data, end_date, cutoff_date, is_qdii=False):
    data_all = sorted(valid_data, key=lambda x: x["date"])
    if not data_all:
        return None

    data_cutoff = [item for item in data_all if item["date"] >= cutoff_date]
    if not data_cutoff:
        data_cutoff = data_all

    latest_nav = data_all[-1]["nav"]
    latest_date = data_all[-1]["date"]

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    if weekday == 5:
        target_friday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    elif weekday == 6:
        target_friday = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    else:
        target_friday = today_str

    is_weekend = (weekday >= 5)
    today_gain = None

    if is_qdii:
        if len(data_all) >= 2:
            prev_nav = data_all[-2]["nav"]
            if prev_nav and prev_nav > 0:
                today_gain = ((latest_nav / prev_nav) - 1) * 100.0
    else:
        if is_weekend:
            if len(data_all) >= 2 and latest_date <= target_friday:
                prev_nav = data_all[-2]["nav"]
                if prev_nav and prev_nav > 0:
                    today_gain = ((latest_nav / prev_nav) - 1) * 100.0
        else:
            if latest_date == today_str and len(data_all) >= 2:
                prev_nav = data_all[-2]["nav"]
                if prev_nav and prev_nav > 0:
                    today_gain = ((latest_nav / prev_nav) - 1) * 100.0
            elif len(data_all) >= 2:
                prev_nav = data_all[-2]["nav"]
                if prev_nav and prev_nav > 0:
                    today_gain = ((latest_nav / prev_nav) - 1) * 100.0

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

    if max_drawdown == 0:
        recovery_rate = 100.0
    elif peak_nav == trough_nav:
        recovery_rate = 0.0
    else:
        recovery_rate = ((latest_nav - trough_nav) / (peak_nav - trough_nav)) * 100.0

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
        if ytd:
            target_dt = latest_dt.replace(month=1, day=1)
        elif days:
            target_dt = latest_dt - timedelta(days=days)
        elif months:
            target_dt = add_months(latest_dt, -months)
        else:
            return None
            
        target_date_str = target_dt.strftime('%Y-%m-%d')
        base_nav = None
        for item in data_all:
            if item['date'] >= target_date_str:
                base_nav = item['nav']
                break
                
        if base_nav is not None and base_nav > 0:
            return ((latest_nav / base_nav) - 1) * 100.0
        return None

    week_gain = calc_gain(days=7)
    month_gain = calc_gain(months=1)
    quarter_gain = calc_gain(months=3)
    half_year_gain = calc_gain(months=6)
    year_gain = calc_gain(months=12)
    ytd_gain = calc_gain(ytd=True)

    return {
        "max_nav": peak_nav,
        "max_nav_date": peak_date,
        "min_nav": trough_nav,
        "min_nav_date": trough_date,
        "latest_nav": latest_nav,
        "latest_date": latest_date,
        "max_drawdown": max_drawdown * 100.0,
        "recovery_rate": recovery_rate,
        "recovery_days": recovery_days,
        "rebound_gain": rebound_gain,
        "today_gain": today_gain,
        "week_gain": week_gain,
        "month_gain": month_gain,
        "quarter_gain": quarter_gain,
        "half_year_gain": half_year_gain,
        "year_gain": year_gain,
        "ytd_gain": ytd_gain
    }

def generate_html_report(results, start_date, end_date, today_str, fear_greed_info, filename="fund_drawdown_dashboard.html"):
    CPO_CODES = {
        "022365", "540010", "002112", "011892", "021528",
        "009645", "011370", "011452", "016371", "001956",
        "016234", "016173", "006616", "018291", "020661",
        "017462", "001438", "008984", "180031", "004320", "027063"
    }

    STORAGE_CODES = {
        "025500", "025209", "018816", "014320"
    }

    SEMICONDUCTOR_CODES = {
        "024418", "024975", "020640", "019633", "024424",
        "017811", "013841", "007491", "020629", "017747",
        "026633", "162214", "007343", "018777"
    }

    AI_CODES = {
        "024663", "024726", "023286", "023408", "025506",
        "025493", "025653", "005963", "014162", "011840",
        "024412", "024775", "026613", "023551", "024561"
    }

    GRID_CODES = {
        "025857", "023639", "023675", "019411", "167002",
        "020425", "002164", "017133", "017042", "026681",
        "016387", "025833", "011172", "001665", "018919"
    }

    ROBOT_CODES = {
        "016531", "018345", "020482", "018125", "007519",
        "014243", "018957", "003835", "014939", "008998",
        "004233", "008182", "017968", "024648"
    }

    INDEX_SET_LOCAL = {"NDX", "SPX", "SOXX", "SOXL"}
    PRECIOUS_METALS_LOCAL = {"XAU", "AUM", "XAG"}
    CRYPTO_LOCAL = {"BTC", "ETH", "SOL", "BNB"}
    col_count = 20

    def date_to_label(date_str):
        if 'Q' in date_str:
            return date_str
        if date_str.isdigit() and len(date_str) == 4:
            return f"{date_str}年报"
        try:
            year, month, _ = date_str.split('-')
            month = int(month)
            quarter = (month - 1) // 3 + 1
            return f"{year}Q{quarter}"
        except Exception:
            return date_str

    def quarter_to_end_date(date_str):
        if not date_str:
            return ""
        if re.match(r'^\d{4}-\d{2}-\d{2}$', str(date_str)):
            return date_str
        m = re.match(r'^(\d{4})Q([1-4])$', str(date_str), re.I)
        if m:
            year = m.group(1)
            q = int(m.group(2))
            end_map = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
            return f"{year}-{end_map[q]}"
        m2 = re.search(r'(\d{4}).*?([1-4])', str(date_str))
        if m2:
            year = m2.group(1)
            q = int(m2.group(2))
            end_map = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
            return f"{year}-{end_map[q]}"
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
            highlighted_parts = []
            for part in parts:
                highlighted = re.sub(r'(\d+\.\d+%)', r'<span class="highlight-rate">\1</span>', part)
                highlighted_parts.append(highlighted)
            redemption_lines = "<br>".join(highlighted_parts)
        else:
            redemption_lines = redemption_text or "未知"

        def format_gain(val):
            if val is None:
                return '-'
            return f"{val:.2f}%"

        def gain_class(val):
            if val is None:
                return ''
            if val > 0:
                return 'gain-positive'
            elif val < 0:
                return 'gain-negative'
            else:
                return ''

        # 分类映射
        if r['code'] in CPO_CODES:
            group = "cpo"
            macro_category = "a_share"
        elif r['code'] in STORAGE_CODES:
            group = "storage"
            macro_category = "a_share"
        elif r['code'] in SEMICONDUCTOR_CODES:
            group = "semiconductor"
            macro_category = "a_share"
        elif r['code'] in AI_CODES:
            group = "ai"
            macro_category = "a_share"
        elif r['code'] in GRID_CODES:
            group = "grid"
            macro_category = "a_share"
        elif r['code'] in ROBOT_CODES:
            group = "robot"
            macro_category = "a_share"
        elif r['code'] in PRECIOUS_METALS_LOCAL:
            group = "metals"
            macro_category = "other"
        elif r['code'] in CRYPTO_LOCAL:
            group = "crypto"
            macro_category = "other"
        elif r['code'] in INDEX_SET_LOCAL:
            group = "index"
            macro_category = "other"
        elif r['code'] in NDX_PASSIVE_CODES:
            group = "ndx_passive"
            macro_category = "us_share"
        elif r['code'] in SPX_PASSIVE_CODES:
            group = "spx_passive"
            macro_category = "us_share"
        else:
            group = "us_active"
            macro_category = "us_share"

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
            <td class="code" data-val="{r['code']}">{r['code']}</td>
            <td class="name" data-val="{r['name']}">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
                    <a href="{fund_url}" target="_blank" title="点击查看行情/概况" style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{r['name']}</a>
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
                prev_holdings_dict = {}
                if prev_period:
                    prev_holdings_dict = {h['name']: h['ratio'] for h in prev_period['holdings']}
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
                            prev_ratio = prev_holdings_dict[name]
                            diff = ratio - prev_ratio
                            if abs(diff) < 0.01:
                                change_text = '持平'
                                change_class = ''
                            elif diff > 0.3:
                                change_text = f'加仓 {diff:.2f}%'
                                change_class = 'change-add'
                            elif diff > 0:
                                change_text = f'↑{diff:.2f}%'
                                change_class = 'change-up'
                            elif diff < -0.3:
                                change_text = f'减仓 {abs(diff):.2f}%'
                                change_class = 'change-sub'
                            else:
                                change_text = f'↓{abs(diff):.2f}%'
                                change_class = 'change-down'
                        else:
                            change_text = '新增'
                            change_class = 'change-new'
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

        holder_data = r.get("holder_struct")
        if holder_data and ("inst" in holder_data) and ("indiv" in holder_data):
            inst_r = holder_data["inst"]
            indiv_r = holder_data["indiv"]
            h_date = holder_data.get("date", "--")
            pie_card_html = f"""
            <div class="quarter-card holder-card">
                <div class="quarter-label">
                    <span class="quarter-title">持有人结构</span>
                </div>
                <div class="holder-pie-wrapper">
                    <canvas id="holder-chart-{r['code']}" data-inst="{inst_r}" data-indiv="{indiv_r}"></canvas>
                </div>
                <div class="holder-date-sub">披露日期: {h_date}</div>
            </div>
            """
        else:
            pie_card_html = f"""
            <div class="quarter-card holder-card">
                <div class="quarter-label">
                    <span class="quarter-title">持有人结构</span>
                </div>
                <div style="flex:1; display:flex; align-items:center; justify-content:center; color:var(--footer-text); font-size:11px;">
                    暂无结构数据
                </div>
                <div class="holder-date-sub">披露日期: --</div>
            </div>
            """

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

        rows_html += f"""
        <tr class="holding-row" data-code="{r['code']}">
            <td colspan="{col_count}" style="padding: 8px 20px; background-color: var(--hover-bg); font-size: 12px; color: var(--footer-text);">
                <div class="holdings-wrapper">
                    <div class="holdings-container">
                        {holdings_html}
                        {pie_card_html}
                    </div>
                    {chart_html}
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
    friend_cards_html = ""
    for link in friend_links:
        friend_cards_html += f"""
        <div class="friend-card">
            <a href="{link['url']}" target="_blank">{link['name']}</a>
            <span class="friend-desc">{link['desc']}</span>
        </div>
        """

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

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        
        /* 顶部通栏主导航 */
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
        .nav-tab-btn:hover {{
            background: var(--hover-bg);
            color: var(--link-color);
        }}
        .nav-tab-btn.active {{
            background: var(--btn-active-bg);
            color: #fff;
        }}
        .nav-right-tools {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .theme-toggle {{
            background: var(--header-bg);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 4px 10px;
            font-size: 11px;
            cursor: pointer;
        }}

        /* 内容视图包裹器 */
        .views-container {{
            flex: 1;
            min-height: 0;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 12px 20px;
        }}
        .view-pane {{
            display: none;
            flex-direction: column;
            height: 100%;
            min-height: 0;
        }}
        .view-pane.active {{
            display: flex;
        }}

        /* 首页视图样式 */
        .home-container {{
            flex: 1;
            overflow-y: auto;
            padding-right: 6px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .home-banner {{
            background: var(--table-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 22px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
        }}
        .home-banner-left h2 {{
            margin: 0 0 6px 0;
            color: var(--link-color);
            font-size: 20px;
        }}
        .home-banner-left p {{
            margin: 0;
            color: var(--footer-text);
            font-size: 12px;
            line-height: 1.5;
        }}

        /* 恐慌指数紧凑型卡片 */
        .fng-compact-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            gap: 14px;
            flex-shrink: 0;
        }}
        .fng-gauge-box {{
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .fng-score-badge {{
            font-size: 24px;
            font-weight: 800;
            font-family: "SFMono-Regular", Consolas, monospace;
            line-height: 1;
            margin-bottom: 2px;
        }}
        .fng-rating-text {{
            font-size: 11px;
            font-weight: 600;
            text-transform: capitalize;
        }}
        .fng-desc-box {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-width: 380px;
            border-left: 1px dashed var(--border);
            padding-left: 14px;
        }}
        .fng-header-line {{
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            font-weight: bold;
            color: var(--header-text);
        }}
        .fng-bar-track {{
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
            position: relative;
            background: linear-gradient(to right, #d93025, #ea8600, #fbbc04, #34a853, #188038);
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
        .fng-range-legend {{
            display: flex;
            justify-content: space-between;
            font-size: 9px;
            color: var(--footer-text);
            margin-top: 1px;
        }}

        /* 首页后续扩展占位区 */
        .home-grid-section {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 14px;
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
        .home-card-body {{
            font-size: 12px;
            color: var(--footer-text);
            line-height: 1.6;
        }}

        /* 基金列表子导航与筛选栏 */
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
        .category-nav {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .category-title {{
            font-size: 11px;
            font-weight: 700;
            color: var(--footer-text);
            margin-right: 4px;
        }}
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
        .cat-btn:hover {{
            background: var(--btn-active-bg);
            color: var(--btn-active-text);
        }}
        .cat-btn.active {{
            background: var(--btn-active-bg);
            color: var(--btn-active-text);
            border-color: var(--btn-active-bg);
        }}
        .search-box-wrap {{
            width: 260px;
            flex-shrink: 0;
        }}
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

        /* 表格排版 */
        .table-container {{ 
            width: 100%; 
            flex: 1 1 0; 
            min-height: 0; 
            overflow-y: auto; 
            overflow-x: auto; 
            box-sizing: border-box; 
            background: var(--table-bg);
            border-radius: 10px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.06); 
            padding: 8px; 
            border: 1px solid var(--border);
            margin-bottom: 6px;
        }}
        table {{ 
            width: 100%; 
            min-width: 2400px; 
            border-collapse: collapse; 
            font-size: 12px; 
            text-align: right; 
            table-layout: fixed; 
        }}
        th, td {{ 
            padding: 6px 8px; 
            border-bottom: 1px solid var(--border);
            line-height: 1.4; 
            overflow: hidden; 
            text-overflow: ellipsis; 
            box-sizing: border-box; 
        }}
        #fundTable thead th {{
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: var(--header-bg);
            border-bottom: 2px solid var(--border);
        }}
        th:nth-child(1), td:nth-child(1) {{ width: 60px; text-align: left; white-space: nowrap; }}
        th:nth-child(2), td:nth-child(2) {{ width: 250px; min-width: 200px; text-align: left; white-space: normal; word-break: break-word; vertical-align: middle; }}
        th:nth-child(3), td:nth-child(3) {{ width: 80px; text-align: left; white-space: nowrap; }}
        th:nth-child(4), td:nth-child(4) {{ width: 130px; text-align: left; white-space: normal; word-break: break-word; }}
        th:nth-child(5), td:nth-child(5) {{ width: 70px; text-align: left; white-space: nowrap; }}
        th:nth-child(6), td:nth-child(6) {{ width: 100px; text-align: left; white-space: nowrap; }}
        th:nth-child(7), td:nth-child(7),
        th:nth-child(8), td:nth-child(8) {{ width: 128px; white-space: nowrap; }}
        th:nth-child(9), td:nth-child(9) {{ width: 85px; white-space: nowrap; }}
        th:nth-child(10), td:nth-child(10),
        th:nth-child(11), td:nth-child(11),
        th:nth-child(12), td:nth-child(12) {{ width: 300px; white-space: nowrap; }}
        th:nth-child(13), td:nth-child(13) {{ width: 80px; white-space: nowrap; }}
        th:nth-child(14), td:nth-child(14) {{ width: 155px; min-width: 90px; white-space: normal; }}
        th:nth-child(15), td:nth-child(15),
        th:nth-child(16), td:nth-child(16),
        th:nth-child(17), td:nth-child(17),
        th:nth-child(18), td:nth-child(18),
        th:nth-child(19), td:nth-child(19),
        th:nth-child(20), td:nth-child(20) {{ width: 80px; white-space: nowrap; }}
        th {{ 
            background-color: var(--header-bg);
            color: var(--header-text);
            font-weight: 600; 
            text-align: right; 
            user-select: none; 
            cursor: pointer; 
            white-space: normal;
            word-break: keep-all;
            line-height: 1.25;
            height: 38px;
            vertical-align: middle;
            position: relative; 
        }}
        th:hover {{ background-color: #e4e7eb; }}
        [data-theme="dark"] th:hover {{ background-color: #3d3d3d; }}
        th:nth-child(1), th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5), th:nth-child(6) {{ text-align: left; }}
        tr:hover {{ background-color: var(--hover-bg); }}
        
        .code {{ font-family: "SFMono-Regular", Consolas, monospace; font-weight: bold; color: #1a73e8; }}
        .name a {{ font-weight: 500; color: #1a73e8; text-decoration: none; }}
        .redemption-sub {{ font-size: 10px; color: var(--footer-text); margin-top: 2px; }}
        .highlight-rate {{ color: #d93025; font-weight: bold; }}
        .highlight-val {{ font-weight: 600; color: #e67e22; }}
        .fee-sub {{ font-size: 10px; color: var(--footer-text); }}

        .progress-container {{
            background-color: var(--progress-track);
            border-radius: 6px;
            overflow: hidden;
            height: 20px;
            width: 100%;
            position: relative;
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
        }}
        .progress-bar span {{
            color: #fff;
            font-size: 11px;
            font-weight: 600;
        }}
        .bar-red {{ background-color: #d93025; }}
        .bar-blue {{ background-color: #1a73e8; }}
        .bar-green {{ background-color: #188038; }}
        .metric-red {{ color: #d93025; font-weight: 600; }}
        .metric-green {{ color: #188038; font-weight: 600; }}
        .gain-positive {{ color: #d93025; font-weight: bold; }}
        .gain-negative {{ color: #188038; font-weight: bold; }}
        .gain-date {{ font-size: 10px; color: var(--footer-text); }}

        /* 折叠持仓卡片排版 */
        .fund-row {{ cursor: pointer; }}
        .holding-row td {{
            background-color: var(--hover-bg) !important;
            border-top: 1px dashed var(--border);
        }}
        .holding-row {{ display: none; }}
        .holding-row.show {{ display: table-row; }}
        .holdings-wrapper {{
            display: flex;
            flex-wrap: nowrap;
            gap: 16px;
            align-items: stretch;
            width: 100%;
        }}
        .holdings-container {{
            flex: 0 0 calc(50% - 8px);
            width: calc(50% - 8px);
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            align-items: stretch;
            min-width: 0;
        }}
        .quarter-card {{
            min-width: 0;
            background: var(--card-bg);
            border-radius: 8px;
            padding: 10px 8px;
            box-shadow: var(--card-shadow);
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
        }}
        .empty-holdings-placeholder {{ grid-column: span 3; }}
        .quarter-label {{
            font-weight: bold;
            font-size: 12px;
            margin-bottom: 8px;
            color: var(--header-text);
            border-bottom: 1px solid var(--border);
            padding-bottom: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .quarter-title {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .quarter-end {{ font-size: 10px; color: var(--footer-text); }}
        .quarter-stocks {{ display: flex; flex-direction: column; gap: 4px; flex: 1; }}
        .stock-item {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 50px 56px;
            gap: 3px;
            font-size: 11px;
            align-items: center;
        }}
        .stock-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .stock-ratio {{ text-align: right; font-weight: 500; }}
        .stock-change {{ text-align: right; font-size: 10px; white-space: nowrap; }}
        .change-add {{ color: #d93025; }}
        .change-sub {{ color: #188038; }}
        .change-up {{ color: #d93025; }}
        .change-down {{ color: #188038; }}
        .change-new {{ color: #1a73e8; }}
        .stock-total {{
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px dashed var(--border);
            font-weight: 600;
        }}
        .stock-total .stock-ratio {{ color: #e67e22; }}
        
        .holder-card {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .holder-pie-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            min-height: 140px;
            max-height: 180px;
        }}
        .holder-date-sub {{
            font-size: 10px;
            color: var(--footer-text);
            text-align: center;
            border-top: 1px dashed var(--border);
            padding-top: 6px;
            margin-top: 4px;
        }}

        .chart-container {{
            flex: 0 0 calc(50% - 8px);
            background: var(--card-bg);
            border-radius: 8px;
            padding: 10px;
            box-shadow: var(--card-shadow);
            display: flex;
            flex-direction: column;
            min-height: 200px;
        }}
        .chart-controls {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }}
        .chart-controls button {{
            background: var(--btn-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2px 10px;
            font-size: 11px;
            cursor: pointer;
            color: var(--btn-text);
        }}
        .chart-controls button.active {{
            background: var(--btn-active-bg);
            color: var(--btn-active-text);
        }}
        .chart-container canvas {{
            width: 100% !important;
            height: auto !important;
            max-height: 200px;
            flex: 1;
        }}
        
        .footer-note {{ 
            font-size: 11px; 
            color: var(--footer-text);
            background: var(--footer-bg);
            padding: 6px 12px; 
            border-radius: 6px; 
            border: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
    </style>
</head>
<body>
    <!-- 顶部主菜单导航栏 -->
    <header class="main-navbar">
        <div class="nav-brand">
            <span>📈 资产量化与策略看板</span>
        </div>
        <div class="nav-tabs-group">
            <button class="nav-tab-btn active" data-view="homeView">🏠 首页概览</button>
            <button class="nav-tab-btn" data-view="fundView">📊 基金量化看板</button>
        </div>
        <div class="nav-right-tools">
            <button class="theme-toggle" id="themeToggle">🌓 切换主题</button>
        </div>
    </header>

    <!-- 主体视图区 -->
    <main class="views-container">
        
        <!-- 视图 1：首页 -->
        <section id="homeView" class="view-pane active">
            <div class="home-container">
                <!-- 头部 Banner 与紧凑恐慌指数卡片 -->
                <div class="home-banner">
                    <div class="home-banner-left">
                        <h2>宏观全景与市场情绪</h2>
                        <p>监控全球主要市场流动性、跨资产表现与市场恐慌贪婪程度，为仓位攻防提供科学的量化依据。</p>
                    </div>
                    
                    <!-- 恐慌指数紧凑组件 -->
                    <div class="fng-compact-card">
                        <div class="fng-gauge-box">
                            <div class="fng-score-badge" id="fngScore">--</div>
                            <div class="fng-rating-text" id="fngRating">--</div>
                        </div>
                        <div class="fng-desc-box">
                            <div class="fng-header-line">
                                <span>市场情绪 (Fear & Greed)</span>
                                <span style="font-weight:normal; font-size:10px; color:var(--footer-text);" id="fngDate">--</span>
                            </div>
                            <div class="fng-bar-track">
                                <div class="fng-bar-pointer" id="fngPointer" style="left: 50%;"></div>
                            </div>
                            <div class="fng-range-legend">
                                <span style="color:#d93025;">0 极度恐慌</span>
                                <span style="color:#ea8600;">恐慌</span>
                                <span style="color:#fbbc04;">中性</span>
                                <span style="color:#34a853;">贪婪</span>
                                <span style="color:#188038;">100 极度贪婪</span>
                            </div>
                            <div style="font-size:10px; color:var(--footer-text); margin-top:2px;">
                                💡 <strong>指标含义：</strong> 0~25 极恐(往往孕育买点) | 26~45 谨慎 | 46~54 中性 | 55~75 贪婪 | 76~100 亢奋极贪(注意风控)
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 首页后续内容预留区 -->
                <div class="home-grid-section">
                    <div class="home-card-box">
                        <div class="home-card-title">
                            <span>📌 策略速览与投资备忘</span>
                            <span style="font-size:11px; font-weight:normal; color:var(--link-color);">后续持续扩展</span>
                        </div>
                        <div class="home-card-body">
                            <p>• <strong>资产分层配置：</strong> 建议维持海外核心指数资产底仓，同时通过网格及定投工具平滑A股科技与周期板块的波动。</p>
                            <p>• <strong>恐慌指数运用：</strong> 当市场处于极端恐慌区间时，逐步加大定投资金比例；处于极度贪婪时，分批兑现浮盈。</p>
                            <div style="padding: 20px; text-align: center; background: var(--hover-bg); border-radius: 8px; margin-top: 10px; border: 1px dashed var(--border);">
                                💡 首页后续内容扩充区域（可扩展：大盘估值雷达、资金动向、重要财经日历）
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
            <!-- 顶部多级分类菜单栏 (美股、A股、其他) -->
            <div class="sub-filter-bar">
                <div class="category-nav">
                    <span class="category-title">市场大类:</span>
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

            <!-- 数据表格 -->
            <div class="table-container">
                <table id="fundTable">
                    <thead>
                        <tr>
                            <th data-col="0" onclick="sortTable(0)">代码 <span class="sort-icon">⇅</span></th>
                            <th data-col="1" onclick="sortTable(1)">基金名称 / 赎回费率阶梯 <span class="sort-icon">⇅</span></th>
                            <th data-col="2" onclick="sortTable(2)">最新规模 <span class="sort-icon">⇅</span></th>
                            <th data-col="3" onclick="sortTable(3)">运作费(管/托/销) <span class="sort-icon">⇅</span></th>
                            <th data-col="4" onclick="sortTable(4)">申购费率 <span class="sort-icon">⇅</span></th>
                            <th data-col="5" onclick="sortTable(5)">申购状态/限额 <span class="sort-icon">⇅</span></th>
                            <th data-col="6" onclick="sortTable(6)">最高净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="7" onclick="sortTable(7)">最低净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="8" onclick="sortTable(8)">最新净值 <span class="sort-icon">⇅</span></th>
                            <th data-col="9" onclick="sortTable(9)">最大回撤 <span class="sort-icon">⇅</span></th>
                            <th data-col="10" onclick="sortTable(10)">自低点反弹 <span class="sort-icon">⇅</span></th>
                            <th data-col="11" onclick="sortTable(11)">修复程度 <span class="sort-icon">⇅</span></th>
                            <th data-col="12" onclick="sortTable(12)">修复时间 <span class="sort-icon">⇅</span></th>
                            <th data-col="13" onclick="sortTable(13)">{col_today_title} <span class="sort-icon">⇅</span></th>
                            <th data-col="14" onclick="sortTable(14)">近一周 <span class="sort-icon">⇅</span></th>
                            <th data-col="15" onclick="sortTable(15)">近一月 <span class="sort-icon">⇅</span></th>
                            <th data-col="16" onclick="sortTable(16)">近三月 <span class="sort-icon">⇅</span></th>
                            <th data-col="17" onclick="sortTable(17)">近半年 <span class="sort-icon">⇅</span></th>
                            <th data-col="18" onclick="sortTable(18)">近一年 <span class="sort-icon">⇅</span></th>
                            <th data-col="19" onclick="sortTable(19)">今年内 <span class="sort-icon">⇅</span></th>
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
                    <span>💡 <strong>使用提示：</strong> 表格支持列宽自由拖拽与表头排序；点击基金数据行可展开查看前十大持仓、持有人结构及走势图。</span>
                </div>
                <div class="footer-right">
                    <span>⏱️ 统计更新于: <strong>{update_time_str}</strong></span>
                </div>
            </div>
        </section>
    </main>

    <script>
        var fundNavData = {json.dumps(nav_data_json, ensure_ascii=False)};
        var fngData = {json.dumps(fear_greed_info, ensure_ascii=False)};

        // 1. 初始化恐慌指数
        (function() {{
            const scoreElem = document.getElementById('fngScore');
            const ratingElem = document.getElementById('fngRating');
            const dateElem = document.getElementById('fngDate');
            const pointerElem = document.getElementById('fngPointer');
            if (fngData && scoreElem) {{
                const val = fngData.score;
                scoreElem.innerText = val;
                ratingElem.innerText = fngData.rating;
                dateElem.innerText = fngData.date + ' (' + fngData.source + ')';
                pointerElem.style.left = val + '%';
                
                // 情绪色彩
                let color = '#fbbc04';
                if (val <= 25) color = '#d93025';
                else if (val <= 45) color = '#ea8600';
                else if (val >= 75) color = '#188038';
                else if (val >= 55) color = '#34a853';
                scoreElem.style.color = color;
                ratingElem.style.color = color;
            }}
        }})();

        // 2. 主导航切换 (首页 vs 看板)
        document.querySelectorAll('.nav-tab-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
                this.classList.add('active');
                const targetView = document.getElementById(this.dataset.view);
                if (targetView) targetView.classList.add('active');
            }});
        }});

        // 3. 亮暗主题切换
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

        // 4. 多级标签与搜索筛选逻辑
        document.addEventListener('DOMContentLoaded', function() {{
            const catBtns = document.querySelectorAll('.cat-btn');
            const searchInput = document.getElementById('searchInput');
            const emptyRow = document.getElementById('empty-row');
            const allRows = document.querySelectorAll('#fundTable tbody tr:not(#empty-row)');
            let currentMacro = 'all';
            let currentSub = 'all';
            let searchKeyword = '';

            function applyFilters() {{
                let hasVisible = false;
                const keyword = searchKeyword.trim().toLowerCase();

                allRows.forEach(row => {{
                    if (row.classList.contains('holding-row')) return;
                    const macro = row.getAttribute('data-macro');
                    const sub = row.getAttribute('data-group');
                    const nameCell = row.querySelector('.name a');
                    const name = nameCell ? nameCell.textContent.toLowerCase() : '';
                    const codeCell = row.querySelector('.code');
                    const code = codeCell ? codeCell.textContent.toLowerCase() : '';

                    let matchCategory = false;
                    if (currentMacro === 'all') {{
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
                        emptyRow.querySelector('td').textContent = keyword ? '未找到匹配基金' : '当前分类暂无数据';
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

        // 5. 原生饼图绘制插件与走势图渲染
        var chartInstances = {{}};
        var holderChartInstances = {{}};
        
        const pieLabelsPlugin = {{
            id: 'pieLabels',
            afterDraw(chart) {{
                if (chart.config.type !== 'pie') return;
                const ctx = chart.ctx;
                chart.data.datasets.forEach((dataset, i) => {{
                    const meta = chart.getDatasetMeta(i);
                    meta.data.forEach((element, index) => {{
                        const val = dataset.data[index];
                        if (val <= 6) return;
                        const {{ x, y }} = element.tooltipPosition();
                        ctx.save();
                        ctx.fillStyle = '#ffffff';
                        ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.shadowColor = 'rgba(0, 0, 0, 0.45)';
                        ctx.shadowBlur = 3;
                        ctx.fillText(`${{val.toFixed(1)}}%`, x, y);
                        ctx.restore();
                    }});
                }});
            }}
        }};
        Chart.register(pieLabelsPlugin);

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
            const inst = parseFloat(canvas.getAttribute('data-inst'));
            const indiv = parseFloat(canvas.getAttribute('data-indiv'));
            if (isNaN(inst) || isNaN(indiv)) return;

            const ctx = canvas.getContext('2d');
            holderChartInstances[code] = new Chart(ctx, {{
                type: 'pie',
                data: {{
                    labels: ['机构持有', '个人持有'],
                    datasets: [{{
                        data: [inst, indiv],
                        backgroundColor: ['#1a73e8', '#e67e22'],
                        borderColor: 'transparent',
                        borderWidth: 0
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'bottom',
                            labels: {{
                                font: {{ size: 10 }},
                                boxWidth: 10,
                                padding: 6,
                                color: getComputedStyle(document.documentElement).getPropertyValue('--text').trim() || '#333',
                                generateLabels: function(chart) {{
                                    const data = chart.data;
                                    if (data.labels.length && data.datasets.length) {{
                                        return data.labels.map((label, i) => {{
                                            const val = data.datasets[0].data[i];
                                            return {{
                                                text: `${{label}}: ${{val.toFixed(2)}}%`,
                                                fillStyle: data.datasets[0].backgroundColor[i],
                                                strokeStyle: 'transparent',
                                                lineWidth: 0,
                                                index: i
                                            }};
                                        }});
                                    }}
                                    return [];
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
                }} else return;
            }}
            const data = fundNavData[code];
            if (!data || !data.dates || data.dates.length === 0) return;
            const filtered = filterNavData(data, 'month');
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
                        fill: true,
                        tension: 0.1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }}
                }}
            }});
            chartInstances[code] = chart;
        }}

        // 点击展开折叠
        document.addEventListener('DOMContentLoaded', function() {{
            const table = document.getElementById('fundTable');
            table.addEventListener('click', function(e) {{
                const target = e.target.closest('tr.fund-row');
                if (!target || e.target.tagName === 'A') return;
                const code = target.dataset.code;
                const hRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                if (hRow) {{
                    hRow.classList.toggle('show');
                    if (hRow.classList.contains('show')) {{
                        hRow.style.display = '';
                        setTimeout(() => {{
                            initChart(code);
                            initHolderChart(code);
                        }}, 50);
                    }} else {{
                        hRow.style.display = 'none';
                    }}
                }}
            }});
        }});

        // 表格基础排序
        let currentSortCol = -1;
        let isAscending = true;
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
        }}
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
        except Exception:
            pass

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
                if nav > 0:
                    data.append({"date": d_str, "nav": nav})
    except Exception:
        data = []

    if data:
        data = sorted(data, key=lambda x: x['date'])
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'start_date': start_date, 'end_date': end_date, 'data': data}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
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
        except Exception:
            pass

    df = None
    data = []
    try:
        if symbol == "AUM":
            df = ak.futures_main_sina(symbol="AU0")
        elif symbol == "XAU":
            for sym in ["GC", "XAU"]:
                try:
                    df = ak.futures_foreign_hist(symbol=sym)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
        elif symbol == "XAG":
            for sym in ["SI", "XAG"]:
                try:
                    df = ak.futures_foreign_hist(symbol=sym)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue

        if df is not None and not df.empty:
            d_col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            c_col = '收盘价' if '收盘价' in df.columns else ('close' if 'close' in df.columns else df.columns[4])
            df[d_col] = pd.to_datetime(df[d_col]).dt.strftime('%Y-%m-%d')
            df = df[(df[d_col] >= start_date) & (df[d_col] <= end_date)].sort_values(d_col)
            for _, row in df.iterrows():
                try:
                    nav = float(row[c_col])
                    if nav > 0:
                        data.append({"date": str(row[d_col]), "nav": nav})
                except Exception:
                    continue

        if data:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'start_date': start_date, 'end_date': end_date, 'data': data}, f, ensure_ascii=False, indent=2)
            return data
    except Exception:
        pass
    return None

def fetch_index_data(symbol, start_date, end_date):
    df = None
    close_col = None
    date_col = None

    try:
        if symbol in SINA_INDEX_MAP:
            sina_symbol = SINA_INDEX_MAP[symbol]
            df = ak.index_us_stock_sina(symbol=sina_symbol)
            if df is not None and not df.empty:
                date_col = 'date' if 'date' in df.columns else df.columns[0]
                close_col = 'close' if 'close' in df.columns else None
                if close_col is None:
                    for c in df.columns:
                        if 'close' in str(c).lower() or '收盘' in str(c):
                            close_col = c
                            break
                if close_col is None:
                    close_col = df.columns[4] if len(df.columns) > 4 else df.columns[-1]

        elif symbol == "SOXL":
            for try_symbol in ["105.SOXL", "SOXL", "106.SOXL"]:
                try:
                    df = ak.stock_us_hist(symbol=try_symbol, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""), adjust="")
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue

            if df is not None and not df.empty:
                date_col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
                close_col = '收盘' if '收盘' in df.columns else ('close' if 'close' in df.columns else None)
                if close_col is None:
                    for c in df.columns:
                        if 'close' in str(c).lower() or '收盘' in str(c):
                            close_col = c
                            break

        elif symbol == "SOXX":
            for try_symbol in ["105.SOXX", "SOXX", "106.SOXX"]:
                try:
                    df = ak.stock_us_hist(symbol=try_symbol, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""), adjust="")
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue

            if df is not None and not df.empty:
                date_col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
                close_col = '收盘' if '收盘' in df.columns else ('close' if 'close' in df.columns else None)
                if close_col is None:
                    for c in df.columns:
                        if 'close' in str(c).lower() or '收盘' in str(c):
                            close_col = c
                            break

        if df is None or df.empty:
            return None

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df['date_str'] = df[date_col].dt.strftime('%Y-%m-%d')
        mask = (df['date_str'] >= start_date) & (df['date_str'] <= end_date)
        df = df.loc[mask].sort_values('date_str')

        if df.empty:
            return None

        data = []
        for _, row in df.iterrows():
            try:
                nav = float(row[close_col])
                if nav > 0:
                    data.append({"date": row['date_str'], "nav": nav})
            except (ValueError, TypeError):
                continue
        return data if data else None
    except Exception:
        return None

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_start = "2025-01-01"
    cutoff_date = "2026-04-01"

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default=default_start)
    parser.add_argument("--end", type=str, default=today_str)
    parser.add_argument("--funds", nargs="+", default=DEFAULT_FUNDS)
    parser.add_argument("--out", type=str, default="fund_drawdown_dashboard.html")

    args = parser.parse_args()
    opener = get_direct_opener()

    print(f"\n======== 开始抓取数据 ========")
    print(f"统计区间: {args.start} 至 {args.end}")
    
    # 抓取市场情绪/恐慌指数
    fear_greed_info = fetch_fear_and_greed_index(opener)
    print(f"📊 恐慌贪婪指数获取成功: {fear_greed_info['score']} ({fear_greed_info['rating']})")

    results = []
    for idx, code in enumerate(args.funds, start=1):
        meta = fetch_fund_detail_meta(opener, code)
        raw_data = fetch_from_eastmoney(opener, code, args.start, args.end)
        if not raw_data:
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ❌ 历史净值抓取失败")
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
                "source": "天天基金",
                "nav_data": raw_data_sorted
            })
            results.append(res)
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ✅ 完成")
        time.sleep(random.uniform(0.05, 0.1))

    # 获取其他标的数据
    for symbol in PRECIOUS_METALS_SYMBOLS:
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
                        "holder_struct": None, "source": "贵金属行情", "nav_data": data
                    })
                    results.append(res)
        except Exception:
            pass

    for symbol in CRYPTO_SYMBOLS:
        try:
            data = fetch_crypto_data(symbol, args.start, args.end)
            if data:
                meta_name = CRYPTO_NAMES.get(symbol, symbol)
                res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
                if res:
                    res.update({
                        "code": symbol, "name": meta_name, "scale": "--", "scale_val": -1.0,
                        "fee_manage": "--", "fee_custody": "--", "fee_sales": "--", "fee_source": "--",
                        "fee_purchase": "--", "fee_redemption": "--", "buy_status": "--", "buy_limit": "--",
                        "buy_limit_val": -1, "fee_total": "--", "fee_val": -1.0, "holdings": [],
                        "holder_struct": None, "source": "现货行情", "nav_data": data
                    })
                    results.append(res)
        except Exception:
            pass

    for symbol in INDEX_SYMBOLS:
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
                        "holder_struct": None, "source": "指数行情", "nav_data": data
                    })
                    results.append(res)
        except Exception:
            pass

    if results:
        abs_path = generate_html_report(results, args.start, args.end, today_str, fear_greed_info, filename=args.out)
        print(f"\n🎉 升级版网页生成成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass

if __name__ == "__main__":
    main()