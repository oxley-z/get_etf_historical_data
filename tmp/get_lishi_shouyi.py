#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取指定QDII基金的年度收益（按自然年）
数据来源：天天基金网
"""

import re
import json
import time
import requests
from datetime import datetime

# ==================== 基金列表 ====================
FUND_DICT = {
    "002891": "华夏移动互联混合(QDII)",
    "014002": "浦银全球智能科技(QDII)C",
    "006555": "浦银全球智能科技(QDII)A",
    "012922": "易方达全球成长精选混合(QDII)C",
    "000043": "嘉实美国(QDII)C",
    "018036": "长城全球新能源(QDII)C",
    "017731": "嘉实全球(QDII)C",
    "021277": "广发全球(QDII)C",
    "024239": "华夏全球科技(QDII)C",
    "015202": "汇添富全球(QDII)C",
    "018230": "易方达全球优质(QDII)C",
    "017654": "创金合信全球(QDII)C",
    "019156": "易方达全球配置(QDII)C",
    "021662": "国服亚洲(QDII)C",
    "018147": "建信新兴市场(QDII)C",
    "008254": "华宝致远(QDII)C",
    "022184": "富国全球(QDII)C",
    "017437": "华宝纳斯达克(QDII)C",
}

# ==================== 配置 ====================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "http://fund.eastmoney.com/",
}
REQUEST_TIMEOUT = 15
RETRY_TIMES = 3
RETRY_DELAY = 2  # 秒

# ==================== 核心函数 ====================

def fetch_fund_nav_data(fund_code: str) -> list | None:
    """
    从天天基金网获取基金的全部历史单位净值数据。

    接口返回一个 JS 文件，其中 Data_netWorthTrend 变量存储了
    每日的净值时间序列，格式为：
        Data_netWorthTrend = [
            {"x": 1577808000000, "y": 1.5234, "equityReturn": 0.65, ...},
            ...
        ]
    """
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                print(f"  [!] HTTP {resp.status_code}，第 {attempt} 次重试…")
                time.sleep(RETRY_DELAY)
                continue

            # 用正则提取 Data_netWorthTrend 的 JSON 数组
            match = re.search(
                r"Data_netWorthTrend\s*=\s*(\[\{.+?\}\]);",
                resp.text,
                re.DOTALL,
            )
            if not match:
                print(f"  [!] 未找到 Data_netWorthTrend，第 {attempt} 次重试…")
                time.sleep(RETRY_DELAY)
                continue

            raw = json.loads(match.group(1))
            return raw  # [{"x": timestamp_ms, "y": nav, ...}, ...]

        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"  [!] 请求/解析异常: {e}，第 {attempt} 次重试…")
            time.sleep(RETRY_DELAY)

    print(f"  [×] 基金 {fund_code} 数据获取失败，已跳过。")
    return None


def calc_annual_returns(nav_list: list) -> dict:
    """
    根据每日净值时间序列，计算每个自然年的收益率。

    年度收益率 = (年末最后一个交易日净值 / 上一年最后交易日净值 - 1) × 100%

    对于首个年份，使用该年第一个交易日净值作为期初值。
    """
    if not nav_list:
        return {}

    # 按时间戳排序（接口通常已排序，此处做一次保险）
    nav_list.sort(key=lambda d: d["x"])

    # 按年份分组 {year: [(ts, nav), ...]}
    year_data: dict[int, list] = {}
    for item in nav_list:
        ts = item["x"]
        nav = item.get("y")
        if nav is None:
            continue
        # 接口返回的是毫秒时间戳
        year = datetime.fromtimestamp(ts / 1000).year
        year_data.setdefault(year, []).append((ts, nav))

    sorted_years = sorted(year_data.keys())
    annual_returns = {}

    for i, year in enumerate(sorted_years):
        records = sorted(year_data[year], key=lambda x: x[0])
        end_nav = records[-1][1]

        if i == 0:
            # 首个年份：用该年第一个交易日的净值作为期初
            start_nav = records[0][1]
        else:
            # 非首个年份：用上一年最后一个交易日的净值作为期初
            prev_records = sorted(year_data[sorted_years[i - 1]], key=lambda x: x[0])
            start_nav = prev_records[-1][1]

        if start_nav and start_nav != 0:
            ret = (end_nav / start_nav - 1) * 100
            annual_returns[year] = round(ret, 2)

    return annual_returns


# ==================== 主流程 ====================

def main():
    print("=" * 70)
    print("  QDII 基金年度收益一览（数据来源：天天基金网）")
    print("=" * 70)

    all_results = {}

    for idx, (code, name) in enumerate(FUND_DICT.items(), 1):
        print(f"\n[{idx}/{len(FUND_DICT)}] 正在获取: {code} {name}")
        nav_data = fetch_fund_nav_data(code)
        if nav_data is None:
            all_results[code] = {"name": name, "returns": None}
            continue

        returns = calc_annual_returns(nav_data)
        all_results[code] = {"name": name, "returns": returns}
        print(f"  获取成功，共 {len(returns)} 个年度数据")
        time.sleep(0.5)  # 温和限速，避免被封

    # ---------- 输出结果 ----------
    print("\n" + "=" * 70)
    print("  年度收益率汇总（%）")
    print("=" * 70)

    # 收集所有出现过的年份，作为表头
    all_years = set()
    for r in all_results.values():
        if r["returns"]:
            all_years.update(r["returns"].keys())
    all_years = sorted(all_years)

    # 表头
    header = f"{'基金名称':<30}" + "".join(f"{y:>8}" for y in all_years)
    print(header)
    print("-" * len(header))

    # 逐行输出
    for code, info in all_results.items():
        name = info["name"]
        # 截断过长的名称
        display_name = name if len(name) <= 28 else name[:26] + "…"
        line = f"{display_name:<30}"
        if info["returns"]:
            for y in all_years:
                val = info["returns"].get(y)
                line += f"{val:>8.2f}" if val is not None else f"{'—':>8}"
        else:
            line += "  数据获取失败"
        print(line)

    print("-" * len(header))
    print(f"\n共处理 {len(all_results)} 只基金，数据截至最新交易日。")


if __name__ == "__main__":
    main()