"""
天天基金 · 纳指基金特色数据抓取（v2，不保存 CSV）
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

FUNDS = {
    "017091": "景顺长城纳斯达克科技ETF联接(QDII)A",
    "016055": "博时纳斯达克100ETF发起式联接(QDII)A",
    "160213": "国泰纳斯达克100指数(QDII)",
    "019172": "摩根纳斯达克100指数(QDII)A",
    "019441": "万家纳斯达克100指数发起式(QDII)A",
    "018043": "天弘纳斯达克100指数发起(QDII)A",
    "019547": "招商纳斯达克100ETF发起式联接(QDII)A",
    "016532": "嘉实纳斯达克100ETF发起联接(QDII)A",
    "006373": "国富全球科技",
    "006555": "浦银全球",
    "012920": "易方达全球成长",
    "002891": "华夏移动互联",
    "021662": "国富亚洲科技",
    "161128": "易方达标普信息技术",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fundf10.eastmoney.com/",
}

EMPTY = {
    "跟踪指数": "", "年化跟踪误差": "", "同类平均": "", "截止日期": "",
    "标准差_近1年": "", "标准差_近2年": "", "标准差_近3年": "",
    "夏普比率_近1年": "", "夏普比率_近2年": "", "夏普比率_近3年": "",
}


def _clean(s):
    if s is None:
        return ""
    return re.sub(r"[\s\u3000]+", "", s)


def _find_deadline_after(table, max_up=8):
    """从 table 出发，往后 / 往上找最近的 '截止至：YYYY-MM-DD'"""
    node = table
    for _ in range(max_up):
        sib = node.find_next_sibling()
        while sib is not None:
            txt = sib.get_text() if hasattr(sib, "get_text") else str(sib)
            m = re.search(r"截止至[：:]\s*(\d{4}-\d{2}-\d{2})", txt)
            if m:
                return m.group(1)
            sib = sib.find_next_sibling()
        node = node.parent
        if node is None:
            break
    return ""


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    r = dict(EMPTY)

    for table in soup.find_all("table"):
        rows_data = []
        for tr in table.find_all("tr"):
            tds = [_clean(td.get_text()) for td in tr.find_all(["td", "th"])]
            if tds:
                rows_data.append(tds)
        if not rows_data:
            continue
        flat = "".join("".join(tds) for tds in rows_data)

        # ---------- 指数基金指标表 ----------
        if "跟踪指数" in flat and "年化跟踪误差" in flat:
            for tds in rows_data:
                if len(tds) < 3:
                    continue
                if tds[0] == "跟踪指数":          # 表头行，跳过
                    continue
                if tds[1].endswith("%") and tds[2].endswith("%"):
                    r["跟踪指数"] = tds[0]
                    r["年化跟踪误差"] = tds[1]
                    r["同类平均"] = tds[2]
                    break
            if not r["截止日期"]:
                r["截止日期"] = _find_deadline_after(table)
            continue

        # ---------- 基金风险指标表 ----------
        has_std = any(tds and tds[0] == "标准差" for tds in rows_data)
        has_sharpe = any(tds and tds[0] == "夏普比率" for tds in rows_data)
        if has_std or has_sharpe:
            for tds in rows_data:
                if len(tds) < 4:
                    continue
                if tds[0] == "标准差":
                    r["标准差_近1年"] = tds[1]
                    r["标准差_近2年"] = tds[2]
                    r["标准差_近3年"] = tds[3]
                elif tds[0] == "夏普比率":
                    r["夏普比率_近1年"] = tds[1]
                    r["夏普比率_近2年"] = tds[2]
                    r["夏普比率_近3年"] = tds[3]

    return r


def fetch_fund_features(fund_code, retries=3, save_debug=True):
    url = f"https://fundf10.eastmoney.com/tsdata_{fund_code}.html"
    last_html = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            last_html = resp.text
            result = parse_page(resp.text)
            if result["年化跟踪误差"] or result["标准差_近1年"]:
                return result
            print(f"  [第{attempt}次] {fund_code} 未解析到数据，HTML 长度 {len(resp.text)}")
            time.sleep(2)
        except requests.RequestException as e:
            print(f"  [第{attempt}次] {fund_code} 请求异常: {e}")
            time.sleep(3)

    if save_debug and last_html:
        os.makedirs("debug_html", exist_ok=True)
        path = f"debug_html/{fund_code}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(last_html)
        print(f"  [debug] 已保存 HTML 到 {path}")

    return dict(EMPTY)


def main():
    print("天天基金 · 纳指基金特色数据抓取（v2）")
    print(f"抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    rows = []
    for code, name in FUNDS.items():
        print(f"\n抓取 [{code}] {name} ...")
        d = fetch_fund_features(code)
        print(f"  跟踪指数     : {d['跟踪指数'] or '—'}")
        print(f"  年化跟踪误差 : {d['年化跟踪误差'] or '—'}   同类平均: {d['同类平均'] or '—'}")
        print(f"  标准差(1/2/3): {d['标准差_近1年'] or '—'} / {d['标准差_近2年'] or '—'} / {d['标准差_近3年'] or '—'}")
        print(f"  夏普  (1/2/3): {d['夏普比率_近1年'] or '—'} / {d['夏普比率_近2年'] or '—'} / {d['夏普比率_近3年'] or '—'}")
        print(f"  截止日期     : {d['截止日期'] or '—'}")
        rows.append({"代码": code, "名称": name, **d})

    df = pd.DataFrame(rows)

    # 按年化跟踪误差升序
    def key(x):
        try:
            return float(str(x).replace("%", ""))
        except Exception:
            return 999
    df["_sort"] = df["年化跟踪误差"].apply(key)
    df = df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)

    # 精简输出
    show = ["代码", "名称", "跟踪指数", "年化跟踪误差", "同类平均", "截止日期"]
    print("\n" + "=" * 90)
    print("年化跟踪误差汇总（按数值升序）")
    print("=" * 90)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    pd.set_option("display.unicode.east_asian_width", True)
    print(df[show].to_string(index=False))

    # 完整输出
    print("\n" + "=" * 90)
    print("完整特色数据")
    print("=" * 90)
    print(df.to_string(index=False))

    return df


if __name__ == "__main__":
    main()