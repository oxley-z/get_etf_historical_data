import os
import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

# 1. 清理进程内失效的代理环境变量，避免连接本地死端口导致 ConnectionRefused
for proxy_key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(proxy_key, None)

# 通用请求头，防止部分数据源反爬阻断
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

def get_direct_opener():
    """构建绕过系统本地代理的底层网络连接池"""
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

opener = get_direct_opener()


# =====================================================================
# 通用解析工具
# =====================================================================
def fetch_from_yahoo_finance(symbol: str, timeout: int = 5) -> float:
    """通用源: Yahoo Finance Chart API v8"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with opener.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        result = data.get("chart", {}).get("result", [{}])[0]
        price = result.get("meta", {}).get("regularMarketPrice")
        
        # 若盘中点位为空，回溯最近一个有效收盘价
        if price is None:
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            valid_closes = [c for c in closes if c is not None]
            if valid_closes:
                price = valid_closes[-1]
        
        if price is not None:
            return round(float(price), 2)
    return 0.0


def fetch_from_cboe_quote(symbol: str, timeout: int = 5) -> float:
    """通用源: CBOE 官方延时行情接口"""
    # 格式通常为 _VIX.json, _VXN.json, _SKEW.json
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/quotes/{symbol}.json"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with opener.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        quote_data = data.get("data", {})
        price = quote_data.get("last_trade_price") or quote_data.get("current_price") or quote_data.get("close")
        if price is not None:
            return round(float(price), 2)
    return 0.0


# =====================================================================
# 指标 1: VIX 波动率指数
# =====================================================================
def get_vix() -> tuple[float, str]:
    # 源 1: Yahoo Finance (^VIX)
    try:
        val = fetch_from_yahoo_finance("^VIX")
        if val > 0:
            return val, "Yahoo Finance (^VIX)"
    except Exception:
        pass

    # 源 2: CBOE 官方接口 (_VIX)
    try:
        val = fetch_from_cboe_quote("_VIX")
        if val > 0:
            return val, "CBOE 官方 (_VIX)"
    except Exception:
        pass

    # 源 3: 新浪外盘指数/期货接口 (gb_$vix / hf_VX)
    try:
        url = "https://hq.sinajs.cn/list=gb_$vix"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            # 格式: var hq_str_gb_$vix="VIX指数,15.84,..."
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                if len(parts) > 1 and float(parts[1]) > 0:
                    return round(float(parts[1]), 2), "新浪财经 (gb_$vix)"
    except Exception:
        pass

    return 0.0, "失败(已兜底)"


# =====================================================================
# 指标 2: CNN 恐慌与贪婪指数 (Fear & Greed Index)
# =====================================================================
def get_cnn_fear_greed() -> tuple[float, str]:
    # 源 1: CNN Dataviz 官方数据端点
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            **DEFAULT_HEADERS,
            "Referer": "https://www.cnn.com/markets/fear-and-greed"
        })
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            score = data.get("fear_and_greed", {}).get("score")
            if score is not None:
                return round(float(score), 2), "CNN Dataviz 官方"
    except Exception:
        pass

    # 源 2: Alternative.me 情绪接口 (高可用备选)
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", [])
            if items and items[0].get("value") is not None:
                return round(float(items[0]["value"]), 2), "Alternative.me (情绪镜像)"
    except Exception:
        pass

    return 0.0, "失败(已兜底)"


# =====================================================================
# 指标 3: USD/CNY 汇率
# =====================================================================
def get_usd_cny() -> tuple[float, str]:
    # 源 1: 新浪外汇实时接口 (fx_susdcny)
    try:
        url = "https://hq.sinajs.cn/list=fx_susdcny"
        req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"})
        with opener.open(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            # 格式: var hq_str_fx_susdcny="16:00:00,7.1234,..."
            match = re.search(r'"([^"]+)"', content)
            if match:
                parts = match.group(1).split(",")
                # 通常第 2 位或第 9 位为当前实时汇率
                for idx in [1, 8]:
                    if len(parts) > idx and float(parts[idx]) > 0:
                        return round(float(parts[idx]), 4), "新浪外汇 (fx_susdcny)"
    except Exception:
        pass

    # 源 2: 开放免密汇率 API (open.er-api.com)
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rate = data.get("rates", {}).get("CNY")
            if rate is not None and float(rate) > 0:
                return round(float(rate), 4), "Open Exchange API"
    except Exception:
        pass

    # 源 3: Yahoo Finance (USDCNY=X)
    try:
        val = fetch_from_yahoo_finance("USDCNY=X")
        if val > 0:
            return round(val, 4), "Yahoo Finance (USDCNY=X)"
    except Exception:
        pass

    return 0.0, "失败(已兜底)"


# =====================================================================
# 指标 4: VXN 纳指100波动率指数
# =====================================================================
def get_vxn() -> tuple[float, str]:
    # 源 1: Yahoo Finance (^VXN)
    try:
        val = fetch_from_yahoo_finance("^VXN")
        if val > 0:
            return val, "Yahoo Finance (^VXN)"
    except Exception:
        pass

    # 源 2: CBOE 官方接口 (_VXN)
    try:
        val = fetch_from_cboe_quote("_VXN")
        if val > 0:
            return val, "CBOE 官方 (_VXN)"
    except Exception:
        pass

    return 0.0, "失败(已兜底)"


# =====================================================================
# 指标 5: SKEW 黑天鹅偏斜指数
# =====================================================================
def get_skew() -> tuple[float, str]:
    # 源 1: Yahoo Finance (^SKEW)
    try:
        val = fetch_from_yahoo_finance("^SKEW")
        if val > 0:
            return val, "Yahoo Finance (^SKEW)"
    except Exception:
        pass

    # 源 2: CBOE 官方接口 (_SKEW)
    try:
        val = fetch_from_cboe_quote("_SKEW")
        if val > 0:
            return val, "CBOE 官方 (_SKEW)"
    except Exception:
        pass

    return 0.0, "失败(已兜底)"


# =====================================================================
# 执行调度主函数
# =====================================================================
def fetch_all_macro_data() -> dict:
    print("=" * 60)
    print(f"正在多源获取宏观情绪与市场指标 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]...")
    print("=" * 60)

    fetch_tasks = [
        ("VIX", get_vix),
        ("CNN恐慌指数", get_cnn_fear_greed),
        ("USD/CNY", get_usd_cny),
        ("VXN", get_vxn),
        ("SKEW", get_skew),
    ]

    results = {}

    for name, fetch_func in fetch_tasks:
        try:
            val, source = fetch_func()
        except Exception:
            val, source = 0.0, "异常中断(已兜底)"

        results[name] = {
            "value": val,
            "source": source,
            "status": "成功" if val > 0 else "失败 (返回 0.0)"
        }
        
        status_icon = "✓" if val > 0 else "✗"
        print(f"[{status_icon}] {name:<10}: {val:<8} | 命中通道: {source}")

    return results


if __name__ == "__main__":
    macro_data = fetch_all_macro_data()

    print("\n" + "=" * 60)
    print("结构化导出数据 (Dict):")
    print(json.dumps(macro_data, ensure_ascii=False, indent=4))