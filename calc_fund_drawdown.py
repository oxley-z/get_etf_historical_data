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
    # QDII组
    "002891", "014002", "006555", "012922", "012920", "021662", "457001", "539002",
    "018147", "021842", "006373", "018036", "501226", "008254", "008253", "017731",
    "017730", "016665", "016664", "018230", "018229", "021277", "270023", "005698",
    "024239", "501312", "017204", "017654", "017653", "022184", "100055", "017437",
    "017436", "017145", "017144", "016702", "016701", "016823", "164212", "019156",
    "019155", "016668", "501225", "015202", "001668", "000043", "007280", "019449",
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

QDII_CODES = {
    "002891", "014002", "006555", "012922", "012920", "021662", "457001", "539002",
    "018147", "021842", "006373", "018036", "501226", "008254", "008253", "017731",
    "017730", "016665", "016664", "018230", "018229", "021277", "270023", "005698",
    "024239", "501312", "017204", "017654", "017653", "022184", "100055", "017437",
    "017436", "017145", "017144", "016702", "016701", "016823", "164212", "019156",
    "019155", "016668", "501225", "015202", "001668", "000043", "007280", "019449"
}

# 指数组
INDEX_SYMBOLS = ["NDX", "SPX", "SOXX", "SOXL"]
INDEX_NAMES = {
    "NDX": "纳斯达克100指数",
    "SPX": "标普500指数",
    "SOXX": "iShares 半导体ETF",
    "SOXL": "三倍做多半导体ETF-Direxion"
}

# 贵金属组
PRECIOUS_METALS_SYMBOLS = ["XAU", "AUM", "XAG"]
PRECIOUS_METALS_NAMES = {
    "XAU": "伦敦金 (XAU)",
    "AUM": "黄金连续 (AUM)",
    "XAG": "伦敦银 (XAG)"
}

# 加密货币组
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

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(HOLDINGS_CACHE_DIR, exist_ok=True)
os.makedirs(NAV_CACHE_DIR, exist_ok=True)

def get_direct_opener():
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

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

            quarters = sorted(combined['季度'].unique(), reverse=True)[:4]
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
        "fee_purchase": "0.00%",
        "fee_redemption": "未知",
        "buy_status": "--",
        "buy_limit": "无限额",
        "buy_limit_val": -1,
        "fee_total": "未知",
        "fee_val": -1.0,
        "holdings": []
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

        if meta["fee_purchase"] == "0.00%":
            buy_m = re.search(r'var\s+fund_sourceRate\s*=\s*"([^"]+)";', js_content)
            if buy_m:
                meta["fee_purchase"] = buy_m.group(1)

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

def get_nav_at_date(data, target_date_str):
    if not data:
        return None
    target = datetime.strptime(target_date_str, '%Y-%m-%d')
    best = None
    for item in data:
        dt = datetime.strptime(item['date'], '%Y-%m-%d')
        if dt <= target:
            best = item['nav']
        else:
            break
    return best

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

    def calc_gain(days):
        target_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
        nav_before = get_nav_at_date(data_all, target_date)
        if nav_before is not None and nav_before > 0:
            return ((latest_nav / nav_before) - 1) * 100.0
        return None

    week_gain = calc_gain(7)
    month_gain = calc_gain(30)
    quarter_gain = calc_gain(90)
    half_year_gain = calc_gain(180)
    year_gain = calc_gain(365)

    year_start = datetime.strptime(end_date, '%Y-%m-%d').replace(month=1, day=1).strftime('%Y-%m-%d')
    nav_ytd = get_nav_at_date(data_all, year_start)
    if nav_ytd is not None and nav_ytd > 0:
        ytd_gain = ((latest_nav / nav_ytd) - 1) * 100.0
    else:
        ytd_gain = None

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

def generate_html_report(results, start_date, end_date, today_str, filename="fund_drawdown_dashboard.html"):
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

        if r['code'] in CPO_CODES:
            group = "cpo"
        elif r['code'] in STORAGE_CODES:
            group = "storage"
        elif r['code'] in SEMICONDUCTOR_CODES:
            group = "semiconductor"
        elif r['code'] in AI_CODES:
            group = "ai"
        elif r['code'] in GRID_CODES:
            group = "grid"
        elif r['code'] in ROBOT_CODES:
            group = "robot"
        elif r['code'] in PRECIOUS_METALS_LOCAL:
            group = "metals"
        elif r['code'] in CRYPTO_LOCAL:
            group = "crypto"
        elif r['code'] in INDEX_SET_LOCAL:
            group = "index"
        else:
            group = "qdii"
            
        # [需求优化] 如果是贵金属、加密货币或指数，最新净值高亮
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

        rows_html += f"""
        <tr data-group="{group}" class="fund-row" data-code="{r['code']}">
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
            <td data-val="{r['fee_purchase']}">{r['fee_purchase']}</td>
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
                    stocks_html = '<div style="color: var(--footer-text);">暂无持仓数据</div>'
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
            holdings_html = '<div>暂无持仓数据</div>'

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

    groups = [
        ("汇总", "all"),
        ("QDII", "qdii"),
        ("半导体材料设备", "semiconductor"),
        ("CPO", "cpo"),
        ("人工智能", "ai"),
        ("存储芯片", "storage"),
        ("电网设备", "grid"),
        ("机器人", "robot"),
        ("贵金属", "metals"),
        ("加密货币", "crypto"),
        ("指数", "index")
    ]
    buttons_html = ""
    for label, group_id in groups:
        buttons_html += f'<button class="group-btn" data-group="{group_id}">{label}</button>'

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
    <title>场外基金量化与费率规模看板（含多周期涨幅及走势图）</title>
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
            padding: 14px 20px; 
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            box-sizing: border-box;
            transition: background-color 0.3s, color 0.3s;
        }}
        .top-wrapper {{
            display:grid;
            grid-template-columns:minmax(0, 1fr) minmax(0, 1fr);
            gap:14px;
            height:220px;
            flex:0 0 220px;
            margin-bottom:10px;
            min-height:0;
        }}
        .top-left, .top-right {{
            min-width:0;
            min-height:0;
            border:1px solid var(--border);
            border-radius:12px;
            background:var(--table-bg);
            box-shadow:0 4px 15px rgba(0,0,0,0.07);
            box-sizing:border-box;
        }}
        .top-left {{
            padding:12px 14px;
            display:flex;
            flex-direction:column;
            overflow:hidden;
        }}
        .top-right {{
            padding:12px;
            display:flex;
            flex-direction:column;
            gap:8px;
            overflow:hidden;
        }}
        .theme-toggle {{
            align-self:flex-end;
            background:var(--header-bg);
            color:var(--text);
            border:1px solid var(--border);
            border-radius:18px;
            padding:3px 10px;
            font-size:11px;
            cursor:pointer;
            flex:0 0 auto;
        }}
        .theme-toggle:hover {{ opacity:0.82; }}
        .header {{ text-align:left; margin:0 0 6px 0; }}
        .header-top {{
            display:flex;
            align-items:center;
            margin-bottom:2px;
        }}
        .header-top h2 {{
            color:#1a73e8;
            margin:0;
            font-size:18px;
            line-height:1.2;
        }}
        .header p {{ color:var(--footer-text); font-size:11px; margin:2px 0; line-height:1.3; }}
        .header-info {{
            border:1px solid #e3e7eb;
            border-radius:6px;
            background:var(--hover-bg);
            padding:5px 8px;
            margin-bottom:6px;
            overflow:hidden;
            font-size:11px;
        }}
        .header-info p {{ margin:1px 0; }}
        .group-tabs {{
            display:grid;
            grid-template-columns:minmax(0,1fr) 230px;
            gap:8px;
            align-items:center;
            margin-top:auto;
            min-height:36px;
        }}
        .group-buttons {{
            display:flex;
            flex-wrap:wrap;
            gap:5px;
            align-content:center;
            min-width:0;
        }}
        .group-btn {{
            background:var(--btn-bg);
            color:var(--btn-text);
            border:1px solid var(--border);
            border-radius:16px;
            padding:3px 10px;
            font-size:11px;
            cursor:pointer;
            transition:all .2s;
            font-weight:500;
            white-space:nowrap;
        }}
        .group-btn:hover {{
            background:var(--btn-active-bg);
            color:var(--btn-active-text);
        }}
        .group-btn.active {{
            background:var(--btn-active-bg);
            color:var(--btn-active-text);
            border-color:var(--btn-active-bg);
        }}
        .search-container {{ width:100%; }}
        .search-container input {{
            width:100%;
            max-width:none;
            height:30px;
            padding:4px 12px;
            border-radius:16px;
            border:1px solid #35a853;
            background:var(--input-bg);
            color:var(--text);
            font-size:12px;
            outline:none;
            box-sizing:border-box;
            box-shadow:0 0 0 2px rgba(52,168,83,.08);
        }}
        .search-container input:focus {{ border-color:#188038; box-shadow:0 0 0 3px rgba(52,168,83,.14); }}
        .search-container input::placeholder {{ color:var(--footer-text); }}
        .friend-cards-wrapper {{
            display:grid;
            grid-template-columns:repeat(3,minmax(0,1fr));
            gap:8px;
            width:100%;
            min-height:0;
            flex:1;
        }}
        .friend-card {{
            min-width:0;
            min-height:64px;
            background:var(--card-bg);
            border-radius:6px;
            padding:8px 10px;
            box-shadow:var(--card-shadow);
            border:1px solid var(--border);
            box-sizing:border-box;
            overflow:hidden;
            transition:transform .12s, box-shadow .12s;
        }}
        .friend-card:hover {{
            transform:translateY(-1px);
            box-shadow:0 4px 12px rgba(0,0,0,.12);
        }}
        .friend-card a {{
            color:var(--link-color);
            text-decoration:none;
            font-weight:650;
            font-size:13px;
            display:block;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        }}
        .friend-card a:hover {{ text-decoration:underline; }}
        .friend-card .friend-desc {{
            font-size:10px;
            color:var(--footer-text);
            display:block;
            margin-top:3px;
            line-height:1.3;
            display:-webkit-box;
            -webkit-line-clamp:2;
            -webkit-box-orient:vertical;
            overflow:hidden;
        }}
        .table-container {{ 
            width:100%; 
            height: calc(100vh - 315px); 
            overflow-y: auto; 
            overflow-x: scroll; 
            box-sizing:border-box; 
            background: var(--table-bg);
            border-radius:12px; 
            box-shadow:0 4px 15px rgba(0,0,0,0.08); 
            padding:10px; 
            border:1px solid var(--border);
            flex: 1 1 auto;
            min-height: 0;
            margin-bottom: 8px;
            transition: background 0.3s, border-color 0.3s;
        }}
        .table-container::-webkit-scrollbar {{
            height: 12px;
            width: 8px;
        }}
        .table-container::-webkit-scrollbar-track {{
            background: var(--progress-track);
            border-radius: 6px;
        }}
        .table-container::-webkit-scrollbar-thumb {{
            background: #888;
            border-radius: 6px;
        }}
        .table-container::-webkit-scrollbar-thumb:hover {{
            background: #666;
        }}
        table {{ 
            width:100%; 
            min-width:2350px; 
            border-collapse:collapse; 
            font-size:12px; 
            text-align:right; 
            table-layout:fixed; 
        }}
        th, td {{ 
            padding:6px 8px; 
            border-bottom:1px solid var(--border);
            line-height:1.4; 
            overflow:hidden; 
            text-overflow:ellipsis; 
            box-sizing:border-box; 
            transition: border-color 0.3s;
        }}
        #fundTable thead th {{
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: var(--header-bg);
            border-bottom: 2px solid var(--border);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}
        [data-theme="dark"] #fundTable thead th {{
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
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
            transition: background-color 0.2s, color 0.2s; 
            white-space: normal;
            word-break: keep-all;
            overflow-wrap: anywhere;
            line-height: 1.25;
            height: 42px;
            min-height: 42px;
            vertical-align: middle;
            position: relative; 
        }}
        th:hover {{ background-color: #e4e7eb; }}
        [data-theme="dark"] th:hover {{ background-color: #3d3d3d; }}
        th:nth-child(1), th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5), th:nth-child(6) {{ text-align: left; }}
        tr:hover {{ background-color: var(--hover-bg); }}
        .resizer {{
            position: absolute; 
            right: 0; 
            top: 0; 
            bottom: 0; 
            width: 6px;
            cursor: col-resize; 
            user-select: none; 
            touch-action: none; 
            z-index: 10;
        }}
        .resizer:hover, th.resizing .resizer {{ background-color: #1a73e8; }}
        .sort-icon {{ font-size: 10px; margin-left: 2px; color: var(--footer-text); }}
        .code {{ font-family: "SFMono-Regular", Consolas, monospace; font-weight: bold; color: #1a73e8; }}
        .name a {{ 
            font-weight:500; 
            color:#1a73e8; 
            text-decoration:none; 
            display:inline-block; 
            max-width:100%; 
            overflow:hidden; 
            text-overflow:ellipsis; 
            vertical-align:middle; 
        }}
        .name a:hover {{ text-decoration: underline; color: #1557b0; }}
        
        /* 智能定投按钮样式 */
        .dca-btn {{
            background: #e8f0fe;
            color: #1a73e8;
            border: 1px solid #dadce0;
            border-radius: 12px;
            padding: 2px 6px;
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
        [data-theme="dark"] .dca-btn:hover {{
            background: #8ab4f8;
            color: #202124;
        }}

        .redemption-sub {{ 
            font-size: 10px; 
            color: var(--footer-text);
            font-weight: normal; 
            margin-top: 2px; 
        }}
        .highlight-rate {{
            color: #d93025;
            font-weight: bold;
        }}
        .highlight-val {{ font-weight: 600; color: #e67e22; }}
        .fee-sub {{ font-size: 10px; color: var(--footer-text); }}
        .progress-container {{
            background-color: var(--progress-track);
            border-radius:6px;
            overflow:hidden;
            height:20px;
            width:100%;
            position:relative;
            transition: background 0.3s;
        }}
        .progress-bar {{
            height:100%;
            border-radius:6px;
            min-width:42px;
            display:flex;
            align-items:center;
            justify-content:flex-end;
            padding-right:6px;
            box-sizing:border-box;
            transition:width .2s ease;
        }}
        .progress-bar span {{
            color:#fff;
            font-size:11px;
            font-weight:600;
            text-shadow:0 1px 1px rgba(0,0,0,.25);
        }}
        .bar-red {{ background-color:#d93025; }}
        .bar-blue {{ background-color:#1a73e8; }}
        .bar-green {{ background-color:#188038; }}
        .metric-red {{ color: #d93025; font-weight: 600; }}
        .metric-green {{ color: #188038; font-weight: 600; }}
        .gain-positive {{ color: #d93025; font-weight: bold; }}
        .gain-negative {{ color: #188038; font-weight: bold; }}
        .gain-date {{
            font-size: 10px;
            color: var(--footer-text);
            font-weight: normal;
        }}

        /* --- 新增：特定资产最新净值高亮样式 --- */
        .highlight-special-nav {{
            font-weight: bold;
            color: #d93025;
            background-color: rgba(217, 48, 37, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        [data-theme="dark"] .highlight-special-nav {{
            color: #ff8a65;
            background-color: rgba(255, 138, 101, 0.15);
        }}

        .fund-row {{ cursor: pointer; }}
        .fund-row .name a {{ pointer-events: auto; cursor: pointer; }}
        .holding-row td {{
            background-color: var(--hover-bg) !important;
            border-top: 1px dashed var(--border);
        }}
        .holding-row {{ display: none; }}
        .holding-row.show {{ display: table-row; }}
        .holdings-wrapper {{
            display: flex;
            flex-wrap: nowrap;
            gap: 20px;
            align-items: stretch;
            width: 100%;
        }}
        .holdings-container {{
            flex: 0 0 calc(50% - 10px);
            width: calc(50% - 10px);
            display: flex;
            flex-direction: row;
            gap: 10px;
            align-items: stretch;
            min-width: 0;
        }}
        .quarter-card {{
            flex: 1 1 0;
            min-width: 0;
            background: var(--card-bg);
            border-radius: 8px;
            padding: 10px 10px;
            box-shadow: var(--card-shadow);
            box-sizing: border-box;
            overflow: hidden;
        }}
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
            gap: 8px;
        }}
        .quarter-title {{
            flex: 1;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .quarter-end {{
            flex-shrink: 0;
            font-size: 10px;
            font-weight: 500;
            color: var(--footer-text);
            white-space: nowrap;
        }}
        .quarter-stocks {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .stock-item {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 54px 62px;
            gap: 4px;
            font-size: 11px;
            align-items: center;
        }}
        .stock-name {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-align: left;
        }}
        .stock-ratio {{
            text-align: right;
            font-weight: 500;
        }}
        .stock-change {{
            text-align: right;
            font-size: 10px;
            white-space: nowrap;
        }}
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
        .stock-total .stock-name {{
            color: var(--header-text);
        }}
        .stock-total .stock-ratio {{
            color: #e67e22;
            font-weight: 700;
        }}
        .chart-container {{
            flex: 0 0 calc(50% - 20px);
            background: var(--card-bg);
            border-radius: 8px;
            padding: 10px;
            box-shadow: var(--card-shadow);
            display: flex;
            flex-direction: column;
            min-height: 200px;
        }}
        .chart-controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-bottom: 6px;
        }}
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
            border-color: var(--btn-active-bg);
        }}
        .chart-container canvas {{
            width: 100% !important;
            height: auto !important;
            max-height: 200px;
            flex: 1;
        }}
        @media (max-width: 1000px) {{
            .holdings-wrapper {{ gap: 10px; }}
            .holdings-container {{ gap: 6px; }}
            .quarter-card {{ padding: 8px 6px; }}
            .stock-item {{
                grid-template-columns: minmax(0, 1fr) 48px 56px;
                font-size: 10px;
            }}
            .stock-change {{ font-size: 9px; }}
            .top-wrapper {{
                grid-template-columns:1fr;
                height:auto;
                flex-basis:auto;
            }}
            .top-left, .top-right {{ min-height:210px; }}
            .top-right {{ width:100%; }}
            .friend-cards-wrapper {{ width: 100%; }}
            .friend-card {{ min-height:64px; }}
            .group-tabs {{
                flex-direction: column;
                align-items: stretch;
            }}
            .search-container input {{ max-width: 100%; }}
        }}
        
        .footer-note {{ 
            margin-top: 0; 
            font-size: 11px; 
            color: var(--footer-text);
            line-height: 1.35; 
            background: var(--footer-bg);
            padding: 6px 12px; 
            border-radius: 6px; 
            border: 1px solid var(--border);
            flex-shrink: 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            box-sizing: border-box;
            transition: background 0.3s, color 0.3s, border-color 0.3s;
        }}
        .footer-left {{ flex: 1; min-width: 0; }}
        .footer-left p {{ margin: 1px 0; }}
        .footer-right {{
            flex-shrink: 0;
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 11px;
            font-weight: 500;
            color: var(--link-color);
            background: var(--hover-bg);
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid var(--border);
            white-space: nowrap;
        }}

        /* 定投弹窗样式 */
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
        .dca-field select:focus, .dca-field input:focus {{
            border-color: var(--link-color);
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
    </style>
</head>
<body>
    <div class="top-wrapper">
        <section class="top-left">
            <div class="header">
                <div class="header-top">
                    <h2>场外基金核心量化与全费率规模看板（含多周期涨幅及走势图）</h2>
                </div>
                <p>统计时间区间：<strong>{start_date}</strong> 至 <strong>{end_date}</strong>（包含基金数：{len(results)} 只）</p>
            </div>
            <div class="header-info">
                <p>申购费率已取优惠后费率，销售服务费默认0.00%，赎回费率百分比已高亮。</p>
                <p>最高/最低净值为回撤计算区间内峰值与谷值（谷值位于峰值之后）；涨幅基于完整历史净值计算。</p>
            </div>
            <div class="group-tabs">
                <div class="group-buttons">
                    {buttons_html}
                </div>
                <div class="search-container">
                    <input type="text" id="searchInput" placeholder="🔍 搜索基金名称或代码 ...">
                </div>
            </div>
        </section>
        <section class="top-right">
            <button class="theme-toggle" id="themeToggle">🌓 切换主题</button>
            <div class="friend-cards-wrapper">
                {friend_cards_html}
            </div>
        </section>
    </div>
    <div class="table-container">
        <table id="fundTable">
            <thead>
                <tr>
                    <th data-col="0">代码 <span class="sort-icon">⇅</span></th>
                    <th data-col="1">基金名称 / 赎回费率阶梯 <span class="sort-icon">⇅</span></th>
                    <th data-col="2">最新规模 <span class="sort-icon">⇅</span></th>
                    <th data-col="3">运作费(管/托/销) <span class="sort-icon">⇅</span></th>
                    <th data-col="4">申购费率 <span class="sort-icon">⇅</span></th>
                    <th data-col="5">申购状态/限额 <span class="sort-icon">⇅</span></th>
                    <th data-col="6">最高净值 <span class="sort-icon">⇅</span></th>
                    <th data-col="7">最低净值 <span class="sort-icon">⇅</span></th>
                    <th data-col="8">最新净值 <span class="sort-icon">⇅</span></th>
                    <th data-col="9">最大回撤 <span class="sort-icon">⇅</span></th>
                    <th data-col="10">自低点反弹 <span class="sort-icon">⇅</span></th>
                    <th data-col="11">修复程度 <span class="sort-icon">⇅</span></th>
                    <th data-col="12">修复时间 <span class="sort-icon">⇅</span></th>
                    <th data-col="13">{col_today_title} <span class="sort-icon">⇅</span></th>
                    <th data-col="14">近一周 <span class="sort-icon">⇅</span></th>
                    <th data-col="15">近一月 <span class="sort-icon">⇅</span></th>
                    <th data-col="16">近三月 <span class="sort-icon">⇅</span></th>
                    <th data-col="17">近半年 <span class="sort-icon">⇅</span></th>
                    <th data-col="18">近一年 <span class="sort-icon">⇅</span></th>
                    <th data-col="19">今年内 <span class="sort-icon">⇅</span></th>
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
            <p><strong>使用提示：</strong> 列宽可拖拽调整，点击表头排序。涨幅数据基于可获取的历史净值，若区间内无对应日期数据则显示“-”。</p>
            <p><span style="color: #1a73e8;">👉 点击基金行可展开/收起持仓与净值走势图；点击行内「📊 定投」可立即测算并回溯模拟定投收益。</span></p>
        </div>
        <div class="footer-right" title="静态页面生成与更新时间">
            <span>⏱️ 数据更新于: <strong>{update_time_str}</strong></span>
        </div>
    </div>

    <!-- 智能定投测算弹窗 -->
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
                            <option value="half">近半年</option>
                            <option value="year" selected>近一年</option>
                            <option value="ytd">今年以来</option>
                            <option value="all">全部历史序列</option>
                        </select>
                    </div>
                    <button class="dca-run-btn" id="dcaRunBtn">🚀 开始测算模拟收益</button>
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

        // 智能定投回测小工具交互与计算逻辑
        (function() {{
            let currentDcaCode = null;
            let dcaChartInstance = null;

            const modal = document.getElementById('dcaModal');
            const closeBtn = document.getElementById('closeDcaModal');
            const modalTitle = document.getElementById('dcaModalTitle');
            const freqSelect = document.getElementById('dcaFreq');
            const daySelect = document.getElementById('dcaDaySelect');
            const dayLabel = document.getElementById('dcaDayLabel');
            const dayField = document.getElementById('dcaDayField');
            const amountInput = document.getElementById('dcaAmount');
            const rangeSelect = document.getElementById('dcaRange');
            const runBtn = document.getElementById('dcaRunBtn');

            function populateDays(freq) {{
                daySelect.innerHTML = '';
                if (freq === 'daily') {{
                    dayField.style.display = 'none';
                }} else if (freq === 'weekly' || freq === 'biweekly') {{
                    dayField.style.display = 'flex';
                    dayLabel.textContent = freq === 'weekly' ? '扣款日 (每周几)' : '扣款日 (每两周周几)';
                    const weeks = ['周一', '周二', '周三', '周四', '周五'];
                    weeks.forEach((w, i) => {{
                        const opt = document.createElement('option');
                        opt.value = i + 1; // 1 to 5
                        opt.textContent = w;
                        if (i === 0) opt.selected = true;
                        daySelect.appendChild(opt);
                    }});
                }} else {{
                    dayField.style.display = 'flex';
                    dayLabel.textContent = '扣款日 (每月几号)';
                    for (let i = 1; i <= 28; i++) {{
                        const opt = document.createElement('option');
                        opt.value = i;
                        opt.textContent = i + ' 号';
                        if (i === 1) opt.selected = true;
                        daySelect.appendChild(opt);
                    }}
                }}
            }}

            populateDays('monthly');

            freqSelect.addEventListener('change', function() {{
                populateDays(this.value);
            }});

            // 打开弹窗
            window.openDcaModal = function(code) {{
                currentDcaCode = code;
                const name = fundNames[code] || code;
                modalTitle.textContent = `📊 定投测算: [${{code}}] ${{name}}`;
                modal.classList.add('show');
                runBacktest();
            }};

            closeBtn.addEventListener('click', function() {{
                modal.classList.remove('show');
            }});

            modal.addEventListener('click', function(e) {{
                if (e.target === modal) modal.classList.remove('show');
            }});

            runBtn.addEventListener('click', runBacktest);

            function runBacktest() {{
                if (!currentDcaCode || !fundNavData[currentDcaCode]) return;
                const raw = fundNavData[currentDcaCode];
                if (!raw.dates || raw.dates.length < 2) return;

                const freq = freqSelect.value;
                const targetDay = parseInt(daySelect.value) || 1;
                const perAmount = parseFloat(amountInput.value) || 1000;
                const range = rangeSelect.value;

                // 筛选回测时间区间
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

                if (filtered.length < 2) return;

                // 模拟扣款执行
                let totalInvest = 0;
                let totalShares = 0;
                let investCount = 0;
                let lastInvestKey = '';

                const timelineDates = [];
                const timelineCost = [];
                const timelineValue = [];

                filtered.forEach(item => {{
                    let shouldBuy = false;
                    const dayOfWeek = item.dt.getDay(); // 0 is Sun, 1-5 Mon-Fri
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

                // 渲染结果面板
                document.getElementById('resTotalInvest').innerHTML = `${{investCount}} 期 / <strong>${{totalInvest.toLocaleString()}}</strong> 元`;
                document.getElementById('resTotalAsset').innerHTML = `<strong>${{finalAsset.toFixed(2)}}</strong> 元`;
                
                const profitElem = document.getElementById('resProfit');
                profitElem.textContent = `${{profit >= 0 ? '+' : ''}}${{profit.toFixed(2)}}`;
                profitElem.style.color = profit >= 0 ? '#d93025' : '#188038';

                const rateElem = document.getElementById('resReturnRate');
                rateElem.textContent = `${{returnRate >= 0 ? '+' : ''}}${{returnRate.toFixed(2)}}%`;
                rateElem.style.color = returnRate >= 0 ? '#d93025' : '#188038';

                document.getElementById('resAvgPrice').innerHTML = `${{avgPrice.toFixed(4)}} / ${{latestItem.nav.toFixed(4)}}`;

                // 绘制/刷新曲线
                const ctx = document.getElementById('dcaChart').getContext('2d');
                if (dcaChartInstance) {{
                    dcaChartInstance.destroy();
                }}

                dcaChartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: timelineDates,
                        datasets: [
                            {{
                                label: '总资产 (元)',
                                data: timelineValue,
                                borderColor: '#1a73e8',
                                backgroundColor: 'rgba(26, 115, 232, 0.08)',
                                fill: true,
                                pointRadius: 0,
                                borderWidth: 2,
                                tension: 0.1
                            }},
                            {{
                                label: '累计本金 (元)',
                                data: timelineCost,
                                borderColor: '#e67e22',
                                borderDash: [4, 4],
                                pointRadius: 0,
                                borderWidth: 1.5,
                                fill: false
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {{ mode: 'index', intersect: false }},
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'top',
                                labels: {{ font: {{ size: 10 }}, boxWidth: 12 }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(ctx) {{
                                        return `${{ctx.dataset.label}}: ${{Number(ctx.parsed.y).toLocaleString()}} 元`;
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                ticks: {{ maxTicksLimit: 8, font: {{ size: 9 }} }},
                                grid: {{ display: false }}
                            }},
                            y: {{
                                ticks: {{ font: {{ size: 9 }} }},
                                grid: {{ color: 'rgba(0,0,0,0.05)' }}
                            }}
                        }}
                    }}
                }});
            }}
        }})();

        document.addEventListener('DOMContentLoaded', function() {{
            const buttons = document.querySelectorAll('.group-btn');
            const searchInput = document.getElementById('searchInput');
            const emptyRow = document.getElementById('empty-row');
            const allRows = document.querySelectorAll('#fundTable tbody tr:not(#empty-row)');
            let currentGroup = 'all';
            let searchKeyword = '';
            function applyFilters() {{
                let hasVisible = false;
                const keyword = searchKeyword.trim().toLowerCase();
                allRows.forEach(row => {{
                    if (row.classList.contains('holding-row')) return;
                    const rowGroup = row.getAttribute('data-group');
                    const nameCell = row.querySelector('.name a');
                    const name = nameCell ? nameCell.textContent.toLowerCase() : '';
                    const codeCell = row.querySelector('.code');
                    const code = codeCell ? codeCell.textContent.toLowerCase() : '';
                    const matchGroup = (currentGroup === 'all') || (rowGroup === currentGroup);
                    const matchSearch = keyword === '' || name.includes(keyword) || code.includes(keyword);
                    const visible = matchGroup && matchSearch;
                    if (visible) {{
                        row.style.display = '';
                        hasVisible = true;
                        const code = row.getAttribute('data-code');
                        const holdingRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                        if (holdingRow) {{
                            if (holdingRow.classList.contains('show')) {{
                                holdingRow.style.display = '';
                            }} else {{
                                holdingRow.style.display = 'none';
                            }}
                        }}
                    }} else {{
                        row.style.display = 'none';
                        const code = row.getAttribute('data-code');
                        const holdingRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                        if (holdingRow) {{
                            holdingRow.style.display = 'none';
                        }}
                    }}
                }});
                if (hasVisible) {{
                    emptyRow.style.display = 'none';
                }} else {{
                    emptyRow.style.display = '';
                    const msg = searchKeyword.trim() ? '未找到匹配基金' : '该分类暂无基金，敬请期待';
                    emptyRow.querySelector('td').textContent = msg;
                }}
            }}
            buttons.forEach(btn => {{
                btn.addEventListener('click', function() {{
                    buttons.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    currentGroup = this.dataset.group;
                    applyFilters();
                }});
            }});
            searchInput.addEventListener('input', function() {{
                searchKeyword = this.value;
                applyFilters();
            }});
            const defaultBtn = document.querySelector('.group-btn[data-group="all"]');
            if (defaultBtn) defaultBtn.classList.add('active');
            applyFilters();
        }});

        var chartInstances = {{}};
        var chartColors = {{
            line: '#1a73e8',
            point: '#1a73e8',
            bg: 'rgba(26,115,232,0.1)'
        }};
        const crosshairPlugin = {{
            id: 'fundCrosshair',
            afterDraw(chart) {{
                const crosshair = chart._fundCrosshair;
                if (!crosshair) return;
                const ctx = chart.ctx;
                const area = chart.chartArea;
                if (!area) return;
                const x = Math.max(area.left, Math.min(area.right, crosshair.x));
                const y = Math.max(area.top, Math.min(area.bottom, crosshair.y));
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(x, area.top);
                ctx.lineTo(x, area.bottom);
                ctx.moveTo(area.left, y);
                ctx.lineTo(area.right, y);
                ctx.lineWidth = 1;
                ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a';
                ctx.setLineDash([4, 4]);
                ctx.stroke();
                ctx.restore();
            }}
        }};
        Chart.register(crosshairPlugin);

        function filterNavData(data, period) {{
            if (!data || !data.dates || data.dates.length === 0) return {{ dates: [], navs: [] }};
            const dates = data.dates;
            const navs = data.navs;
            const latest = new Date(dates[dates.length - 1]);
            let startDate = new Date(latest);
            if (period === 'week') {{
                startDate.setDate(latest.getDate() - 7);
            }} else if (period === 'month') {{
                startDate.setMonth(latest.getMonth() - 1);
            }} else if (period === 'quarter') {{
                startDate.setMonth(latest.getMonth() - 3);
            }} else if (period === 'half') {{
                startDate.setMonth(latest.getMonth() - 6);
            }} else if (period === 'year') {{
                startDate.setFullYear(latest.getFullYear() - 1);
            }} else if (period === 'ytd') {{
                startDate = new Date(latest.getFullYear(), 0, 1);
            }}
            const indices = [];
            for (let i = 0; i < dates.length; i++) {{
                const d = new Date(dates[i]);
                if (d >= startDate) {{
                    indices.push(i);
                }}
            }}
            if (indices.length === 0) {{
                return {{ dates: dates, navs: navs }};
            }}
            const filteredDates = indices.map(i => dates[i]);
            const filteredNavs = indices.map(i => navs[i]);
            return {{ dates: filteredDates, navs: filteredNavs }};
        }}

        function initChart(code) {{
            const canvas = document.getElementById(`chart-${{code}}`);
            if (!canvas) return;
            if (chartInstances[code]) {{
                if (typeof chartInstances[code].destroy === 'function') {{
                    chartInstances[code].destroy();
                    delete chartInstances[code];
                }} else {{
                    return;
                }}
            }}
            const data = fundNavData[code];
            if (!data || !data.dates || data.dates.length === 0) {{
                canvas.parentElement.innerHTML = '<div style="padding:20px;text-align:center;color:var(--footer-text);">无净值数据</div>';
                return;
            }}
            const filtered = filterNavData(data, 'month');
            const ctx = canvas.getContext('2d');
            const chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: filtered.dates,
                    datasets: [{{
                        label: '净值',
                        data: filtered.navs,
                        borderColor: chartColors.line,
                        backgroundColor: chartColors.bg,
                        pointBackgroundColor: chartColors.point,
                        pointRadius: 1.5,
                        pointHoverRadius: 4,
                        fill: true,
                        tension: 0.1
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
                            chart._fundCrosshair = {{x: x, y: y}};
                        }} else {{
                            chart._fundCrosshair = null;
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
                                    if (!items || !items.length) return '';
                                    return '时间: ' + items[0].label;
                                }},
                                label: function(context) {{
                                    const values = context.dataset.data;
                                    const index = context.dataIndex;
                                    const value = Number(context.parsed.y);
                                    const firstValue = Number(values[0]);
                                    if (Number.isFinite(firstValue) && firstValue !== 0) {{
                                        const change = ((value - firstValue) / firstValue) * 100;
                                        return '净值: ' + value.toFixed(4) + '    涨幅: ' + (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
                                    }}
                                    return '净值: ' + value.toFixed(4);
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                maxTicksLimit: 12,
                                font: {{ size: 9 }},
                                color: getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a'
                            }},
                            grid: {{ display: false }}
                        }},
                        y: {{
                            ticks: {{
                                font: {{ size: 9 }},
                                color: getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a'
                            }},
                            grid: {{
                                color: getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#e0e0e0'
                            }}
                        }}
                    }}
                }}
            }});
            chartInstances[code] = chart;
            canvas.addEventListener('mouseleave', function() {{
                if (chart) {{
                    chart._fundCrosshair = null;
                    chart.draw();
                }}
            }});
            const container = document.getElementById(`chart-container-${{code}}`);
            if (container) {{
                const btns = container.querySelectorAll('.period-btn');
                btns.forEach(btn => {{
                    btn.addEventListener('click', function() {{
                        btns.forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        const period = this.dataset.period;
                        const filteredData = filterNavData(data, period);
                        if (chart) {{
                            chart.data.labels = filteredData.dates;
                            chart.data.datasets[0].data = filteredData.navs;
                            chart._fundCrosshair = null;
                            chart.update();
                        }}
                    }});
                }});
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
                if (!target) return;
                if (e.target.tagName === 'A') return;
                if (target.style.display === 'none') return;
                const code = target.dataset.code;
                const holdingRow = document.querySelector(`.holding-row[data-code="${{code}}"]`);
                if (holdingRow) {{
                    holdingRow.classList.toggle('show');
                    if (holdingRow.classList.contains('show')) {{
                        holdingRow.style.display = '';
                        setTimeout(function() {{
                            initChart(code);
                        }}, 100);
                    }} else {{
                        holdingRow.style.display = 'none';
                    }}
                }}
            }});
        }});

        document.addEventListener("DOMContentLoaded", function () {{
            const table = document.getElementById("fundTable");
            const headers = table.querySelectorAll("th");
            headers.forEach((th, idx) => {{
                th.addEventListener("click", function(e) {{
                    if (th.classList.contains("is-resizing") || window._isDragging) return;
                    sortTable(idx);
                }});
                const resizer = document.createElement("div");
                resizer.classList.add("resizer");
                th.appendChild(resizer);
                let x = 0, w = 0;
                resizer.addEventListener("mousedown", function (e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    window._isDragging = true;
                    x = e.clientX;
                    w = th.getBoundingClientRect().width;
                    th.style.width = w + "px";
                    th.classList.add("resizing");
                    th.classList.add("is-resizing");
                    function mouseMoveHandler(e) {{
                        const dx = e.clientX - x;
                        const newWidth = Math.max(40, w + dx);
                        th.style.width = newWidth + "px";
                    }}
                    function mouseUpHandler(e) {{
                        th.classList.remove("resizing");
                        document.removeEventListener("mousemove", mouseMoveHandler);
                        document.removeEventListener("mouseup", mouseUpHandler);
                        const finalWidth = th.getBoundingClientRect().width;
                        th.style.width = finalWidth + "px";
                        setTimeout(() => {{
                            window._isDragging = false;
                            th.classList.remove("is-resizing");
                        }}, 50);
                    }}
                    document.addEventListener("mousemove", mouseMoveHandler);
                    document.addEventListener("mouseup", mouseUpHandler);
                }});
            }});
        }});

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
            const holdingRows = allRows.filter(row => row.classList.contains('holding-row'));
            const holdingMap = {{}};
            holdingRows.forEach(row => {{
                const code = row.getAttribute('data-code');
                if (code) holdingMap[code] = row;
            }});
            if (currentSortCol === colIndex) {{
                isAscending = !isAscending;
            }} else {{
                currentSortCol = colIndex;
                isAscending = true;
            }}
            dataRows.sort((a, b) => {{
                const cellA = a.children[colIndex];
                const cellB = b.children[colIndex];
                let valA = cellA.getAttribute('data-val');
                let valB = cellB.getAttribute('data-val');
                const numA = parseFloat(valA);
                const numB = parseFloat(valB);
                if (!isNaN(numA) && !isNaN(numB)) {{
                    return isAscending ? numA - numB : numB - numA;
                }}
                return isAscending 
                    ? valA.localeCompare(valB, 'zh-Hans-CN', {{ sensitivity: 'accent' }})
                    : valB.localeCompare(valA, 'zh-Hans-CN', {{ sensitivity: 'accent' }});
            }});
            const fragment = document.createDocumentFragment();
            dataRows.forEach(row => {{
                fragment.appendChild(row);
                const code = row.getAttribute('data-code');
                const hRow = holdingMap[code];
                if (hRow) {{
                    fragment.appendChild(hRow);
                }}
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
    </script>
</body>
</html>
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    return os.path.abspath(filename)

def fetch_crypto_data(symbol, start_date, end_date):
    """获取主要虚拟货币对USDT历史收盘行情"""
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

    # 1. 币安公用K线接口
    try:
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1d&startTime={start_ts}&endTime={end_ts}&limit=1000"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            klines = json.loads(resp.read().decode('utf-8'))
            for item in klines:
                d_str = datetime.fromtimestamp(item[0] / 1000).strftime('%Y-%m-%d')
                nav = float(item[4])  # 收盘价
                if nav > 0:
                    data.append({"date": d_str, "nav": nav})
    except Exception:
        data = []

    # 2. akshare/新浪外盘期货兜底
    if not data and symbol == "BTC":
        try:
            df = ak.futures_foreign_hist(symbol="BTC")
            if df is not None and not df.empty:
                d_col = 'date' if 'date' in df.columns else df.columns[0]
                c_col = 'close' if 'close' in df.columns else df.columns[4]
                df[d_col] = pd.to_datetime(df[d_col]).dt.strftime('%Y-%m-%d')
                df = df[(df[d_col] >= start_date) & (df[d_col] <= end_date)]
                for _, row in df.iterrows():
                    val = float(row[c_col])
                    if val > 0:
                        data.append({"date": row[d_col], "nav": val})
        except Exception:
            pass

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
    """获取贵金属（伦敦金/银现货、国内黄金/白银连续主力期货）历史行情"""
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
        # 兼容处理：对外显示AUM，底层接口依然拉取 AU0 行情
        if symbol == "AUM":
            df = ak.futures_main_sina(symbol="AU0")
        elif symbol == "XAU":
            # 伦敦金现货/COMEX黄金主力
            for sym in ["GC", "XAU"]:
                try:
                    df = ak.futures_foreign_hist(symbol=sym)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
        elif symbol == "XAG":
            # 伦敦银现货/COMEX白银主力
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
                    df = ak.stock_us_hist(
                        symbol=try_symbol,
                        period="daily",
                        start_date=start_date.replace("-", ""),
                        end_date=end_date.replace("-", ""),
                        adjust=""
                    )
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                try:
                    df = ak.stock_us_daily(symbol="SOXL", adjust="")
                except Exception:
                    pass

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
                    df = ak.stock_us_hist(
                        symbol=try_symbol,
                        period="daily",
                        start_date=start_date.replace("-", ""),
                        end_date=end_date.replace("-", ""),
                        adjust=""
                    )
                    if df is not None and not df.empty:
                        break
                except Exception:
                    continue
            if df is None or df.empty:
                try:
                    df = ak.stock_us_daily(symbol="SOXX", adjust="")
                except Exception:
                    pass

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

        if not data:
            return None

        return data

    except Exception:
        return None

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_start = "2025-01-01"
    cutoff_date = "2026-04-01"

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default=default_start,
                        help="涨幅数据起始日期（默认2025-01-01）")
    parser.add_argument("--end", type=str, default=today_str)
    parser.add_argument("--funds", nargs="+", default=DEFAULT_FUNDS)
    parser.add_argument("--out", type=str, default="fund_drawdown_dashboard.html")

    args = parser.parse_args()
    opener = get_direct_opener()

    print(f"\n======== 开始抓取数据 (持仓多个季度，每个季度独立获取) ========")
    print(f"涨幅统计区间: {args.start} 至 {args.end}")
    print(f"回撤计算区间: {cutoff_date} 至 {args.end}")
    print(f"基金总数: {len(args.funds)}")

    results = []
    for idx, code in enumerate(args.funds, start=1):
        meta = fetch_fund_detail_meta(opener, code)
        raw_data = fetch_from_eastmoney(opener, code, args.start, args.end)
        if not raw_data:
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ❌ 历史净值抓取失败")
            continue
        raw_data_sorted = sorted(raw_data, key=lambda x: x['date'])
        is_qdii = code in QDII_CODES
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
                "fee_total": meta["fee_total"],
                "fee_val": meta["fee_val"],
                "fee_purchase": meta["fee_purchase"],
                "fee_redemption": meta["fee_redemption"],
                "buy_status": meta.get("buy_status", "--"),
                "buy_limit": meta.get("buy_limit", "无限额"),
                "buy_limit_val": meta.get("buy_limit_val", -1),
                "holdings": meta.get("holdings", []),
                "source": "天天基金",
                "nav_data": raw_data_sorted
            })
            results.append(res)
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ✅ 完成 (持仓报告期数: {len(res['holdings'])})")
        time.sleep(random.uniform(0.05, 0.1))

    print("\n======== 开始获取贵金属数据 ========")
    for symbol in PRECIOUS_METALS_SYMBOLS:
        try:
            data = fetch_precious_metals_data(symbol, args.start, args.end)
            if not data:
                print(f"[贵金属] {symbol} 无数据，跳过")
                continue
            meta_name = PRECIOUS_METALS_NAMES.get(symbol, symbol)
            res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
            if res:
                res.update({
                    "code": symbol,
                    "name": meta_name,
                    "scale": "--",
                    "scale_val": -1.0,
                    "fee_manage": "--",
                    "fee_custody": "--",
                    "fee_sales": "--",
                    "fee_purchase": "--",
                    "fee_redemption": "--",
                    "buy_status": "--",
                    "buy_limit": "--",
                    "buy_limit_val": -1,
                    "fee_total": "--",
                    "fee_val": -1.0,
                    "holdings": [],
                    "source": "贵金属行情",
                    "nav_data": data
                })
                results.append(res)
                print(f"[贵金属] {symbol} - {meta_name} ... ✅ (数据点 {len(data)})")
        except Exception as e:
            print(f"[贵金属] {symbol} 获取失败: {e}")

    print("\n======== 开始获取加密货币数据 ========")
    for symbol in CRYPTO_SYMBOLS:
        try:
            data = fetch_crypto_data(symbol, args.start, args.end)
            if not data:
                print(f"[加密货币] {symbol} 无数据，跳过")
                continue
            meta_name = CRYPTO_NAMES.get(symbol, symbol)
            res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
            if res:
                res.update({
                    "code": symbol,
                    "name": meta_name,
                    "scale": "--",
                    "scale_val": -1.0,
                    "fee_manage": "--",
                    "fee_custody": "--",
                    "fee_sales": "--",
                    "fee_purchase": "--",
                    "fee_redemption": "--",
                    "buy_status": "--",
                    "buy_limit": "--",
                    "buy_limit_val": -1,
                    "fee_total": "--",
                    "fee_val": -1.0,
                    "holdings": [],
                    "source": "现货行情",
                    "nav_data": data
                })
                results.append(res)
                print(f"[加密货币] {symbol} - {meta_name} ... ✅ (数据点 {len(data)})")
        except Exception as e:
            print(f"[加密货币] {symbol} 获取失败: {e}")

    print("\n======== 开始获取指数数据 ========")
    for symbol in INDEX_SYMBOLS:
        try:
            data = fetch_index_data(symbol, args.start, args.end)
            if not data:
                print(f"[指数] {symbol} 无数据，跳过")
                continue

            meta = {
                "name": INDEX_NAMES.get(symbol, symbol),
                "scale": "--",
                "scale_val": -1.0,
                "fee_manage": "--",
                "fee_custody": "--",
                "fee_sales": "--",
                "fee_purchase": "--",
                "fee_redemption": "--",
                "buy_status": "--",
                "buy_limit": "--",
                "buy_limit_val": -1,
                "fee_total": "--",
                "fee_val": -1.0,
                "holdings": []
            }
            res = analyze_fund_metrics(data, args.end, cutoff_date, is_qdii=False)
            if res:
                res.update({
                    "code": symbol,
                    "name": meta["name"],
                    "scale": meta["scale"],
                    "scale_val": meta["scale_val"],
                    "fee_manage": meta["fee_manage"],
                    "fee_custody": meta["fee_custody"],
                    "fee_sales": meta["fee_sales"],
                    "fee_total": meta["fee_total"],
                    "fee_val": meta["fee_val"],
                    "fee_purchase": meta["fee_purchase"],
                    "fee_redemption": meta["fee_redemption"],
                    "buy_status": meta["buy_status"],
                    "buy_limit": meta["buy_limit"],
                    "buy_limit_val": meta["buy_limit_val"],
                    "holdings": meta["holdings"],
                    "source": "akshare指数",
                    "nav_data": data
                })
                results.append(res)
                print(f"[指数] {symbol} - {meta['name']} ... ✅ (数据点 {len(data)})")
        except Exception as e:
            print(f"[指数] {symbol} 获取失败: {e}")

    if results:
        abs_path = generate_html_report(results, args.start, args.end, today_str, filename=args.out)
        print(f"\n🎉 网页生成成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass

if __name__ == "__main__":
    main()