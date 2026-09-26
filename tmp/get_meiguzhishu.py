import os
import re
import json
import time
from datetime import datetime
import urllib.request
import urllib.parse
from collections import defaultdict

# 1. 进程级清理系统残留代理
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

TARGET_ASSETS = [
    {"code": ".ndx", "symbol": "NDX", "name": "纳斯达克100指数"},
    {"code": ".inx", "symbol": "SPX", "name": "标普500指数"},
    {"code": ".sox", "symbol": "SOX", "name": "费城半导体指数"},
    {"code": "soxl", "symbol": "SOXL", "name": "三倍做多半导体ETF-Direxion"},
    {"code": "xlk",  "symbol": "XLK",  "name": "信息科技行业ETF-SPDR"}
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
    "Accept": "*/*"
}

# ★ 两个不同的起始日期
DAILY_START_DATE = "2025-01-01"    # 每日净值 CSV 的起始日期
ANNUAL_START_YEAR = 2000           # 年度收益率的起始年份


def get_direct_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_sina_us_kline(opener, symbol_code, start_date_str="2000-01-01"):
    """
    通过新浪美股日 K 线接口抓取历史数据。
    ★ 注意：这里传入较早的 start_date_str（如 2000-01-01），
       一次性拿回完整历史，后续再在内存里切分。
    """
    callback_name = "US_KLINE_CB"
    url = (
        f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/{callback_name}"
        f"/US_MinKService.getDailyK?symbol={urllib.parse.quote(symbol_code)}"
    )

    req = urllib.request.Request(url, headers=HEADERS)
    records = []

    with opener.open(req, timeout=15) as resp:
        content = resp.read().decode("gbk", errors="ignore")
        match = re.search(r'\((\[.*\])\)', content)
        if not match:
            return records

        raw_list = json.loads(match.group(1))
        for item in raw_list:
            d_str = item.get("d")
            if d_str and d_str >= start_date_str:
                try:
                    records.append({
                        "date": d_str,
                        "open": float(item.get("o", 0.0)),
                        "high": float(item.get("h", 0.0)),
                        "low": float(item.get("l", 0.0)),
                        "close": float(item.get("c", 0.0)),
                        "volume": int(float(item.get("v", 0)))
                    })
                except (ValueError, TypeError):
                    continue

    records.sort(key=lambda x: x["date"])
    return records


def compute_annual_returns(records, start_year=2000):
    """
    根据日线数据计算每个自然年的收益率（仅保留 start_year 及以后的年份）。
    规则：
      - 首个年份（start_year）：用该年第一个交易日的开盘价作为基准
      - 后续年份：用上一年最后一个交易日的收盘价作为基准
    返回列表: [(年份, 收益率%), ...]
    """
    if not records:
        return []

    year_data = defaultdict(list)
    for r in records:
        year = int(r["date"][:4])
        if year >= start_year - 1:      # 多保留一年，便于计算首年基准
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
            base_price = first_rec["open"]    # 首年用第一个交易日开盘价
        else:
            base_price = prev_year_close       # 其余年份用上年末收盘价

        end_price = last_rec["close"]

        if year >= start_year and base_price and base_price > 0:
            ret = (end_price / base_price - 1) * 100.0
            annual_returns.append((year, ret))

        prev_year_close = end_price

    return annual_returns


def save_to_csv(symbol, name, records, start_date_str, out_dir="market_data"):
    """保存指定日期区间内的日线数据到 CSV。"""
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    filtered = [r for r in records if r["date"] >= start_date_str]
    if not filtered:
        return None

    filename = os.path.join(out_dir, f"{symbol}_{name}_2025_至今.csv")
    with open(filename, "w", encoding="utf-8-sig") as f:
        f.write("日期,开盘点位,最高点位,最低点位,收盘点位,成交量\n")
        for r in filtered:
            f.write(f"{r['date']},{r['open']:.2f},{r['high']:.2f},{r['low']:.2f},{r['close']:.2f},{r['volume']}\n")
    return filename, filtered


def main():
    opener = get_direct_opener()

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
            # ★ 一次性拉取从 ANNUAL_START_YEAR 开始的完整历史
            full_records = fetch_sina_us_kline(opener, code, f"{ANNUAL_START_YEAR}-01-01")
            if not full_records:
                print("❌ 未获取到数据")
                continue

            # 1) 每日净值 CSV：只取 2025-01-01 之后
            csv_result = save_to_csv(symbol, name, full_records, DAILY_START_DATE)
            if csv_result:
                file_path, daily_records = csv_result
            else:
                file_path, daily_records = None, []

            # 2) 年度收益率：基于全量历史计算
            annual_returns = compute_annual_returns(full_records, start_year=ANNUAL_START_YEAR)

            # 3) 区间涨跌幅：仍以 2025-01-01 后的数据计算（用于汇总表）
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