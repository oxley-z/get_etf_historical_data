import os
import re
import json
import time
import random
import argparse
import webbrowser
import urllib.request
import urllib.parse
import akshare as ak
from datetime import datetime, timedelta

# 强制清空代理环境变量，避免 VPN 或代理劫持请求
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(env_var, None)

DEFAULT_FUNDS = [
    "002891", "014002", "012922", "021662", "539002", "021842", "018036",
    "008254", "017731", "016665", "018230", "021277", "005698", "501312",
    "017654", "022184", "017437", "017145", "016702", "016823", "019156"
]

def get_direct_opener():
    """构建绕过本地代理的底层网络连接池"""
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def fetch_fund_detail_meta(opener, code):
    """全面抓取：名称, 规模, 管理费, 托管费, 销售服务费, 申购费, 多档持有期赎回费, 交易状态, 申购限额"""
    meta = {
        "name": f"基金_{code}",
        "scale": "未知",
        "scale_val": -1.0,
        "fee_manage": "--",
        "fee_custody": "--",
        "fee_sales": "--",
        "fee_purchase": "0.00%",     
        "fee_redemption": "未知",
        "buy_status": "--",
        "buy_limit": "无限额",          # 显示用字符串
        "buy_limit_val": -1,           # 排序用数值（单位：元）
        "fee_total": "未知",
        "fee_val": -1.0
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"https://fund.eastmoney.com/{code}.html",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    js_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        req = urllib.request.Request(js_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            content = resp.read().decode('utf-8', errors='ignore')

            match_name = re.search(r'var\s+fS_name\s*=\s*["\']([^"\']+)["\']', content)
            if match_name:
                meta["name"] = match_name.group(1)

            # 规模获取方式替换为 AkShare 雪球接口
            try:
                df_xq = ak.fund_individual_basic_info_xq(symbol=code)
                if df_xq is not None and not df_xq.empty:
                    cols = df_xq.columns.tolist()
                    if len(cols) >= 2:
                        info_dict = dict(zip(df_xq[cols[0]], df_xq[cols[1]]))

                        for k in ["基金规模", "资产规模", "最新规模"]:
                            if k in info_dict and info_dict[k]:
                                scale_str = str(info_dict[k])
                                scale_m = re.search(r'([\d\.]+)', scale_str)
                                if scale_m:
                                    val = float(scale_m.group(1))
                                    meta["scale_val"] = val
                                    meta["scale"] = f"{val:.2f} 亿"
                                break
            except Exception:
                pass

            match_rate = re.search(r'var\s+Data_rateInverstment\s*=\s*["\']([^"\']+)["\']', content)
            if match_rate:
                rate_text = match_rate.group(1)
                m_match = re.search(r'管理费[：:]\s*([\d\.]+)%', rate_text)
                c_match = re.search(r'托管费[：:]\s*([\d\.]+)%', rate_text)
                s_match = re.search(r'销售服务费[：:]\s*([\d\.]+)%', rate_text)
                
                m_val = float(m_match.group(1)) if m_match else 0.0
                c_val = float(c_match.group(1)) if c_match else 0.0
                s_val = float(s_match.group(1)) if s_match else 0.0

                if m_val > 0 or c_val > 0 or s_val > 0:
                    meta["fee_manage"] = f"{m_val:.2f}%"
                    meta["fee_custody"] = f"{c_val:.2f}%"
                    meta["fee_sales"] = f"{s_val:.2f}%"
                    tot = m_val + c_val + s_val
                    meta["fee_val"] = tot
                    meta["fee_total"] = f"{tot:.2f}%"
            
            buy_m = re.search(r'var\s+fund_sourceRate\s*=\s*"([^"]+)";', content)
            if buy_m:
                meta["fee_purchase"] = buy_m.group(1)
    except Exception:
        pass

    f10_url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
    try:
        req = urllib.request.Request(f10_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

            if meta["scale"] == "未知":
                scale_m = re.search(r'基金规模.*?([\d\.]+)\s*亿元', html, re.S)
                if scale_m:
                    meta["scale_val"] = float(scale_m.group(1))
                    meta["scale"] = f"{scale_m.group(1)} 亿"

            if meta["fee_total"] == "未知":
                m_m = re.search(r'管理费率.*?([\d\.]+)%', html, re.S)
                c_m = re.search(r'托管费率.*?([\d\.]+)%', html, re.S)
                s_m = re.search(r'销售服务费率.*?([\d\.]+)%', html, re.S)
                
                m_v = float(m_m.group(1)) if m_m else 0.0
                c_v = float(c_m.group(1)) if c_m else 0.0
                s_v = float(s_m.group(1)) if s_m else 0.0
                
                if m_v > 0 or c_v > 0 or s_v > 0:
                    meta["fee_manage"] = f"{m_v:.2f}%"
                    meta["fee_custody"] = f"{c_v:.2f}%"
                    meta["fee_sales"] = f"{s_v:.2f}%"
                    tot = m_v + c_v + s_v
                    meta["fee_val"] = tot
                    meta["fee_total"] = f"{tot:.2f}%"

            purch_section = re.search(r'申购费率.*?(?:</table>|<div class="info">)', html, re.S)
            if purch_section:
                vals = re.findall(r'([\d\.]+)%', purch_section.group(0))
                if vals:
                    meta["fee_purchase"] = f"{float(vals[0]):.2f}%"

            red_section = re.search(r'赎回费率.*?(?:</table>|</div>\s*</div>)', html, re.S)
            if red_section:
                red_html = red_section.group(0)
                rows = re.findall(r'<tr[^>]*>(.*?)<\/tr>', red_html, re.S)
                red_tiers = []
                for row in rows:
                    cols = re.findall(r'<td[^>]*>(.*?)<\/td>', row, re.S)
                    if len(cols) >= 2:
                        period_desc = re.sub(r'<[^>]+>', '', cols[0]).strip()
                        rate_desc = re.sub(r'<[^>]+>', '', cols[1]).strip()
                        if period_desc and rate_desc and '%' in rate_desc:
                            red_tiers.append(f"{period_desc}: {rate_desc}")
                
                if red_tiers:
                    meta["fee_redemption"] = " | ".join(red_tiers)
                else:
                    red_m = re.findall(r'([\d\.]+)%', red_html)
                    if red_m:
                        meta["fee_redemption"] = f"常规档: {red_m[0]}%"
    except Exception:
        pass

    if code.endswith('C') or code.startswith('014') or code.startswith('012') or code.startswith('021'):
        if meta["fee_purchase"] == "0.00%":
            meta["fee_purchase"] = "0.00% (C类免)"

    # 获取交易状态和申购限额（修复：支持“万元”和“元”，并提取数值用于排序）
    trade_url = f"https://fund.eastmoney.com/{code}.html"
    try:
        req = urllib.request.Request(trade_url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            trade_html = resp.read().decode("utf-8", errors="ignore")

        trade = re.search(r"交易状态：</span>(.*?)</div>", trade_html, re.S)
        if trade:
            text = re.sub(r"<.*?>", "", trade.group(1))
            text = text.replace("&nbsp;", "").strip()

            status = re.search(r"^(.*?)\s*\(", text)
            if status:
                meta["buy_status"] = status.group(1).strip()

            # 修复：提取数字和单位，计算元数值
            limit_match = re.search(r"单日累计购买上限([\d.]+)(万?)元", text)
            if limit_match:
                num = float(limit_match.group(1))
                if limit_match.group(2) == "万":
                    num *= 10000
                meta["buy_limit"] = f"{limit_match.group(1)}{limit_match.group(2)}元"  # 保留原始格式
                meta["buy_limit_val"] = num
            else:
                # 无上限或未匹配，保持默认
                meta["buy_limit"] = "无限额"
                meta["buy_limit_val"] = -1
    except Exception:
        pass

    return meta

def fetch_from_eastmoney(opener, code, start_date, end_date):
    """获取历史净值数据"""
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"
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

def analyze_fund_metrics(valid_data):
    """计算核心量化指标：最大回撤、修复率、低点反弹幅度"""
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
    """生成包含申购限额列的 HTML 看板，限额按数值排序"""
    rows_html = ""
    for r in results:
        fund_url = f"https://fund.eastmoney.com/{r['code']}.html"
        
        max_dd_pct = min(max(r['max_drawdown'], 0), 100)
        rec_pct = min(max(r['recovery_rate'], 0), 100)
        reb_pct = min(max(r['rebound_gain'], 0), 100)

        # 获取限额显示字符串和数值
        limit_display = r.get('buy_limit', '无限额')
        limit_val = r.get('buy_limit_val', -1)

        rows_html += f"""
        <tr>
            <td class="code" data-val="{r['code']}">{r['code']}</td>
            <td class="name" data-val="{r['name']}">
                <a href="{fund_url}" target="_blank" title="点击查看天天基金概况">{r['name']}</a>
                <div class="redemption-sub">赎回: {r['fee_redemption']}</div>
            </td>
            <td data-val="{r['scale_val']}" class="highlight-val">{r['scale']}</td>
            <td data-val="{r['fee_val']}">{r['fee_total']} <span class="fee-sub">(管:{r['fee_manage']}/托:{r['fee_custody']}/销:{r['fee_sales']})</span></td>
            <td data-val="{r['fee_purchase']}">{r['fee_purchase']}</td>
            <td data-val="{limit_val}">{r.get('buy_status', '--')}<div class="fee-sub">{limit_display}</div></td>
            <td data-val="{r['peak_nav']}">{r['peak_nav']:.4f}</td>
            <td data-val="{r['trough_nav']}">{r['trough_nav']:.4f}</td>
            <td data-val="{r['latest_nav']}">{r['latest_nav']:.4f}</td>
            <td class="metric-red" data-val="{r['max_drawdown']}">
                <div class="progress-container progress-text">
                    <div class="progress-bar bar-red" style="width: {max_dd_pct}%;">
                        <span>{r['max_drawdown']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td data-val="{r['recovery_rate']}">
                <div class="progress-container progress-text">
                    <div class="progress-bar bar-blue" style="width: {rec_pct}%;">
                        <span>{r['recovery_rate']:.2f}%</span>
                    </div>
                </div>
            </td>
            <td class="metric-green" data-val="{r['rebound_gain']}">
                <div class="progress-container progress-text">
                    <div class="progress-bar bar-green" style="width: {reb_pct}%;">
                        <span>{r['rebound_gain']:.2f}%</span>
                    </div>
                </div>
            </td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>场外基金量化与费率规模看板（含申购限额）</title>
    <style>
        body {{ 
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif; 
            background-color: #f8f9fa; 
            margin: 0; 
            padding: 30px 50px; 
            color: #333; 
        }}
        .header {{ text-align: center; margin-bottom: 12px; }}
        .header h2 {{ color: #1a73e8; margin: 0 0 4px 0; font-size: 20px; }}
        .header p {{ color: #5f6368; font-size: 13px; margin: 0; }}
        .table-container {{ 
            width:100%; 
            overflow-x:auto; 
            box-sizing:border-box; 
            background:#fff; 
            border-radius:12px; 
            box-shadow:0 4px 15px rgba(0,0,0,0.08); 
            padding:20px; 
            border:1px solid #e0e0e0; 
        }}
        
        table {{ 
            width:100%; 
            min-width:1650px; 
            border-collapse:collapse; 
            font-size:12px; 
            text-align:right; 
            table-layout:fixed; 
        }}
        th, td {{ 
            padding:6px 8px; 
            border-bottom:1px solid #eee; 
            line-height:1.4; 
            overflow:hidden; 
            text-overflow:ellipsis; 
            box-sizing:border-box; 
        }}
        
        /* ----- 各列宽度与换行策略 ----- */
        th:nth-child(1), td:nth-child(1) {{ width: 80px; text-align: left; white-space: nowrap; }}
        th:nth-child(2), td:nth-child(2) {{ width: 260px; min-width: 200px; text-align: left; white-space: normal; word-break: break-word; vertical-align: middle; }}
        th:nth-child(3), td:nth-child(3) {{ width: 120px; text-align: left; white-space: nowrap; }}
        th:nth-child(4), td:nth-child(4) {{ width: 160px; text-align: left; white-space: normal; word-break: break-word; }}
        th:nth-child(5), td:nth-child(5) {{ width: 80px; text-align: left; white-space: nowrap; }}
        th:nth-child(6), td:nth-child(6) {{ width: 120px; text-align: left; white-space: nowrap; }}  /* 申购限额列 */
        th:nth-child(7), td:nth-child(7),
        th:nth-child(8), td:nth-child(8),
        th:nth-child(9), td:nth-child(9) {{ width: 80px; white-space: nowrap; }}
        th:nth-last-child(3),
        td:nth-last-child(3),
        th:nth-last-child(2),
        td:nth-last-child(2),
        th:nth-last-child(1),
        td:nth-last-child(1) {{
            width: 250px;
            min-width: 200px;
            white-space: nowrap;
        }}

        th {{ 
            background-color: #f1f3f4; 
            color: #3c4043; 
            font-weight: 600; 
            text-align: right; 
            user-select: none; 
            cursor: pointer; 
            transition: background-color 0.2s; 
            white-space: nowrap; 
            position: relative; 
        }}
        th:hover {{ background-color: #e4e7eb; }}
        th:nth-child(1), th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5), th:nth-child(6) {{ text-align: left; }}
        tr:hover {{ background-color: #f8f9fa; }}
        
        .resizer {{
            position: absolute; 
            right: 0; 
            top: 0; 
            bottom: 0; 
            width: 6px;
            cursor: col-resize; 
            user-select: none; 
            touch-action: none; 
            z-index: 10;
        }}
        .resizer:hover, th.resizing .resizer {{ background-color: #1a73e8; }}

        .sort-icon {{ font-size: 10px; margin-left: 2px; color: #70757a; }}
        .code {{ font-family: "SFMono-Regular", Consolas, monospace; font-weight: bold; color: #1a73e8; }}
        .name a {{ 
            font-weight:500; 
            color:#1a73e8; 
            text-decoration:none; 
            display:inline-block; 
            max-width:100%; 
            overflow:hidden; 
            text-overflow:ellipsis; 
            vertical-align:middle; 
        }}
        .name a:hover {{ text-decoration: underline; color: #1557b0; }}
        .redemption-sub {{ 
            font-size: 10px; 
            color: #7f8c8d; 
            font-weight: normal; 
            margin-top: 2px; 
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .highlight-val {{ font-weight: 600; color: #e67e22; }}
        .fee-sub {{ font-size: 10px; color: #7f8c8d; }}
        
        .progress-container {{
            background-color:#e5e7eb;
            border-radius:6px;
            overflow:hidden;
            height:20px;
            width:100%;
            position:relative;
        }}
        .progress-bar {{
            height:100%;
            border-radius:6px;
            min-width:42px;
            display:flex;
            align-items:center;
            justify-content:flex-end;
            padding-right:6px;
            box-sizing:border-box;
            transition:width .2s ease;
        }}
        .progress-bar span {{
            color:#fff;
            font-size:11px;
            font-weight:600;
            text-shadow:0 1px 1px rgba(0,0,0,.25);
        }}
        .bar-red {{ background-color:#d93025; }}
        .bar-blue {{ background-color:#1a73e8; }}
        .bar-green {{ background-color:#188038; }}

        .metric-red {{ color: #d93025; font-weight: 600; }}
        .metric-green {{ color: #188038; font-weight: 600; }}
        .footer-note {{ 
            margin-top: 10px; 
            font-size: 12px; 
            color: #70757a; 
            line-height: 1.4; 
            background: #fff; 
            padding: 10px 12px; 
            border-radius: 6px; 
            border: 1px solid #e0e0e0; 
        }}
        .footer-note p {{ margin: 2px 0; }}
    </style>
</head>
<body>

    <div class="header">
        <h2>场外基金核心量化与全费率规模看板（含申购限额）</h2>
        <p>统计时间区间：<strong>{start_date}</strong> 至 <strong>{end_date}</strong> （包含基金数：{len(results)} 只）</p>
    </div>

    <div class="table-container">
        <table id="fundTable">
            <thead>
                <tr>
                    <th data-col="0">代码 <span class="sort-icon">⇅</span></th>
                    <th data-col="1">基金名称 / 赎回费率阶梯 <span class="sort-icon">⇅</span></th>
                    <th data-col="2">最新规模 <span class="sort-icon">⇅</span></th>
                    <th data-col="3">运作费(管/托/销) <span class="sort-icon">⇅</span></th>
                    <th data-col="4">申购费率 <span class="sort-icon">⇅</span></th>
                    <th data-col="5">申购状态/限额 <span class="sort-icon">⇅</span></th>
                    <th data-col="6">最高净值 <span class="sort-icon">⇅</span></th>
                    <th data-col="7">最低净值 <span class="sort-icon">⇅</span></th>
                    <th data-col="8">最新净值 <span class="sort-icon">⇅</span></th>
                    <th data-col="9">最大回撤 <span class="sort-icon">⇅</span></th>
                    <th data-col="10">修复程度 <span class="sort-icon">⇅</span></th>
                    <th data-col="11">自低点反弹 <span class="sort-icon">⇅</span></th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>

    <div class="footer-note">
        <p><strong>使用提示：</strong> 列宽可拖拽调整，点击表头排序。名称列与运作费列支持自动换行，避免文字覆盖。申购限额按数值大小排序（元为单位）。</p>
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", function () {{
            const table = document.getElementById("fundTable");
            const headers = table.querySelectorAll("th");

            headers.forEach((th, idx) => {{
                th.addEventListener("click", function(e) {{
                    if (th.classList.contains("is-resizing") || window._isDragging) {{
                        return;
                    }}
                    sortTable(idx);
                }});

                const resizer = document.createElement("div");
                resizer.classList.add("resizer");
                th.appendChild(resizer);

                let x = 0;
                let w = 0;

                resizer.addEventListener("mousedown", function (e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    window._isDragging = true;
                    x = e.clientX;
                    w = th.getBoundingClientRect().width;
                    th.style.width = w + "px";
                    th.classList.add("resizing");
                    th.classList.add("is-resizing");

                    function mouseMoveHandler(e) {{
                        const dx = e.clientX - x;
                        const newWidth = Math.max(40, w + dx);
                        th.style.width = newWidth + "px";
                    }}

                    function mouseUpHandler(e) {{
                        th.classList.remove("resizing");
                        document.removeEventListener("mousemove", mouseMoveHandler);
                        document.removeEventListener("mouseup", mouseUpHandler);
                        const finalWidth = th.getBoundingClientRect().width;
                        th.style.width = finalWidth + "px";
                        setTimeout(() => {{
                            window._isDragging = false;
                            th.classList.remove("is-resizing");
                        }}, 50);
                    }}

                    document.addEventListener("mousemove", mouseMoveHandler);
                    document.addEventListener("mouseup", mouseUpHandler);
                }});
            }});
        }});

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
                if (icon) {{
                    if (idx === colIndex) {{
                        icon.textContent = isAscending ? "▲" : "▼";
                        th.style.color = "#1a73e8";
                    }} else {{
                        icon.textContent = "⇅";
                        th.style.color = "#3c4043";
                    }}
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

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default=default_start)
    parser.add_argument("--end", type=str, default=today_str)
    parser.add_argument("--funds", nargs="+", default=DEFAULT_FUNDS)
    parser.add_argument("--out", type=str, default="fund_drawdown_dashboard.html")

    args = parser.parse_args()
    opener = get_direct_opener()

    print(f"\n======== 开始抓取数据 (含申购限额，已修复单位识别与排序) ========")
    print(f"统计区间: {args.start} 至 {args.end}")

    results = []
    for idx, code in enumerate(args.funds, start=1):
        meta = fetch_fund_detail_meta(opener, code)
        raw_data = fetch_from_eastmoney(opener, code, args.start, args.end)
        
        if not raw_data:
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ❌ 历史净值抓取失败")
            continue

        res = analyze_fund_metrics(raw_data)
        if res:
            res.update({
                "code": code,
                "name": meta["name"],
                "scale": meta["scale"],
                "scale_val": meta["scale_val"],
                "fee_manage": meta["fee_manage"],
                "fee_custody": meta["fee_custody"],
                "fee_sales": meta["fee_sales"],
                "fee_total": meta["fee_total"],
                "fee_val": meta["fee_val"],
                "fee_purchase": meta["fee_purchase"],
                "fee_redemption": meta["fee_redemption"],
                "buy_status": meta.get("buy_status", "--"),
                "buy_limit": meta.get("buy_limit", "无限额"),
                "buy_limit_val": meta.get("buy_limit_val", -1),
                "source": "天天基金"
            })
            results.append(res)
            print(f"[{idx}/{len(args.funds)}] {code} - {meta['name']} ... ✅ 完成")
        
        time.sleep(random.uniform(0.05, 0.1))

    if results:
        abs_path = generate_html_report(results, args.start, args.end, filename=args.out)
        print(f"\n🎉 网页生成成功！文件路径: {abs_path}")
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass

if __name__ == "__main__":
    main()