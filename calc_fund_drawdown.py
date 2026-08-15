import os
import re
import json
import time
import random
import argparse
import webbrowser
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ==========================================
# 1. 进程内强制清空代理环境变量（彻底杜绝 ProxyError）
# ==========================================
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

DEFAULT_FUNDS = [
    "002891", "014002", "012922", "021662", "539002", "021842", "018036",
    "008254", "017731", "016665", "018230", "021277", "005698", "501312",
    "017654", "022184", "017437", "017145", "016702", "016823", "019156"
]

def get_direct_opener():
    """创建一个彻底绕过本地代理的 urllib opener"""
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def fetch_fund_name_from_source(opener, code):
    """从天天基金官方 JS 数据源中动态解析基金全称"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": f"https://fund.eastmoney.com/{code}.html"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            match = re.search(r'var\s+fS_name\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return f"基金_{code}"

def fetch_from_eastmoney(opener, code, start_date, end_date):
    base_url = "https://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "callback": "jQuery11230_lsjz",
        "fundCode": code,
        "pageIndex": 1,
        "pageSize": 200,
        "startDate": start_date,
        "endDate": end_date,
        "_": str(int(time.time() * 1000))
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html",
        "Accept": "*/*"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode('utf-8')
            match = re.search(r'jQuery11230_lsjz\((.*)\)', html)
            if match:
                res_json = json.loads(match.group(1))
                lsjz = res_json.get("Data", {}).get("LSJZList", [])
                if lsjz:
                    clean_data = []
                    for item in lsjz:
                        if item.get("DWJZ"):
                            clean_data.append({"date": item["FSRQ"], "nav": float(item["DWJZ"])})
                    return clean_data
    except Exception:
        pass
    return None

def fetch_from_sina(opener, code, start_date, end_date):
    url = f"https://finance.sina.com.cn/fund/api/jsonp.php/IO.XSRF.Fund.getFundNav/FundService.getNav?symbol={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode('utf-8')
            match = re.search(r'\((\{.*\})\)', html)
            if match:
                res_json = json.loads(match.group(1))
                data_list = res_json.get("result", {}).get("data", {}).get("data", [])
                clean_data = []
                for item in data_list:
                    fdate = item.get("date")
                    if fdate and start_date <= fdate <= end_date and item.get("nav"):
                        clean_data.append({"date": fdate, "nav": float(item["nav"])})
                if clean_data:
                    return clean_data
    except Exception:
        pass
    return None

def fetch_fund_data_multisource(opener, code, start_date, end_date):
    data = fetch_from_eastmoney(opener, code, start_date, end_date)
    if data:
        return data, "天天基金"

    data = fetch_from_sina(opener, code, start_date, end_date)
    if data:
        return data, "新浪财经"

    return None, "全部失败"

def analyze_fund_metrics(valid_data):
    data = sorted(valid_data, key=lambda x: x["date"])
    if not data:
        return None

    max_drawdown = 0.0
    peak_nav = data[0]["nav"]
    trough_nav = data[0]["nav"]
    temp_peak = data[0]["nav"]

    for item in data:
        nav = item["nav"]
        if nav > temp_peak:
            temp_peak = nav
            
        drawdown = (temp_peak - nav) / temp_peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            peak_nav = temp_peak
            trough_nav = nav

    latest_nav = data[-1]["nav"]

    if max_drawdown == 0:
        recovery_rate = 100.0  
    elif peak_nav == trough_nav:
        recovery_rate = 0.0
    else:
        recovery_rate = ((latest_nav - trough_nav) / (peak_nav - trough_nav)) * 100.0

    rebound_gain = ((latest_nav - trough_nav) / trough_nav) * 100.0 if trough_nav > 0 else 0.0

    return {
        "peak_nav": peak_nav,
        "trough_nav": trough_nav,
        "latest_nav": latest_nav,
        "max_drawdown": max_drawdown * 100.0,
        "recovery_rate": recovery_rate,
        "rebound_gain": rebound_gain
    }

def generate_html_report(results, start_date, end_date, filename="fund_drawdown_dashboard.html"):
    """生成带有交互式排序功能的 HTML 报表"""
    rows_html = ""
    for r in results:
        rows_html += f"""
        <tr>
            <td class="code" data-val="{r['code']}">{r['code']}</td>
            <td class="name" data-val="{r['name']}">{r['name']}</td>
            <td data-val="{r['source']}"><span class="badge">{r['source']}</span></td>
            <td data-val="{r['peak_nav']}">{r['peak_nav']:.4f}</td>
            <td data-val="{r['trough_nav']}">{r['trough_nav']:.4f}</td>
            <td data-val="{r['latest_nav']}">{r['latest_nav']:.4f}</td>
            <td class="metric-red" data-val="{r['max_drawdown']}">{r['max_drawdown']:.2f}%</td>
            <td data-val="{r['recovery_rate']}">{r['recovery_rate']:.2f}%</td>
            <td class="metric-green" data-val="{r['rebound_gain']}">{r['rebound_gain']:.2f}%</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>场外基金历史净值与分析看板</title>
    <style>
        body {{ font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif; background-color: #f8f9fa; margin: 0; padding: 24px; color: #333; }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .header h2 {{ color: #1a73e8; margin: 0 0 8px 0; font-size: 24px; }}
        .header p {{ color: #5f6368; font-size: 14px; margin: 0; }}
        .table-container {{ overflow-x: auto; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 16px; border: 1px solid #e0e0e0; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; text-align: right; }}
        th, td {{ padding: 12px 16px; border-bottom: 1px solid #eee; }}
        th {{ background-color: #f1f3f4; color: #3c4043; font-weight: 600; text-align: right; user-select: none; cursor: pointer; transition: background-color 0.2s; }}
        th:hover {{ background-color: #e4e7eb; }}
        th:nth-child(1), th:nth-child(2), th:nth-child(3),
        td:nth-child(1), td:nth-child(2), td:nth-child(3) {{ text-align: left; }}
        tr:hover {{ background-color: #f8f9fa; }}
        .sort-icon {{ font-size: 12px; margin-left: 4px; color: #70757a; }}
        .code {{ font-family: "SFMono-Regular", Consolas, monospace; font-weight: bold; color: #1a73e8; }}
        .name {{ font-weight: 500; color: #202124; }}
        .badge {{ background: #e8f0fe; color: #1967d2; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }}
        .metric-red {{ color: #d93025; font-weight: 600; }}
        .metric-green {{ color: #188038; font-weight: 600; }}
        .footer-note {{ margin-top: 20px; font-size: 13px; color: #70757a; line-height: 1.6; background: #fff; padding: 16px; border-radius: 8px; border: 1px solid #e0e0e0; }}
        .footer-note p {{ margin: 4px 0; }}
    </style>
</head>
<body>

    <div class="header">
        <h2>场外基金核心量化指标对比看板</h2>
        <p>统计时间区间：<strong>{start_date}</strong> 至 <strong>{end_date}</strong> （包含基金数：{len(results)} 只）</p>
    </div>

    <div class="table-container">
        <table id="fundTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">代码 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(1)">基金名称 (动态源获取) <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(2)">来源 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(3)">最高净值 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(4)">最低净值 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(5)">最新净值 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(6)">最大回撤 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(7)">修复程度 <span class="sort-icon">⇅</span></th>
                    <th onclick="sortTable(8)">自低点反弹 <span class="sort-icon">⇅</span></th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>

    <div class="footer-note">
        <p><strong>使用提示：</strong> 点击表格头部（列标题）可针对该列进行 <strong>升序 / 降序</strong> 排序切换。</p>
        <p><strong>指标说明：</strong></p>
        <p>1. <strong>修复程度 (%)</strong>：(最新净值 - 最低净值) / (最高净值 - 最低净值) × 100%（接近或超过 100% 表示接近或突破前期高点）。</p>
        <p>2. <strong>自低点反弹 (%)</strong>：(最新净值 - 最低净值) / 最低净值 × 100%（衡量底部的绝对反弹力度）。</p>
    </div>

    <script>
        let currentSortCol = -1;
        let isAscending = true;

        function sortTable(colIndex) {{
            const table = document.getElementById("fundTable");
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));

            if (currentSortCol === colIndex) {{
                isAscending = !isAscending;
            }} else {{
                currentSortCol = colIndex;
                isAscending = true;
            }}

            rows.sort((a, b) => {{
                const cellA = a.children[colIndex];
                const cellB = b.children[colIndex];
                
                let valA = cellA.getAttribute("data-val");
                let valB = cellB.getAttribute("data-val");

                const numA = parseFloat(valA);
                const numB = parseFloat(valB);

                if (!isNaN(numA) && !isNaN(numB)) {{
                    return isAscending ? numA - numB : numB - numA;
                }}

                return isAscending 
                    ? valA.localeCompare(valB, 'zh-Hans-CN', {{ sensitivity: 'accent' }})
                    : valB.localeCompare(valA, 'zh-Hans-CN', {{ sensitivity: 'accent' }});
            }});

            rows.forEach(row => tbody.appendChild(row));

            const headers = table.querySelectorAll("th");
            headers.forEach((th, idx) => {{
                const icon = th.querySelector(".sort-icon");
                if (idx === colIndex) {{
                    icon.textContent = isAscending ? "▲" : "▼";
                    th.style.color = "#1a73e8";
                }} else {{
                    icon.textContent = "⇅";
                    th.style.color = "#3c4043";
                }}
            }});
        }}
    </script>
</body>
</html>
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return os.path.abspath(filename)

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="多源动态分析并直接生成 HTML 页面")
    parser.add_argument("--start", type=str, default=default_start)
    parser.add_argument("--end", type=str, default=today_str)
    parser.add_argument("--funds", nargs="+", default=DEFAULT_FUNDS)
    parser.add_argument("--out", type=str, default="fund_drawdown_dashboard.html", help="输出的HTML文件名")

    args = parser.parse_args()
    opener = get_direct_opener()

    print(f"\n======== 开始抓取数据并生成带排序功能的 HTML 看板 ========")
    print(f"统计区间: {args.start} 至 {args.end}")
    print(f"处理进度:")

    results = []
    for idx, code in enumerate(args.funds, start=1):
        fund_name = fetch_fund_name_from_source(opener, code)
        raw_data, source_name = fetch_fund_data_multisource(opener, code, args.start, args.end)
        
        if not raw_data:
            print(f"[{idx}/{len(args.funds)}] {code} - {fund_name} ... ❌ 抓取失败")
            continue

        res = analyze_fund_metrics(raw_data)
        if res:
            res.update({
                "code": code,
                "name": fund_name,
                "source": source_name
            })
            results.append(res)
            print(f"[{idx}/{len(args.funds)}] {code} - {fund_name} ... ✅ 完成 ({source_name})")
        
        time.sleep(random.uniform(0.05, 0.1))

    if results:
        abs_path = generate_html_report(results, args.start, args.end, filename=args.out)
        print(f"\n🎉 网页生成成功！文件路径:")
        print(f"👉 {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass
    else:
        print("\n❌ 未能成功获取任何有效的基金数据，无法生成HTML。")

if __name__ == "__main__":
    main()