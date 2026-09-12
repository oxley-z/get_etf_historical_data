import os
import re
import urllib.request

# 1. 清空代理环境变量，确保直连
for env_var in [
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy"
]:
    os.environ.pop(env_var, None)

# 查询代码列表：包含你指定的 3 只基金与参考的 014002
TARGET_FUNDS = ["022365", "540010", "002112", "014002"]

def get_direct_opener():
    """构建直连 opener"""
    proxy_handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(proxy_handler)

def get_fund_name(opener, code):
    """从 pingzhongdata JS 文件中直接提取基金真实名称"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r'var\s+fS_name\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1).strip()
    except Exception:
        pass
    return f"基金_{code}"

def get_holder_structure(opener, code):
    """
    抓取天天基金 F10 持有人结构的真实后端异步接口：
    https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&code={code}
    """
    url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&code={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        # 必须带上对应的页面 Referer 才能通过鉴权验证
        "Referer": f"https://fundf10.eastmoney.com/cyrjg_{code}.html",
        "Accept": "*/*"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 匹配所有 <tr> 行
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
        for row in rows:
            # 过滤掉表头 th，提取数据 td
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            if len(cols) >= 3:
                # 检查第 1 列是否为报告期日期 (YYYY-MM-DD)
                date_m = re.search(r'\d{4}-\d{2}-\d{2}', cols[0])
                if not date_m:
                    continue

                # 提取各列纯文本
                def clean_text(val):
                    return re.sub(r'<[^>]+>', '', val).strip()

                date_str = date_m.group(0)
                inst_ratio = clean_text(cols[1])
                indiv_ratio = clean_text(cols[2])
                internal_ratio = clean_text(cols[3]) if len(cols) > 3 else "--"
                total_shares = clean_text(cols[4]) if len(cols) > 4 else "--"

                return {
                    "date": date_str,
                    "institution": inst_ratio,
                    "individual": indiv_ratio,
                    "internal": internal_ratio,
                    "total_shares": total_shares
                }
    except Exception:
        pass

    return None

def main():
    opener = get_direct_opener()

    print(f"{'='*72}")
    print(f"{'代码':<8}{'基金名称':<22}{'报告期':<14}{'机构占比':<12}{'个人占比':<12}{'内部持有':<10}")
    print(f"{'-'*72}")

    for code in TARGET_FUNDS:
        name = get_fund_name(opener, code)
        holder_info = get_holder_structure(opener, code)

        if holder_info:
            print(
                f"{code:<8}{name[:12]:<22}{holder_info['date']:<14}"
                f"{holder_info['institution']:<12}{holder_info['individual']:<12}{holder_info['internal']:<10}"
            )
        else:
            print(f"{code:<8}{name[:12]:<22}{'暂无披露数据':<30}")

    print(f"{'='*72}")
    print("注：持有人结构只在基金半年报（6月30日）与年报（12月31日）中披露。")

if __name__ == "__main__":
    main()