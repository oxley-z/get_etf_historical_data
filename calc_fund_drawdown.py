import os
import re
import json
import time
import random
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ==========================================
# 1. 进程内强制清空代理环境变量（彻底杜绝 ProxyError）
# ==========================================
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

# 仅保留纯基金代码列表，名称由源动态获取
DEFAULT_FUNDS = [
    "002891", "014002", "012922", "021662", "539002", "021842", "018036",
    "008254", "017731", "016665", "018230", "021277", "005698", "501312",
    "017654", "022184", "017437", "017145", "016702", "016823", "019156"
]

def get_direct_opener():
    """创建一个彻底绕过本地代理的 urllib opener"""
    proxy_handler = urllib.request.ProxyHandler({})  # 空字典代表强制直连
    return urllib.request.build_opener(proxy_handler)

# ==========================================
# 2. 从数据源动态获取基金名称（不写死）
# ==========================================
def fetch_fund_name_from_source(opener, code):
    """从天天基金官方 JS 数据源中实时解析基金全称"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": f"https://fund.eastmoney.com/{code}.html"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            # 匹配 var fS_name = "xxx";
            match = re.search(r'var\s+fS_name\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    
    # 降级备用：如果源获取失败，返回代码占位
    return f"未知基金_{code}"

# ==========================================
# 3. 多源净值获取模块
# ==========================================
def fetch_from_eastmoney(opener, code, start_date, end_date):
    base_url = "https://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "callback": "jQuery11230_lsjz",
        "fundCode": code,
        "pageIndex": 1,
        "pageSize": 200,
        "startDate": start_date,
        "endDate": end_date,
        "_": str(int(time.time() * 1000))
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html",
        "Accept": "*/*"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode('utf-8')
            match = re.search(r'jQuery11230_lsjz\((.*)\)', html)
            if match:
                res_json = json.loads(match.group(1))
                lsjz = res_json.get("Data", {}).get("LSJZList", [])
                if lsjz:
                    clean_data = []
                    for item in lsjz:
                        if item.get("DWJZ"):
                            clean_data.append({"date": item["FSRQ"], "nav": float(item["DWJZ"])})
                    return clean_data
    except Exception:
        pass
    return None

def fetch_from_sina(opener, code, start_date, end_date):
    url = f"https://finance.sina.com.cn/fund/api/jsonp.php/IO.XSRF.Fund.getFundNav/FundService.getNav?symbol={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode('utf-8')
            match = re.search(r'\((\{.*\})\)', html)
            if match:
                res_json = json.loads(match.group(1))
                data_list = res_json.get("result", {}).get("data", {}).get("data", [])
                clean_data = []
                for item in data_list:
                    fdate = item.get("date")
                    if fdate and start_date <= fdate <= end_date and item.get("nav"):
                        clean_data.append({"date": fdate, "nav": float(item["nav"])})
                if clean_data:
                    return clean_data
    except Exception:
        pass
    return None

def fetch_fund_data_multisource(opener, code, start_date, end_date):
    data = fetch_from_eastmoney(opener, code, start_date, end_date)
    if data:
        return data, "天天基金"

    data = fetch_from_sina(opener, code, start_date, end_date)
    if data:
        return data, "新浪财经"

    return None, "全部失败"

# ==========================================
# 4. 指标计算核心算法
# ==========================================
def analyze_fund_metrics(valid_data):
    data = sorted(valid_data, key=lambda x: x["date"])
    if not data:
        return None

    max_drawdown = 0.0
    peak_nav = data[0]["nav"]
    trough_nav = data[0]["nav"]
    temp_peak = data[0]["nav"]

    for item in data:
        nav = item["nav"]
        if nav > temp_peak:
            temp_peak = nav
            
        drawdown = (temp_peak - nav) / temp_peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            peak_nav = temp_peak
            trough_nav = nav

    latest_nav = data[-1]["nav"]

    if max_drawdown == 0:
        recovery_rate = 100.0  
    elif peak_nav == trough_nav:
        recovery_rate = 0.0
    else:
        recovery_rate = ((latest_nav - trough_nav) / (peak_nav - trough_nav)) * 100.0

    rebound_gain = ((latest_nav - trough_nav) / trough_nav) * 100.0 if trough_nav > 0 else 0.0

    return {
        "peak_nav": peak_nav,
        "trough_nav": trough_nav,
        "latest_nav": latest_nav,
        "max_drawdown": max_drawdown * 100.0,
        "recovery_rate": recovery_rate,
        "rebound_gain": rebound_gain
    }

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="多源动态获取名称与回撤分析系统")
    parser.add_argument("--start", type=str, default=default_start)
    parser.add_argument("--end", type=str, default=today_str)
    parser.add_argument("--funds", nargs="+", default=DEFAULT_FUNDS)

    args = parser.parse_args()
    opener = get_direct_opener()

    print(f"\n======== 开始多源动态获取名称与深度分析 ========")
    print(f"统计时间区间: {args.start} 至 {args.end}")
    print(f"待处理基金数: {len(args.funds)} 只\n")

    header = (
        f"{'代码':<7} | "
        f"{'基金名称 (动态源获取)':<26} | "
        f"{'来源':<8} | "
        f"{'最高净值':<8} | "
        f"{'最低净值':<8} | "
        f"{'最新净值':<8} | "
        f"{'最大回撤':<9} | "
        f"{'修复程度':<9} | "
        f"{'自低点反弹'}"
    )
    print(header)
    print("-" * 115)

    for code in args.funds:
        # 实时动态从源获取名称，绝不写死
        fund_name = fetch_fund_name_from_source(opener, code)
        
        raw_data, source_name = fetch_fund_data_multisource(opener, code, args.start, args.end)
        
        if not raw_data:
            print(f"{code:<7} | {fund_name:<26} | {source_name:<8} | 无法获取历史数据")
            continue

        res = analyze_fund_metrics(raw_data)
        if not res:
            print(f"{code:<7} | {fund_name:<26} | {source_name:<8} | 净值数据不足")
            continue

        print(
            f"{code:<7} | "
            f"{fund_name:{chr(12288)}<20} | "  # 保持中文宽带对齐
            f"{source_name:<6} | "
            f"{res['peak_nav']:<8.4f} | "
            f"{res['trough_nav']:<8.4f} | "
            f"{res['latest_nav']:<8.4f} | "
            f"{res['max_drawdown']:<7.2f}% | "
            f"{res['recovery_rate']:<7.2f}% | "
            f"{res['rebound_gain']:<7.2f}%"
        )
        
        time.sleep(random.uniform(0.05, 0.1))

    print("-" * 115)

if __name__ == "__main__":
    main()