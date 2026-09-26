import os
import json
import time
from datetime import datetime
import urllib.request
import urllib.parse
from collections import defaultdict

# ★ 如果在本地运行需要走代理翻墙，请注释掉下面这段代码；
# ★ 如果在 GitHub Actions (海外服务器) 运行，保留或注释均可。
# for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
#     os.environ.pop(env_var, None)

# 对应 Yahoo Finance 的标准代码与标的
TARGET_ASSETS = [
    {"code": "^NDX",  "symbol": "NDX",  "name": "纳斯达克100指数"},
    {"code": "^GSPC", "symbol": "SPX",  "name": "标普500指数"},
    {"code": "^SOX",  "symbol": "SOX",  "name": "费城半导体指数"},
    {"code": "SOXL",  "symbol": "SOXL", "name": "三倍做多半导体ETF-Direxion"},
    {"code": "XLK",   "symbol": "XLK",  "name": "信息科技行业ETF-SPDR"}
]

# 模拟完整的浏览器请求头，防止雅虎 403 Forbidden 拦截
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
    "Connection": "keep-alive"
}

DAILY_START_DATE = "2025-01-01"    # 每日净值 CSV 的起始日期
ANNUAL_START_YEAR = 2000           # 年度收益率的起始年份


def fetch_yahoo_kline(symbol_code, start_year=2000):
    """
    通过 Yahoo Finance v8 接口拉取从指定年份开始的历史日线数据。
    """
    # 计算起始时间戳 (例如 2000-01-01 00:00:00)
    period1 = int(time.mktime(time.strptime(f"{start_year}-01-01", "%Y-%m-%d")))
    period2 = int(time.time())

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol_code)}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )

    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    records = []

    # 直接使用 urllib 默认 opener（会自动挂载系统代理）
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        result = data.get("chart", {}).get("result", [])
        if not result:
            return records

        chart_data = result[0]
        timestamps = chart_data.get("timestamp", [])
        quote = chart_data.get("indicators", {}).get("quote", [{}])[0]

        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        for i in range(len(timestamps)):
            # 过滤节假日休市或异常的空点位
            if opens[i] is None or closes[i] is None:
                continue

            d_str = time.strftime("%Y-%m-%d", time.gmtime(timestamps[i]))
            records.append({
                "date": d_str,
                "open": float(opens[i]),
                "high": float(highs[i] or opens[i]),
                "low": float(lows[i] or opens[i]),
                "close": float(closes[i]),
                "volume": int(volumes[i] or 0)
            })

    records.sort(key=lambda x: x["date"])
    return records


def compute_annual_returns(records, start_year=2000):
    """
    根据日线数据计算每个自然年的收益率。
    - 首个年份：用该年第一个交易日的开盘价作为基准
    - 后续年份：用上一年最后一个交易日的收盘价作为基准
    """
    if not records:
        return []

    year_data = defaultdict(list)
    for r in records:
        year = int(r["date"][:4])
        if year >= start_year - 1:
            year_data[year].append(r)

    for year in year_data:
        year_data[year].sort(key=lambda x: x["date"])

    sorted_years = sorted(year_data.keys())
    annual_returns = []
    prev_year_close = None

    for year in sorted_years:
        year_records = year_data[year]
        first_rec = year_records[0]
        last_rec = year_records[-1]

        if prev_year_close is None:
            base_price = first_rec["open"]
        else:
            base_price = prev_year_close

        end_price = last_rec["close"]

        if year >= start_year and base_price and base_price > 0:
            ret = (end_price / base_price - 1) * 100.0
            annual_returns.append((year, ret))

        prev_year_close = end_price

    return annual_returns

def main():
    print("=" * 70)
    print(f" 每日净值: {DAILY_START_DATE} 至今")
    print(f" 年度收益率: {ANNUAL_START_YEAR} 年至今")
    print("=" * 70 + "\n")

    summary = []

    for asset in TARGET_ASSETS:
        code = asset["code"]
        symbol = asset["symbol"]
        name = asset["name"]

        print(f"正在拉取: {name} ({symbol}) ...", end=" ", flush=True)
        try:
            full_records = fetch_yahoo_kline(code, start_year=ANNUAL_START_YEAR)
            if not full_records:
                print("❌ 未获取到数据")
                continue

            # 2) 计算 2000 年至今完整年度收益率
            annual_returns = compute_annual_returns(full_records, start_year=ANNUAL_START_YEAR)

            # 3) 计算区间涨跌幅
            if daily_records:
                first_row = daily_records[0]
                last_row = daily_records[-1]
                cum_ret = ((last_row["close"] - first_row["open"]) / first_row["open"]) * 100.0
            else:
                first_row = last_row = None
                cum_ret = 0.0

            summary.append({
                "symbol": symbol,
                "name": name,
                "count": len(daily_records),
                "start_date": first_row["date"] if first_row else "--",
                "end_date": last_row["date"] if last_row else "--",
                "start_price": first_row["open"] if first_row else 0.0,
                "latest_price": last_row["close"] if last_row else 0.0,
                "cum_return": cum_ret,
                "annual_returns": annual_returns,
                "file": file_path or "--"
            })

            print(f"✅ 完成 (日线 {len(daily_records)} 条, 年度 {len(annual_returns)} 个, 文件: {file_path})")

            # 打印年度收益率
            if annual_returns:
                print(f"     年度收益率 (共 {len(annual_returns)} 年):")
                for year, ret in annual_returns:
                    print(f"       {year}年: {ret:+.2f}%")
            else:
                print("     年度收益率: 无数据")

        except Exception as e:
            print(f"❌ 失败: {e}")

        time.sleep(0.5)

    # ===== 汇总表 =====
    print("\n" + "=" * 70)
    print(f"{'代码':<8} | {'标的名称':<14} | {'起始点位':<10} | {'最新点位':<10} | {'区间涨跌幅':<10}")
    print("-" * 70)
    for s in summary:
        ret_str = f"{s['cum_return']:+.2f}%"
        print(f"{s['symbol']:<8} | {s['name']:<14} | {s['start_price']:<10.2f} | {s['latest_price']:<10.2f} | {ret_str:<10}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()