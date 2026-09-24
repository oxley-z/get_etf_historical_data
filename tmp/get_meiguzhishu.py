import os
import re
import json
import time
from datetime import datetime
import urllib.request
import urllib.parse

# 1. 进程级清理系统残留代理，防止本地代理握手异常
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

# 目标品种对应新浪美股代码：
# 新浪接口：指数与普通 ETF 统一采用全小写 ticker (标普500为 .inx，纳指100为 .ndx)
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

def get_direct_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def fetch_sina_us_kline(opener, symbol_code, start_date_str="2025-01-01"):
    """
    通过新浪美股日 K 线接口抓取历史数据并过滤起始日期
    返回字段: 日期, 开盘价, 最高价, 最低价, 收盘价, 成交量
    """
    callback_name = "US_KLINE_CB"
    url = (
        f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/{callback_name}"
        f"/US_MinKService.getDailyK?symbol={urllib.parse.quote(symbol_code)}"
    )
    
    req = urllib.request.Request(url, headers=HEADERS)
    records = []
    
    with opener.open(req, timeout=10) as resp:
        content = resp.read().decode("gbk", errors="ignore")
        match = re.search(r'\((\[.*\])\)', content)
        if not match:
            return records
            
        raw_list = json.loads(match.group(1))
        for item in raw_list:
            # 格式: {"d": "2025-01-02", "o": "...", "h": "...", "l": "...", "c": "...", "v": "..."}
            d_str = item.get("d")
            if d_str and d_str >= start_date_str:
                records.append({
                    "date": d_str,
                    "open": float(item.get("o", 0.0)),
                    "high": float(item.get("h", 0.0)),
                    "low": float(item.get("l", 0.0)),
                    "close": float(item.get("c", 0.0)),
                    "volume": int(float(item.get("v", 0)))
                })
                
    records.sort(key=lambda x: x["date"])
    return records

def save_to_csv(symbol, name, records, out_dir="market_data"):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    filename = os.path.join(out_dir, f"{symbol}_{name}_2025_至今.csv")
    with open(filename, "w", encoding="utf-8-sig") as f:
        f.write("日期,开盘点位,最高点位,最低点位,收盘点位,成交量\n")
        for r in records:
            f.write(f"{r['date']},{r['open']:.2f},{r['high']:.2f},{r['low']:.2f},{r['close']:.2f},{r['volume']}\n")
    return filename

def main():
    opener = get_direct_opener()
    start_date = "2025-01-01"
    
    print("=" * 70)
    print(f" 获取历史数据 ({start_date} 至今) - 新浪财经接口")
    print("=" * 70 + "\n")
    
    summary = []
    
    for asset in TARGET_ASSETS:
        code = asset["code"]
        symbol = asset["symbol"]
        name = asset["name"]
        
        print(f"正在拉取: {name} ({symbol}) ...", end=" ", flush=True)
        try:
            records = fetch_sina_us_kline(opener, code, start_date)
            if not records:
                print("❌ 未获取到数据")
                continue
                
            file_path = save_to_csv(symbol, name, records)
            first_row = records[0]
            last_row = records[-1]
            cum_ret = ((last_row["close"] - first_row["open"]) / first_row["open"]) * 100.0
            
            summary.append({
                "symbol": symbol,
                "name": name,
                "count": len(records),
                "start_date": first_row["date"],
                "end_date": last_row["date"],
                "start_price": first_row["open"],
                "latest_price": last_row["close"],
                "cum_return": cum_ret,
                "file": file_path
            })
            print(f"✅ 完成 (共 {len(records)} 个交易日, 文件: {file_path})")
            
        except Exception as e:
            print(f"❌ 失败: {e}")
            
        time.sleep(0.3)

    print("\n" + "=" * 70)
    print(f"{'代码':<8} | {'标的名称':<14} | {'起始点位':<10} | {'最新点位':<10} | {'区间涨跌幅':<10}")
    print("-" * 70)
    for s in summary:
        ret_str = f"{s['cum_return']:+.2f}%"
        print(f"{s['symbol']:<8} | {s['name']:<14} | {s['start_price']:<10.2f} | {s['latest_price']:<10.2f} | {ret_str:<10}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()