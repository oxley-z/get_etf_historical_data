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
    "019155", "016668", "501225", "015202", "001668", "000043",
    # CPO 组
    "022365", "540010", "002112", "011892", "021528",
    "009645", "011370", "011452", "016371", "001956",
    "016234", "016173", "006616", "018291", "020661",
    "017462", "001438", "008984", "180031", "004320",
    # 存储芯片组
    "025500", "025209", "018816", "014320", "027063",
    # 半导体材料设备组
    "024418", "024975", "020640", "019633", "024424",
    "017811", "013841", "007491", "020629", "017747",
    "026633", "162214", "007343", "018777",
    # 人工智能组
    "024663", "024726", "023286", "023408", "025506",
    "025493", "025653", "005963", "014162", "011840",
    "024412", "024775", "026613", "023551", "024561",
    # 电网设备组（新增）
    "025857", "023639", "023675", "019411", "167002",
    "020425", "002164", "017133", "017042", "026681",
    "016387", "025833", "011172", "001665", "018919",
    # 机器人组（新增）
    "016531", "018345", "020482", "018125", "007519",
    "014243", "018957", "003835", "014939", "008998",
    "004233", "008182", "017968", "024648"
]

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_direct_opener():
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def extract_holdings_from_df(df):
    """从DataFrame提取持仓列表（名称+比例）备用"""
    if df is None or df.empty:
        return []
    ratio_col = None
    for col in df.columns:
        if '占净值比例' in col or '比例' in col:
            ratio_col = col
            break
    if ratio_col is None:
        for col in df.columns:
            if df[col].dtype in ['float64', 'int64'] and '代码' not in col:
                ratio_col = col
                break
    if ratio_col:
        df = df.sort_values(by=ratio_col, ascending=False)
    top10 = df.head(10)
    holdings = []
    name_col = None
    for col in df.columns:
        if '股票名称' in col or '名称' in col or '证券简称' in col:
            name_col = col
            break
    if name_col is None:
        for col in df.columns:
            if df[col].dtype == 'object':
                name_col = col
                break
    if name_col is None:
        name_col = df.columns[0]
    for _, row in top10.iterrows():
        name = str(row[name_col]) if pd.notna(row[name_col]) else ''
        ratio = 0.0
        if ratio_col:
            ratio = float(row[ratio_col]) if pd.notna(row[ratio_col]) else 0.0
        if name and name not in ['nan', 'None', '']:
            holdings.append({'name': name, 'ratio': ratio})
    return holdings

def fetch_holdings(opener, code):
    """
    获取基金前十大持仓（最近四个季度），优先使用 akshare 多年度数据，
    失败时降级到原有 API/akshare 方法。
    返回格式: [{"date": "2026Q2", "holdings": [{"name": "xx", "ratio": 9.9}]}]
    """
    print(f"\n[DEBUG] 开始获取基金 {code} 的持仓数据")
    cache_file = os.path.join(CACHE_DIR, f"{code}_holdings.json")

    # 1. 检查缓存（如果存在且有效，直接返回）
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) >= 2 and 'date' in data[0]:
                # 至少有两个季度且非空
                if any(len(p['holdings']) > 0 for p in data):
                    print(f"[DEBUG] 使用缓存数据，共 {len(data)} 个报告期")
                    return data
                else:
                    print("[DEBUG] 缓存数据为空，重新获取")
                    os.remove(cache_file)
        except Exception:
            try:
                os.remove(cache_file)
            except:
                pass

    # 2. 主要方法：使用 akshare 获取近三年所有季度数据
    print("[DEBUG] 尝试使用 akshare 获取多年度数据...")
    try:
        current_year = datetime.now().year
        years = [str(current_year - i) for i in range(3)]  # 今年、去年、前年
        all_dfs = []
        for year in years:
            try:
                df = ak.fund_portfolio_hold_em(symbol=code, date=year)
                if df is not None and not df.empty:
                    all_dfs.append(df)
                    print(f"[DEBUG] 获取 {year} 年数据成功，行数: {len(df)}")
            except Exception as e:
                print(f"[DEBUG] akshare {year} 年失败: {e}")

        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            # 去重（同一季度可能重复）
            combined.drop_duplicates(inplace=True)
            # 确保 '季度' 列存在
            if '季度' not in combined.columns:
                # 若没有季度列，尝试从报告期生成（通常有 '报告期'）
                if '报告期' in combined.columns:
                    # 转换报告期 (如 2026-06-30 -> 2026Q2)
                    combined['季度'] = combined['报告期'].apply(
                        lambda x: f"{x[:4]}Q{(int(x[5:7])-1)//3 + 1}" if isinstance(x, str) and len(x)>=7 else None
                    )
                else:
                    # 若没有，尝试用 '截止日期' 等
                    date_col = next((c for c in combined.columns if '日期' in c or '时间' in c), None)
                    if date_col:
                        combined['季度'] = combined[date_col].apply(
                            lambda x: f"{x[:4]}Q{(int(x[5:7])-1)//3 + 1}" if isinstance(x, str) and len(x)>=7 else None
                        )
                    else:
                        # 最后，尝试从 '股票代码' 分组无法得到季度，则放弃
                        print("[DEBUG] 无法确定季度列，akshare 数据无效")
                        raise ValueError("缺少季度信息")

            # 按季度分组，取每个季度前10大，取最近四个季度
            quarters = sorted(combined['季度'].unique(), reverse=True)[:4]  # 修改为4个季度
            result = []
            for q in quarters:
                df_q = combined[combined['季度'] == q].sort_values('占净值比例', ascending=False)
                # 取前10，并确保列名正确（可能有 '股票名称' 或 '名称'）
                name_col = '股票名称' if '股票名称' in df_q.columns else '名称' if '名称' in df_q.columns else None
                ratio_col = '占净值比例' if '占净值比例' in df_q.columns else None
                if name_col is None or ratio_col is None:
                    # 尝试其他列
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
                print(f"[DEBUG] akshare 获取成功，共 {len(result)} 个季度")
                # 保存缓存
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception as e:
        print(f"[DEBUG] akshare 主方法失败: {e}")

    # 3. 降级方案：保留原有的多种尝试（API、akshare 季度末日期、akshare 年份格式）
    print("[DEBUG] 降级到原有方法...")
    try:
        return _fetch_holdings_legacy(opener, code)
    except NameError:
        print("[DEBUG] 无备用函数，使用简化后备...")
        print("[ERROR] 请将原 fetch_holdings 函数重命名为 _fetch_holdings_legacy 并保留")
        return []

def fetch_fund_detail_meta(opener, code):
    """全面抓取：名称、规模、运作费率（管/托/销）、申购费率（优惠后）、赎回费率、交易状态、限额、持仓"""
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

    # 6. 获取前十大持仓（多个季度）
    meta["holdings"] = fetch_holdings(opener, code)

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

    # 计算今日涨幅（相对于前一个交易日），仅作为计算，显示逻辑在HTML中根据日期决定
    today_gain = None
    if len(data_all) >= 2:
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
        "017462", "001438", "008984", "180031", "004320"
    }

    STORAGE_CODES = {
        "025500", "025209", "018816", "014320", "027063"
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

    col_count = 20  # 新增今日涨幅列

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
        except:
            return date_str

    # 构建基金净值数据字典用于图表
    nav_data_json = {}
    for r in results:
        if 'nav_data' in r and r['nav_data']:
            # 按日期排序（已排序）
            nav_data_json[r['code']] = {
                'dates': [item['date'] for item in r['nav_data']],
                'navs': [item['nav'] for item in r['nav_data']]
            }

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

        def gain_class(val):
            if val is None:
                return ''
            if val > 0:
                return 'gain-positive'
            elif val < 0:
                return 'gain-negative'
            else:
                return ''

        # 分组判断
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
        else:
            group = "qdii"

        holdings_history = r.get('holdings', [])
        print(f"[HTML生成] 基金 {r['code']} 持仓数据: {len(holdings_history)} 个报告期")
        if holdings_history:
            for idx, p in enumerate(holdings_history):
                print(f"[HTML生成]  季度 {p['date']} 股票数: {len(p['holdings'])}")

        # 今日涨幅：如果最新日期等于今天，显示涨幅，否则显示 "--"
        today_gain_val = r.get('today_gain', None)
        if r['latest_date'] == today_str:
            today_gain_display = format_gain(today_gain_val)
            today_gain_class = gain_class(today_gain_val)
            today_data_val = today_gain_val if today_gain_val is not None else -9999
        else:
            today_gain_display = "--"
            today_gain_class = ''
            today_data_val = -9999

        rows_html += f"""
        <tr data-group="{group}" class="fund-row" data-code="{r['code']}">
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
            <td data-val="{today_data_val}" class="{today_gain_class}">{today_gain_display}</td>
            <td data-val="{r['week_gain'] if r['week_gain'] is not None else -9999}" class="{gain_class(r['week_gain'])}">{format_gain(r['week_gain'])}</td>
            <td data-val="{r['month_gain'] if r['month_gain'] is not None else -9999}" class="{gain_class(r['month_gain'])}">{format_gain(r['month_gain'])}</td>
            <td data-val="{r['quarter_gain'] if r['quarter_gain'] is not None else -9999}" class="{gain_class(r['quarter_gain'])}">{format_gain(r['quarter_gain'])}</td>
            <td data-val="{r['half_year_gain'] if r['half_year_gain'] is not None else -9999}" class="{gain_class(r['half_year_gain'])}">{format_gain(r['half_year_gain'])}</td>
            <td data-val="{r['year_gain'] if r['year_gain'] is not None else -9999}" class="{gain_class(r['year_gain'])}">{format_gain(r['year_gain'])}</td>
            <td data-val="{r['ytd_gain'] if r['ytd_gain'] is not None else -9999}" class="{gain_class(r['ytd_gain'])}">{format_gain(r['ytd_gain'])}</td>
        </tr>
        """

        # 持仓展开行：左侧三个季度卡片，右侧图表
        if holdings_history:
            sorted_holdings = sorted(holdings_history, key=lambda x: x['date'], reverse=True)
            display_holdings = sorted_holdings[:3]
            holdings_html = ""
            for i, period in enumerate(display_holdings):
                date_str = period['date']
                holdings_list = period['holdings']
                label = date_to_label(date_str)
                prev_period = sorted_holdings[i+1] if i+1 < len(sorted_holdings) else None
                prev_holdings_dict = {}
                if prev_period:
                    prev_holdings_dict = {h['name']: h['ratio'] for h in prev_period['holdings']}
                stocks_html = ""
                if holdings_list:
                    for h in holdings_list:
                        name = h['name']
                        ratio = h['ratio']
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
                else:
                    stocks_html = '<div style="color: var(--footer-text);">暂无持仓数据</div>'
                holdings_html += f"""
                <div class="quarter-card">
                    <div class="quarter-label">{label}</div>
                    <div class="quarter-stocks">{stocks_html}</div>
                </div>
                """
        else:
            holdings_html = '<div>暂无持仓数据</div>'

        # 图表区域（右侧50%）
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

    # 分组标签
    groups = [
        ("汇总", "all"),
        ("QDII", "qdii"),
        ("半导体材料设备", "semiconductor"),
        ("CPO", "cpo"),
        ("人工智能", "ai"),
        ("存储芯片", "storage"),
        ("电网设备", "grid"),
        ("机器人", "robot")
    ]
    buttons_html = ""
    for label, group_id in groups:
        buttons_html += f'<button class="group-btn" data-group="{group_id}">{label}</button>'

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
        .group-tabs {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
            margin-bottom: 10px;
            flex-shrink: 0;
        }}
        .group-btn {{
            background: var(--btn-bg);
            color: var(--btn-text);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 6px 18px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 500;
        }}
        .group-btn:hover {{
            background: var(--btn-active-bg);
            color: var(--btn-active-text);
        }}
        .group-btn.active {{
            background: var(--btn-active-bg);
            color: var(--btn-active-text);
            border-color: var(--btn-active-bg);
        }}
        .search-container {{
            display: flex;
            justify-content: center;
            margin-bottom: 12px;
            flex-shrink: 0;
        }}
        .search-container input {{
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid var(--input-border);
            background: var(--input-bg);
            color: var(--text);
            font-size: 14px;
            width: 300px;
            max-width: 80%;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-container input:focus {{
            border-color: #1a73e8;
        }}
        .search-container input::placeholder {{
            color: var(--footer-text);
        }}
        .table-container {{ 
            width:100%; 
            height: calc(100vh - 280px); 
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
        th:nth-child(2), td:nth-child(2) {{ width: 240px; min-width: 180px; text-align: left; white-space: normal; word-break: break-word; vertical-align: middle; }}
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
        th:nth-child(14), td:nth-child(14) {{ width: 70px; white-space: nowrap; }}
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
        .gain-positive {{ color: #d93025; font-weight: bold; }}
        .gain-negative {{ color: #188038; font-weight: bold; }}
        .fund-row {{ cursor: pointer; }}
        .fund-row .name a {{ pointer-events: auto; cursor: pointer; }}
        .holding-row td {{
            background-color: var(--hover-bg) !important;
            border-top: 1px dashed var(--border);
        }}
        .holding-row {{ display: none; }}
        .holding-row.show {{ display: table-row; }}

        /* 持仓与折线图同一行：左半边三个季度等宽，右半边折线图 */
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
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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

        .chart-container {{
            flex: 0 0 calc(50% - 20px);
            background: var(--card-bg);
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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
            .holdings-wrapper {{
                gap: 10px;
            }}
            .holdings-container {{
                gap: 6px;
            }}
            .quarter-card {{
                padding: 8px 6px;
            }}
            .stock-item {{
                grid-template-columns: minmax(0, 1fr) 48px 56px;
                font-size: 10px;
            }}
            .stock-change {{
                font-size: 9px;
            }}
        }}

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
        <h2>场外基金核心量化与全费率规模看板（含多周期涨幅及走势图）</h2>
        <p>统计时间区间：<strong>{start_date}</strong> 至 <strong>{end_date}</strong> （包含基金数：{len(results)} 只）</p>
        <p style="font-size:12px; color: var(--footer-text);">申购费率已取优惠后费率，销售服务费默认0.00%。赎回费率百分比已高亮。</p>
        <p style="font-size:12px; color: var(--footer-text);">最高/最低净值显示为2026-04-01后最大回撤的峰值与谷值（谷值在峰值之后）。涨幅基于完整数据计算。</p>
    </div>
    <div class="group-tabs">
        {buttons_html}
    </div>
    <div class="search-container">
        <input type="text" id="searchInput" placeholder="🔍 搜索基金名称或代码 ...">
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
                    <th data-col="13">今日涨幅 ({today_str}) <span class="sort-icon">⇅</span></th>
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
        <p><strong>使用提示：</strong> 列宽可拖拽调整，点击表头排序。涨幅数据基于可获取的历史净值，若区间内无对应日期数据则显示“-”。<br>
        <span style="color: #1a73e8;">👉 点击基金行可展开/收起持仓与净值走势图；左半边三个季度持仓等宽排列，鼠标进入走势图显示十字线、时间、净值和区间涨幅。</span></p>
    </div>
    <script>
        // 基金净值数据（由Python注入）
        var fundNavData = {json.dumps(nav_data_json, ensure_ascii=False)};

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

        // 分组 + 搜索 联动过滤（修改：增加 'all' 分组支持）
        document.addEventListener('DOMContentLoaded', function() {{
            const buttons = document.querySelectorAll('.group-btn');
            const searchInput = document.getElementById('searchInput');
            const emptyRow = document.getElementById('empty-row');
            const allRows = document.querySelectorAll('#fundTable tbody tr:not(#empty-row)');

            let currentGroup = 'all';   // 默认显示汇总
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

            // 默认激活汇总按钮
            const defaultBtn = document.querySelector('.group-btn[data-group="all"]');
            if (defaultBtn) defaultBtn.classList.add('active');
            applyFilters();
        }});

        // 图表相关
        var chartInstances = {{}};
        var chartColors = {{
            line: '#1a73e8',
            point: '#1a73e8',
            bg: 'rgba(26,115,232,0.1)'
        }};

        // 鼠标十字线插件：鼠标进入图表后显示横/纵十字线
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
                // 如果区间无数据，取全部
                return {{ dates: dates, navs: navs }};
            }}
            const filteredDates = indices.map(i => dates[i]);
            const filteredNavs = indices.map(i => navs[i]);
            return {{ dates: filteredDates, navs: filteredNavs }};
        }}

        function initChart(code) {{
            const canvas = document.getElementById(`chart-${{code}}`);
            if (!canvas) return;
            // 检查是否已初始化
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
            // 默认显示近一月
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
                        legend: {{
                            display: false
                        }},
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
                                font: {{
                                    size: 9
                                }},
                                color: getComputedStyle(document.documentElement).getPropertyValue('--footer-text').trim() || '#70757a'
                            }},
                            grid: {{
                                display: false
                            }}
                        }},
                        y: {{
                            ticks: {{
                                font: {{
                                    size: 9
                                }},
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

            // 鼠标离开图表时隐藏十字线
            canvas.addEventListener('mouseleave', function() {{
                if (chart) {{
                    chart._fundCrosshair = null;
                    chart.draw();
                }}
            }});

            // 绑定周期按钮事件
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

        // 点击基金行展开/关闭持仓，并初始化图表
        document.addEventListener('DOMContentLoaded', function() {{
            const table = document.getElementById('fundTable');
            table.addEventListener('click', function(e) {{
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
                        // 延迟初始化图表，确保渲染完成
                        setTimeout(function() {{
                            initChart(code);
                        }}, 100);
                    }} else {{
                        holdingRow.style.display = 'none';
                    }}
                }}
            }});
        }});

        // 排序和列宽拖拽逻辑（原代码保留）
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

<style>
.holding-empty {{
    min-height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #999;
    font-size: 14px;
}}
</style>
<script>
document.addEventListener("DOMContentLoaded", function () {{
    // 对所有持仓卡片进行处理：
    // 卡片标签保留原来的“2026年2季度股票投资明细”等标题；
    // 如果卡片内部没有有效持仓行，则显示“暂无持仓数据”。
    document.querySelectorAll(".holding-card, .position-card, .holding-item").forEach(function(card) {{
        var table = card.querySelector("table");
        if (!table) {{
            if (!card.querySelector(".holding-empty")) {{
                var empty = document.createElement("div");
                empty.className = "holding-empty";
                empty.textContent = "暂无持仓数据";
                card.appendChild(empty);
            }}
            return;
        }}

        var rows = table.querySelectorAll("tbody tr");
        var validRows = 0;

        rows.forEach(function(row) {{
            var cells = row.querySelectorAll("td");
            var text = row.textContent.trim();
            if (cells.length > 0 && text && text !== "暂无持仓数据") {{
                validRows++;
            }}
        }});

        if (validRows === 0) {{
            table.style.display = "none";
            if (!card.querySelector(".holding-empty")) {{
                var empty = document.createElement("div");
                empty.className = "holding-empty";
                empty.textContent = "暂无持仓数据";
                card.appendChild(empty);
            }}
        }}
    }});
}});
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
        # 排序并保存净值数据用于图表
        raw_data_sorted = sorted(raw_data, key=lambda x: x['date'])
        res = analyze_fund_metrics(raw_data_sorted, args.end, cutoff_date)
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
                "nav_data": raw_data_sorted  # 添加净值数据
            })
            results.append(res)
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ✅ 完成 (持仓报告期数: {len(res['holdings'])})")
        time.sleep(random.uniform(0.05, 0.1))

    if results:
        abs_path = generate_html_report(results, args.start, args.end, today_str, filename=args.out)
        print(f"\n🎉 网页生成成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass

if __name__ == "__main__":
    main()