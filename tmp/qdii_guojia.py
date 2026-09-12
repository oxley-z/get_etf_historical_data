# -*- coding: utf-8 -*-

import re
import requests


# ============================================================
# 基金列表
# ============================================================

FUNDS = {
    "002891": "华夏移动互联混合(QDII)",
    "014002": "浦银全球智能科技(QDII)C",
    "006555": "浦银全球智能科技(QDII)A",
    "012922": "易方达全球成长精选混合(QDII)C",
}


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fund.eastmoney.com/",
    "Accept": "application/json,text/plain,*/*",
}


session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 1. 获取基金定期报告列表
# ============================================================

def get_report_list(code):

    url = "https://api.fund.eastmoney.com/f10/JJGG"

    params = {
        "fundcode": code,
        "pageIndex": 1,
        "pageSize": 50,
        "type": 3,
    }

    r = session.get(
        url,
        params=params,
        timeout=20,
    )

    r.raise_for_status()

    data = r.json()

    if not data.get("Data"):
        return []

    return data["Data"]


# ============================================================
# 2. 找最新中期报告
# ============================================================

def find_latest_report(code):

    reports = get_report_list(code)

    if not reports:
        print("    没有获取到报告列表")
        return None

    # --------------------------------------------------------
    # 只找中期报告
    # --------------------------------------------------------

    candidates = []

    for item in reports:

        title = item.get(
            "TITLE",
            ""
        )

        publish_date = item.get(
            "PUBLISHDATEDesc",
            ""
        )

        report_id = item.get(
            "ID",
            ""
        )

        # 排除“中期报告摘要”
        if (
            "中期报告" in title
            and "摘要" not in title
        ):

            candidates.append(
                {
                    "title": title,
                    "date": publish_date,
                    "id": report_id,
                }
            )

    if not candidates:
        print(
            "    没有找到中期报告，尝试寻找第2季度报告"
        )

        for item in reports:

            title = item.get(
                "TITLE",
                ""
            )

            if (
                "第2季度报告" in title
                and "摘要" not in title
            ):

                candidates.append(
                    {
                        "title": title,
                        "date": item.get(
                            "PUBLISHDATEDesc",
                            ""
                        ),
                        "id": item.get(
                            "ID",
                            ""
                        ),
                    }
                )

    if not candidates:
        return None

    # --------------------------------------------------------
    # 按日期倒序
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: x["date"],
        reverse=True,
    )

    return candidates[0]


# ============================================================
# 3. 获取报告正文
# ============================================================

def get_report_content(report_id):

    url = (
        "https://np-cnotice-fund.eastmoney.com/"
        "api/content/ann"
    )

    params = {
        "client_source": "web_fund",
        "show_all": "1",
        "art_code": report_id,
    }

    r = session.get(
        url,
        params=params,
        timeout=30,
    )

    r.raise_for_status()

    data = r.json()

    if not data.get("data"):
        return ""

    return data["data"].get(
        "notice_content",
        ""
    )


# ============================================================
# 4. 找国家配置章节
# ============================================================

def get_country_section(text):

    patterns = [
        "期末在各个国家（地区）证券市场的权益投资分布",
        "期末在各个国家（地区）证券市场的股票及存托凭证投资分布",
        "报告期末在各个国家（地区）证券市场的股票及存托凭证投资分布",

        # 有些报告使用半角括号
        "期末在各个国家(地区)证券市场的权益投资分布",
        "期末在各个国家(地区)证券市场的股票及存托凭证投资分布",
        "报告期末在各个国家(地区)证券市场的股票及存托凭证投资分布",
    ]

    start = -1
    matched = None

    for pattern in patterns:

        pos = text.find(pattern)

        if pos >= 0:

            start = pos
            matched = pattern

            break

    if start < 0:

        return ""

    print(
        f"    找到章节：{matched}"
    )

    section = text[start:]

    # --------------------------------------------------------
    # 找下一章节
    # --------------------------------------------------------

    stop_patterns = [
        "期末按行业分类的权益投资组合",
        "期末按行业分类的股票及存托凭证投资组合",
        "报告期末按行业分类的股票及存托凭证投资组合",
        "期末按行业分类",
        "报告期末按行业分类",
    ]

    end = len(section)

    for pattern in stop_patterns:

        pos = section.find(pattern)

        if pos > 100:

            end = min(
                end,
                pos
            )

    return section[:end]


# ============================================================
# 5. 国家名称
# ============================================================

COUNTRIES = [
    "中国内地",
    "中国香港",
    "中国台湾",
    "中国大陆",
    "美国",
    "日本",
    "韩国",
    "新加坡",
    "荷兰",
    "英国",
    "法国",
    "德国",
    "瑞士",
    "加拿大",
    "澳大利亚",
    "新西兰",
    "印度",
    "巴西",
    "以色列",
    "丹麦",
    "瑞典",
    "芬兰",
    "意大利",
    "西班牙",
    "爱尔兰",
    "比利时",
    "卢森堡",
    "挪威",
    "奥地利",
    "葡萄牙",
    "马来西亚",
    "泰国",
    "印度尼西亚",
    "越南",
    "菲律宾",
    "墨西哥",
]


# ============================================================
# 6. 解析国家配置
# ============================================================

def parse_country_data(section):

    results = []

    # --------------------------------------------------------
    # 把 HTML 标签去掉
    # --------------------------------------------------------

    section = re.sub(
        r"<[^>]+>",
        " ",
        section
    )

    # HTML实体
    section = (
        section
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
    )

    # --------------------------------------------------------
    # 统一空白
    # --------------------------------------------------------

    section = re.sub(
        r"[ \t\r]+",
        " ",
        section
    )

    # --------------------------------------------------------
    # 国家 + 金额 + 比例
    #
    # 支持：
    #
    # 美国 2,572,748,883.45 63.23
    #
    # 以及：
    #
    # 美国
    # 2,572,748,883.45
    # 63.23
    # --------------------------------------------------------

    for country in COUNTRIES:

        pattern = (
            rf"{re.escape(country)}"
            rf"\s*"
            rf"([\d,]+\.\d+)"
            rf"\s*"
            rf"(\d+(?:\.\d+)?)"
        )

        match = re.search(
            pattern,
            section
        )

        if not match:
            continue

        value = float(
            match.group(1)
            .replace(",", "")
        )

        ratio = float(
            match.group(2)
        )

        results.append(
            {
                "country": country,
                "value": value,
                "ratio": ratio,
            }
        )

    # --------------------------------------------------------
    # 防止重复
    # --------------------------------------------------------

    unique = {}

    for item in results:

        unique[
            item["country"]
        ] = item

    results = list(
        unique.values()
    )

    # --------------------------------------------------------
    # 按占比从高到低
    # --------------------------------------------------------

    results.sort(
        key=lambda x: x["ratio"],
        reverse=True,
    )

    return results


# ============================================================
# 7. 单只基金
# ============================================================

def process_fund(code):

    print()
    print("=" * 72)

    print(
        f"{code}  {FUNDS[code]}"
    )

    # --------------------------------------------------------
    # 找报告
    # --------------------------------------------------------

    try:

        report = find_latest_report(
            code
        )

    except Exception as e:

        print(
            f"    获取报告列表失败：{e}"
        )

        return

    if not report:

        print(
            "    ❌ 没有找到最新中期报告"
        )

        return

    print(
        f"    报告：{report['title']}"
    )

    print(
        f"    日期：{report['date']}"
    )

    print(
        f"    ID：{report['id']}"
    )

    # --------------------------------------------------------
    # 获取报告正文
    # --------------------------------------------------------

    try:

        content = get_report_content(
            report["id"]
        )

    except Exception as e:

        print(
            f"    获取报告正文失败：{e}"
        )

        return

    if not content:

        print(
            "    ❌ 报告正文为空"
        )

        return

    # --------------------------------------------------------
    # 找国家配置章节
    # --------------------------------------------------------

    section = get_country_section(
        content
    )

    if not section:

        print(
            "    ❌ 没有找到国家配置章节"
        )

        return

    # --------------------------------------------------------
    # 解析
    # --------------------------------------------------------

    data = parse_country_data(
        section
    )

    if not data:

        print(
            "    ❌ 没有解析到国家配置"
        )

        return

    # --------------------------------------------------------
    # 输出
    # --------------------------------------------------------

    print()

    print(
        f"{'国家/地区':<10}"
        f"{'公允价值':>22}"
        f"{'占净值比例':>14}"
    )

    print(
        "-" * 48
    )

    for item in data:

        print(
            f"{item['country']:<10}"
            f"{item['value']:>22,.2f}"
            f"{item['ratio']:>13.2f}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    for code in FUNDS:

        try:

            process_fund(
                code
            )

        except Exception as e:

            print()
            print(
                f"{code} ❌ 异常：{e}"
            )


if __name__ == "__main__":

    main()