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
from datetime import datetime, timedelta

# 强制清空代理环境变量
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

DEFAULT_FUNDS = [
    "002891", "014002", "006555", "012922", "012920", "021662", "457001", "539002",
    "018147", "021842", "006373", "018036", "501226", "008254", "008253", "017731",
    "017730", "016665", "016664", "018230", "018229", "021277", "270023", "005698",
    "024239", "501312", "017204", "017654", "017653", "022184", "100055", "017437",
    "017436", "017145", "017144", "016702", "016701", "016823", "164212", "019156",
    "019155",
    "016668", "501225", "015202", "001668", "000043"
]

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_direct_opener():
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def fetch_fund_detail_meta(opener, code):
    """全面抓取：名称、规模、运作费率（管/托/销）、申购费率（优惠后）、赎回费率、交易状态、限额"""
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
        "fee_val": -1.0
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"https://fund.eastmoney.com/{code}.html",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    # 1. 获取基金主页 HTML
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

    # 2. 从 pingzhongdata.js 补充
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

    # 3. 从 F10 页面补充
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

    # 4. 处理缺失值
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

    # 5. 计算运作费合计
    m_val = float(re.search(r'([\d.]+)', meta["fee_manage"]).group(1)) if meta["fee_manage"] != "--" else 0.0
    c_val = float(re.search(r'([\d.]+)', meta["fee_custody"]).group(1)) if meta["fee_custody"] != "--" else 0.0
    s_val = float(re.search(r'([\d.]+)', meta["fee_sales"]).group(1)) if meta["fee_sales"] != "--" else 0.0
    tot = m_val + c_val + s_val
    if tot > 0:
        meta["fee_val"] = tot
        meta["fee_total"] = f"{tot:.2f}%"
    else:
        meta["fee_total"] = "0.00%"

    return meta

def fetch_from_eastmoney(opener, code, start_date, end_date):
    """获取历史净值数据（自动翻页，每页20条），带缓存"""
    cache_file = os.path.join(CACHE_DIR, f"{code}.json")
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

def analyze_fund_metrics(valid_data, end_date, cutoff_date):
    data_all = sorted(valid_data, key=lambda x: x["date"])
    if not data_all:
        return None

    data_cutoff = [item for item in data_all if item["date"] >= cutoff_date]
    if not data_cutoff:
        data_cutoff = data_all

    latest_nav = data_all[-1]["nav"]
    latest_date = data_all[-1]["date"]

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
        "week_gain": week_gain,
        "month_gain": month_gain,
        "quarter_gain": quarter_gain,
        "half_year_gain": half_year_gain,
        "year_gain": year_gain,
        "ytd_gain": ytd_gain
    }

def generate_html_report(results, start_date, end_date, filename="fund_drawdown_dashboard.html"):
    rows_html = ""
    for r in results:
        fund_url = f"https://fund.eastmoney.com/{r['code']}.html"
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

        rows_html += f"""
        <tr>
            <td class="code" data-val="{r['code']}">{r['code']}</td>
            <td class="name" data-val="{r['name']}">
                <a href="{fund_url}" target="_blank" title="点击查看天天基金概况">{r['name']}</a>
                <div class="redemption-sub" style="white-space: normal; line-height: 1.6;">赎回:<br>{redemption_lines}</div>
            </td>
            <td data-val="{r['scale_val']}" class="highlight-val">{r['scale']}</td>
            <td data-val="{r['fee_val']}">{r['fee_total']} <span class="fee-sub">(管:{r['fee_manage']}/托:{r['fee_custody']}/销:{r['fee_sales']})</span></td>
            <td data-val="{r['fee_purchase']}">{r['fee_purchase']}</td>
            <td data-val="{limit_val}">{r.get('buy_status', '--')}<div class="fee-sub">{limit_display}</div></td>
            <td data-val="{r['max_nav']}">{max_nav_display}</td>
            <td data-val="{r['min_nav']}">{min_nav_display}</td>
            <td data-val="{r['latest_nav']}">{r['latest_nav']:.4f}</td>
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
            <td data-val="{r['week_gain'] if r['week_gain'] is not None else -9999}">{format_gain(r['week_gain'])}</td>
            <td data-val="{r['month_gain'] if r['month_gain'] is not None else -9999}">{format_gain(r['month_gain'])}</td>
            <td data-val="{r['quarter_gain'] if r['quarter_gain'] is not None else -9999}">{format_gain(r['quarter_gain'])}</td>
            <td data-val="{r['half_year_gain'] if r['half_year_gain'] is not None else -9999}">{format_gain(r['half_year_gain'])}</td>
            <td data-val="{r['year_gain'] if r['year_gain'] is not None else -9999}">{format_gain(r['year_gain'])}</td>
            <td data-val="{r['ytd_gain'] if r['ytd_gain'] is not None else -9999}">{format_gain(r['ytd_gain'])}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>场外基金量化与费率规模看板（含多周期涨幅）</title>
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
        }}
        body {{ 
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif; 
            background-color: var(--bg);
            color: var(--text);
            margin: 0; 
            padding: 20px 30px; 
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            transition: background-color 0.3s, color 0.3s;
        }}
        .header {{ text-align: center; margin-bottom: 12px; flex-shrink: 0; }}
        .header h2 {{ color: #1a73e8; margin: 0 0 4px 0; font-size: 20px; }}
        .header p {{ color: var(--footer-text); font-size: 13px; margin: 0; }}
        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 30px;
            background: var(--header-bg);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 16px;
            cursor: pointer;
            z-index: 100;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: background 0.2s;
        }}
        .theme-toggle:hover {{ opacity: 0.8; }}
        .table-container {{ 
            width:100%; 
            height: calc(100vh - 200px); 
            overflow-y: auto; 
            overflow-x: scroll; 
            box-sizing:border-box; 
            background: var(--table-bg);
            border-radius:12px; 
            box-shadow:0 4px 15px rgba(0,0,0,0.08); 
            padding:20px; 
            border:1px solid var(--border);
            flex: 1 1 auto;
            min-height: 0;
            transition: background 0.3s, border-color 0.3s;
        }}
        .table-container::-webkit-scrollbar {{
            height: 14px;
            width: 10px;
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
            min-width:2250px; 
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
        th:nth-child(1), td:nth-child(1) {{ width: 60px; text-align: left; white-space: nowrap; }}
        th:nth-child(2), td:nth-child(2) {{ width: 240px; min-width: 180px; text-align: left; white-space: normal; word-break: break-word; vertical-align: middle; }}
        th:nth-child(3), td:nth-child(3) {{ width: 80px; text-align: left; white-space: nowrap; }}
        th:nth-child(4), td:nth-child(4) {{ width: 130px; text-align: left; white-space: normal; word-break: break-word; }}
        th:nth-child(5), td:nth-child(5) {{ width: 70px; text-align: left; white-space: nowrap; }}
        th:nth-child(6), td:nth-child(6) {{ width: 100px; text-align: left; white-space: nowrap; }}
        th:nth-child(7), td:nth-child(7),
        th:nth-child(8), td:nth-child(8) {{ width: 128px; white-space: nowrap; }}
        th:nth-child(9), td:nth-child(9) {{ width: 85px; white-space: nowrap; }}
        th:nth-child(10), td:nth-child(10) ,
        th:nth-child(11), td:nth-child(11),
        th:nth-child(12), td:nth-child(12) {{ width: 300px; white-space: nowrap; }}
        th:nth-child(13), td:nth-child(13) {{ width: 80px; white-space: nowrap; }}
        th:nth-child(14), td:nth-child(14),
        th:nth-child(15), td:nth-child(15),
        th:nth-child(16), td:nth-child(16),
        th:nth-child(17), td:nth-child(17),
        th:nth-child(18), td:nth-child(18),
        th:nth-child(19), td:nth-child(19) {{ width: 80px; white-space: nowrap; }}
        th {{ 
            background-color: var(--header-bg);
            color: var(--header-text);
            font-weight: 600; 
            text-align: right; 
            user-select: none; 
            cursor: pointer; 
            transition: background-color 0.2s, color 0.2s; 
            white-space: nowrap; 
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
        .footer-note {{ 
            margin-top: 10px; 
            font-size: 12px; 
            color: var(--footer-text);
            line-height: 1.4; 
            background: var(--footer-bg);
            padding: 10px 12px; 
            border-radius: 6px; 
            border: 1px solid var(--border);
            flex-shrink: 0;
            transition: background 0.3s, color 0.3s, border-color 0.3s;
        }}
        .footer-note p {{ margin: 2px 0; }}
    </style>
</head>
<body>
    <button class="theme-toggle" id="themeToggle">🌓 切换主题</button>
    <div class="header">
        <h2>场外基金核心量化与全费率规模看板（含多周期涨幅）</h2>
        <p>统计时间区间：<strong>{start_date}</strong> 至 <strong>{end_date}</strong> （包含基金数：{len(results)} 只）</p>
        <p style="font-size:12px; color: var(--footer-text);">申购费率已取优惠后费率，销售服务费默认0.00%。赎回费率百分比已高亮。</p>
        <p style="font-size:12px; color: var(--footer-text);">最高/最低净值显示为2026-04-01后最大回撤的峰值与谷值（谷值在峰值之后）。涨幅基于完整数据计算。</p>
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
                    <th data-col="13">近一周 <span class="sort-icon">⇅</span></th>
                    <th data-col="14">近一月 <span class="sort-icon">⇅</span></th>
                    <th data-col="15">近3月 <span class="sort-icon">⇅</span></th>
                    <th data-col="16">近半年 <span class="sort-icon">⇅</span></th>
                    <th data-col="17">近一年 <span class="sort-icon">⇅</span></th>
                    <th data-col="18">今年内 <span class="sort-icon">⇅</span></th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    <div class="footer-note">
        <p><strong>使用提示：</strong> 列宽可拖拽调整，点击表头排序。涨幅数据基于可获取的历史净值，若区间内无对应日期数据则显示“-”。<br>
        <span style="color: #1a73e8;">👉 横向滚动条位于表格底部（始终可见），纵向滚动查看全部基金。修复时间从2026-04-01后的最低点开始计算。</span></p>
    </div>
    <script>
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

        // 以下为原排序和列宽拖拽逻辑
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
            const table = document.getElementById("fundTable");
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));
            if (currentSortCol === colIndex) {{
                isAscending = !isAscending;
            }} else {{
                currentSortCol = colIndex;
                isAscending = true;
            }}
            rows.sort((a, b) => {{
                const cellA = a.children[colIndex];
                const cellB = b.children[colIndex];
                let valA = cellA.getAttribute("data-val");
                let valB = cellB.getAttribute("data-val");
                const numA = parseFloat(valA);
                const numB = parseFloat(valB);
                if (!isNaN(numA) && !isNaN(numB)) {{
                    return isAscending ? numA - numB : numB - numA;
                }}
                return isAscending 
                    ? valA.localeCompare(valB, 'zh-Hans-CN', {{ sensitivity: 'accent' }})
                    : valB.localeCompare(valA, 'zh-Hans-CN', {{ sensitivity: 'accent' }});
            }});
            rows.forEach(row => tbody.appendChild(row));
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

    print(f"\n======== 开始抓取数据 (缓存启用，暗色模式支持) ========")
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
        res = analyze_fund_metrics(raw_data, args.end, cutoff_date)
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
                "source": "天天基金"
            })
            results.append(res)
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ✅ 完成")
        time.sleep(random.uniform(0.05, 0.1))

    if results:
        abs_path = generate_html_report(results, args.start, args.end, filename=args.out)
        print(f"\n🎉 网页生成成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass

if __name__ == "__main__":
    main()