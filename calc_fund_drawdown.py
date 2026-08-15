import os
import re
import json
import time
import random
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# 进程内强制清除系统代理
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

DEFAULT_FUNDS = [
    "002891", "014002", "012922", "021662", "539002", "021842", "018036",
    "008254", "017731", "016665", "018230", "021277", "005698", "501312",
    "017654", "022184", "017437", "017145", "016702", "016823", "019156"
]

def get_direct_opener():
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def fetch_from_eastmoney(opener, code, start_date, end_date):
    """【源1】天天基金网"""
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
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9"
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
    """【源2】新浪财经"""
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
    # 优先天天基金
    data = fetch_from_eastmoney(opener, code, start_date, end_date)
    if data:
        return data, "天天基金"
    
    # 降级新浪财经
    data = fetch_from_sina(opener, code, start_date, end_date)
    if data:
        return data, "新浪财经"
        
    return None, "全部失败"

def analyze_drawdown_and_recovery(valid_data):
    data = sorted(valid_data, key=lambda x: x["date"])
    if not data:
        return None

    max_drawdown = 0.0
    peak_nav = data[0]["nav"]
    peak_date = data[0]["date"]
    trough_nav = data[0]["nav"]
    trough_date = data[0]["date"]

    temp_peak = data[0]["nav"]
    temp_peak_date = data[0]["date"]

    for item in data:
        nav = item["nav"]
        date = item["date"]
        
        if nav > temp_peak:
            temp_peak = nav
            temp_peak_date = date
            
        drawdown = (temp_peak - nav) / temp_peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            peak_nav = temp_peak
            peak_date = temp_peak_date
            trough_nav = nav
            trough_date = date

    latest_nav = data[-1]["nav"]
    latest_date = data[-1]["date"]

    if max_drawdown == 0:
        recovery_rate = 100.0  
    elif peak_nav == trough_nav:
        recovery_rate = 0.0
    else:
        recovery_rate = ((latest_nav - trough_nav) / (peak_nav - trough_nav)) * 100.0

    return {
        "peak_nav": peak_nav,
        "trough_nav": trough_nav,
        "latest_nav": latest_nav,
        "max_drawdown": max_drawdown * 100.0,
        "recovery_rate": recovery_rate
    }

def main():
    # 动态获取当前实际日期，避免写死未到的日期导致查不到数据
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default=default_start, help="起始日期")
    parser.add_argument("--end", type=str, default=today_str, help="截止日期")
    parser.add_argument("--funds", nargs="+", default=DEFAULT_FUNDS)

    args = parser.parse_args()
    opener = get_direct_opener()

    print(f"\n======== 开始数据抓取与分析 ========")
    print(f"统计区间: {args.start} 至 {args.end}")
    print(f"待处理基金: {len(args.funds)} 只\n")

    header = f"{'代码':<8} | {'来源':<8} | {'最高净值':<8} | {'最低净值':<8} | {'最新净值':<8} | {'最大回撤(%)':<10} | {'修复程度(%)':<10}"
    print(header)
    print("-" * len(header))

    for code in args.funds:
        raw_data, source_name = fetch_fund_data_multisource(opener, code, args.start, args.end)
        
        if not raw_data:
            print(f"{code:<8} | {source_name:<8} | 无法获取有效历史数据")
            continue

        res = analyze_drawdown_and_recovery(raw_data)
        if not res:
            print(f"{code:<8} | {source_name:<8} | 净值序列不足")
            continue

        print(
            f"{code:<8} | "
            f"{source_name:<8} | "
            f"{res['peak_nav']:<8.4f} | "
            f"{res['trough_nav']:<8.4f} | "
            f"{res['latest_nav']:<8.4f} | "
            f"{res['max_drawdown']:<9.2f}% | "
            f"{res['recovery_rate']:<9.2f}%"
        )
        time.sleep(random.uniform(0.05, 0.1))

    print("-" * len(header))

if __name__ == "__main__":
    main()