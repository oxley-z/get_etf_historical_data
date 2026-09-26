import os
import re
import json
import time
import argparse
import urllib.request
from collections import defaultdict
from datetime import datetime

# 1. 强制清理环境变量中的系统代理，杜绝 VPN/代理导致的握手失败与 403[cite: 1, 6]
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

# 目标美股 ETF 及指数代码映射 (新浪财经接口 ticker 格式)
DEFAULT_TARGETS = {
    "QQQ": {"name": "纳斯达克100 ETF-Invesco", "sina_code": "QQQ"},
    "SPY": {"name": "标普500 ETF-SPDR", "sina_code": "SPY"},
    "IVV": {"name": "标普500 ETF-iShares", "sina_code": "IVV"},
    "IVW": {"name": "标普500成长型 ETF-iShares", "sina_code": "IVW"},
    "VOO": {"name": "标普500 ETF-Vanguard", "sina_code": "VOO"},
    "SMH": {"name": "半导体 ETF-VanEck", "sina_code": "SMH"},
    "COMP": {"name": "纳斯达克综合指数", "sina_code": ".IXIC"},  # COMP 对应美股纳指代码 .IXIC
    "VGT": {"name": "信息科技 ETF-Vanguard", "sina_code": "VGT"},
    "ARKW": {"name": "下一代互联网 ETF-ARK", "sina_code": "ARKW"},
    "DIA": {"name": "道琼斯指数 ETF-SPDR", "sina_code": "DIA"},
    "XLK": {"name": "科技行业 ETF-SPDR", "sina_code": "XLK"}
}

def get_direct_opener():
    """创建免代理的直接网络连接"""
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def fetch_sina_us_kline(opener, symbol_code):
    """
    通过新浪财经美股日K线接口免鉴权拉取历史全量日度净值/收盘序列[cite: 1]
    """
    url = f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/IO.XSRV2.CallbackList['d_{symbol_code}']/US_MinKService.getDailyK?symbol={symbol_code}&___qn=3"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=10) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            match = re.search(r'CallbackList\[\'[^\']+\'\]\((.*)\);', content)
            if not match:
                return []
            
            raw_data = json.loads(match.group(1))
            if not isinstance(raw_data, list):
                return []

            records = []
            for item in raw_data:
                records.append({
                    "date": item["d"],
                    "open": float(item["o"]),
                    "high": float(item["h"]),
                    "low": float(item["l"]),
                    "close": float(item["c"]),
                    "volume": float(item["v"])
                })
            records.sort(key=lambda x: x["date"])
            return records
    except Exception as e:
        print(f"  ❌ 请求异常: {e}")
        return []

def aggregate_yearly_metrics(records):
    """按自然年度聚合计算年末净值、最高/最低及年度收益率"""
    if not records:
        return []

    year_map = defaultdict(list)
    for r in records:
        year = r["date"].split("-")[0]
        year_map[year].append(r)

    years = sorted(year_map.keys())
    annual_summary = []
    prev_close = None

    for yr in years:
        bars = year_map[yr]
        first_bar = bars[0]
        last_bar = bars[-1]

        yr_high = max(b["high"] for b in bars)
        yr_low = min(b["low"] for b in bars)
        
        # 成立首年以首日开盘价为基准；后续年度以上一年末收盘净值为基准
        base_nav = prev_close if prev_close is not None else first_bar["open"]
        annual_return = ((last_bar["close"] - base_nav) / base_nav) * 100.0 if base_nav > 0 else 0.0

        annual_summary.append({
            "year": yr,
            "end_date": last_bar["date"],
            "year_end_nav": round(last_bar["close"], 4),
            "year_high": round(yr_high, 4),
            "year_low": round(yr_low, 4),
            "annual_return_pct": round(annual_return, 2),
            "is_inception_year": (prev_close is None)
        })
        prev_close = last_bar["close"]

    return annual_summary

def print_terminal_annual_table(ticker, name, annual_summary):
    """在终端格式化输出单只标的的历年数据表格"""
    print(f"\n==================== 【{ticker}】 {name} 历年收益及净值统计 ====================")
    table_header = f"{'年份':<6} | {'年末日期':<10} | {'年末净值/点位':<14} | {'年内最高':<10} | {'年内最低':<10} | {'年度收益率(%)':<14} | {'备注'}"
    print("-" * len(table_header))
    print(table_header)
    print("-" * len(table_header))

    for row in annual_summary:
        ret_str = f"{row['annual_return_pct']:+8.2f}%"
        remark = "成立/首年统计" if row["is_inception_year"] else ""
        print(
            f"{row['year']:<6} | "
            f"{row['end_date']:<10} | "
            f"{row['year_end_nav']:<14.2f} | "
            f"{row['year_high']:<10.2f} | "
            f"{row['year_low']:<10.2f} | "
            f"{ret_str:<14} | "
            f"{remark}"
        )
    print("-" * len(table_header))

def main():
    parser = argparse.ArgumentParser(description="获取美股 ETF 历年净值并在终端输出表格同时保存为本地 JSON")
    parser.add_argument("--out", type=str, default="us_etf_nav_data.json", help="输出本地 JSON 文件名 (默认: us_etf_nav_data.json)")
    args = parser.parse_args()

    opener = get_direct_opener()
    print("\n>>>>>>>> 开始获取美股 ETF 历年净值与表现数据 <<<<<<<<")
    print(f"监测标的数: {len(DEFAULT_TARGETS)} 只\n")

    output_payload = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(DEFAULT_TARGETS),
            "source": "Sina Finance US Stock Kline API"
        },
        "data": {}
    }

    for ticker, info in DEFAULT_TARGETS.items():
        name = info["name"]
        sina_code = info["sina_code"]

        print(f"正在拉取 {ticker} ({name}) 数据...", end=" ", flush=True)
        records = fetch_sina_us_kline(opener, sina_code)
        
        if not records:
            print("❌ 获取数据失败")
            continue

        print(f"✅ 获取成功 (共计 {len(records)} 个交易日)")
        annual_summary = aggregate_yearly_metrics(records)

        # 1. 终端打印该标的的历年数据
        print_terminal_annual_table(ticker, name, annual_summary)

        # 2. 存入 JSON 字典结构
        output_payload["data"][ticker] = {
            "name": name,
            "sina_symbol": sina_code,
            "start_date": records[0]["date"],
            "latest_date": records[-1]["date"],
            "latest_nav": records[-1]["close"],
            "yearly_performance": annual_summary,
            "daily_nav_history": records
        }
        time.sleep(0.1)

    # 3. 本地 JSON 持久化写入
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"\n💾 全部历年数据与每日净值信息已写入本地文件: {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()