# -*- coding:utf-8 -*-

import akshare as ak
import pandas as pd
from datetime import datetime


FUNDS = [
    "022365",
    "540010",
    "002112",
    "011892",
    "021528",
    "009645",
    "011370",
    "011452",
    "016371"
]


def get_years():
    y = datetime.now().year
    return [
        str(y),
        str(y - 1),
        str(y - 2)
    ]


def get_three_quarters(code):

    all_data = []

    for year in get_years():

        try:
            df = ak.fund_portfolio_hold_em(
                symbol=code,
                date=year
            )

            if not df.empty:
                all_data.append(df)

        except Exception:
            pass


    if not all_data:
        return {}


    data = pd.concat(
        all_data,
        ignore_index=True
    )

    data = data.drop_duplicates()

    data["占净值比例"] = (
        data["占净值比例"]
        .astype(float)
    )


    quarters = sorted(
        data["季度"].drop_duplicates().tolist(),
        reverse=True
    )


    result = {}

    # 保留4个季度，保证最后一个季度可以比较上一季度
    for q in quarters[:4]:

        temp = data[
            data["季度"] == q
        ].copy()

        temp = temp.sort_values(
            "占净值比例",
            ascending=False
        )

        # 不截断，保留完整持仓用于比较
        result[q] = temp


    return result



def compare(current, previous):

    curr = {}
    prev = {}
    names = {}


    for _, r in current.iterrows():

        code = r["股票代码"]

        curr[code] = float(
            r["占净值比例"]
        )

        names[code] = r["股票名称"]



    for _, r in previous.iterrows():

        code = r["股票代码"]

        prev[code] = float(
            r["占净值比例"]
        )

        if code not in names:
            names[code] = r["股票名称"]



    rows = []


    for code in set(curr.keys()) | set(prev.keys()):

        now = curr.get(code, 0)
        old = prev.get(code, 0)

        diff = now - old


        if old == 0 and now > 0:

            status = "🆕 新进"

        elif now == 0 and old > 0:

            status = "❌ 清仓"

        elif diff > 0.3:

            status = "⬆ 加仓"

        elif diff < -0.3:

            status = "⬇ 减仓"

        else:

            status = "➡ 持平"


        rows.append(
            {
                "股票代码": code,
                "股票名称": names[code],
                "当前季度": f"{now:.2f}%",
                "上一季度": f"{old:.2f}%",
                "变化": f"{diff:+.2f}%",
                "状态": status
            }
        )


    return pd.DataFrame(rows).sort_values(
        by="变化",
        key=lambda x: x.str.replace("%","").astype(float),
        ascending=False
    )



def process(code):

    print("\n")
    print("=" * 100)
    print("基金:", code)


    data = get_three_quarters(code)

    qs = list(data.keys())


    if len(qs) == 0:
        print("无持仓数据")
        return


    print("\n")
    print(
        "【最新季度:",
        qs[0],
        "】"
    )


    print(
        data[qs[0]][
            [
                "股票代码",
                "股票名称",
                "占净值比例"
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


    for i in range(len(qs)-1):

        current_q = qs[i]
        previous_q = qs[i+1]


        print("\n")
        print(
            f"【{current_q} vs {previous_q}】"
        )


        result = compare(
            data[current_q],
            data[previous_q]
        )


        print(
            result.to_string(index=False)
        )



if __name__ == "__main__":

    print(
        "基金最近三个季度持仓变化分析"
    )

    for fund in FUNDS:
        process(fund)