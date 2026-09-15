import os
import json
import urllib.request
from http.cookiejar import CookieJar

for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

TARGET_INDICES = ["纳指100", "标普500", "沪深300", "科创50", "恒生科技"]

NAME_MAP = {
    "纳指100": ["纳斯达克100", "纳斯达克", "纳指100"],
    "标普500": ["标普500", "S&P500"],
    "沪深300": ["沪深300"],
    "科创50": ["科创50"],
    "恒生科技": ["恒生科技", "恒生科技指数"]
}

def get_danjuan_data():
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://danjuanfunds.com/djapi/v3/filter/fund"
    }

    try:
        init_req = urllib.request.Request("https://xueqiu.com", headers=headers)
        opener.open(init_req, timeout=5)
    except Exception:
        pass

    api_url = "https://danjuanfunds.com/djapi/index_eva/dj"
    req = urllib.request.Request(api_url, headers=headers)
    
    try:
        with opener.open(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("result_code") == 0:
                return data.get("data", {}).get("items", [])
    except Exception as e:
        print(f"Error fetching data: {e}")
    return []

def evaluate_status(pe_percentile):
    if pe_percentile is None:
        return "⚪ 暂无数据"
    pct = pe_percentile * 100
    if pct <= 20:
        return "🟢 极度低估"
    elif pct <= 40:
        return "🌱 低估"
    elif pct <= 60:
        return "🟡 适中"
    elif pct <= 80:
        return "🟠 偏高"
    else:
        return "🔴 高估"

def main():
    items = get_danjuan_data()
    eva_dict = {}
    for item in items:
        eva_dict[item.get("name", "").strip()] = item

    print("\n======== 数据源: danjuanfunds.com (蛋卷估值中心) ========")
    print("-" * 68)
    print(f"{'指数名称':<12} | {'当前PE(TTM)':<14} | {'历史分位值':<16} | {'估值状态'}")
    print("-" * 68)

    for target in TARGET_INDICES:
        matched = None
        aliases = NAME_MAP.get(target, [target])
        
        for alias in aliases:
            for k, v in eva_dict.items():
                if alias in k:
                    matched = v
                    break
            if matched:
                break

        if matched:
            pe_val = f"{matched.get('pe', 0.0):.2f}" if matched.get('pe') else "--"
            pct = matched.get("pe_percentile")
            pct_val = f"{pct * 100:.2f}%" if pct is not None else "--"
            status = evaluate_status(pct)
            print(f"{target:<14} | {pe_val:<16} | {pct_val:<19} | {status}")
        else:
            print(f"{target:<14} | {'未匹配':<16} | {'--':<19} | ⚪ 暂无数据")

    print("-" * 68)

if __name__ == "__main__":
    main()