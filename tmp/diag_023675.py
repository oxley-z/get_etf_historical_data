import import_re, urllib.request, json, re

code = "023675"
o = import_re.get_direct_opener()
h = import_re.DEFAULT_HEADERS

print(f"\n{'='*70}\n诊断基金 {code}\n{'='*70}\n")

# ============ 1) 蛋卷 ============
print("--- 1) 蛋卷 danjuan ---")
try:
    url = f"https://danjuanfunds.com/djapi/fund/detail/{code}"
    req = urllib.request.Request(url, headers={
        "User-Agent": h["User-Agent"],
        "Referer": f"https://danjuanfunds.com/detail/{code}",
        "Accept": "application/json, text/plain, */*",
    })
    with o.open(req, timeout=10) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')
    print(f"返回长度: {len(raw)}")
    data = json.loads(raw)

    found = []
    def walk(obj, path=""):
        if isinstance(obj, dict):
            if "other_rate_table" in obj:
                print(f"✓ other_rate_table @ {path}: {obj['other_rate_table']}")
                found.append(True)
            for k, v in obj.items():
                walk(v, path + "/" + str(k))
        elif isinstance(obj, list):
            for i, it in enumerate(obj):
                walk(it, path + f"[{i}]")
    walk(data)
    if not found:
        print("✗ 未找到 other_rate_table")
        # 列出所有含 rate/fee/费 的 key
        def find_rate_keys(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    ks = str(k).lower()
                    if "rate" in ks or "fee" in ks or "费" in str(k):
                        print(f"    {path}/{k} = {str(v)[:120]}")
                    find_rate_keys(v, path + "/" + str(k))
            elif isinstance(obj, list):
                for i, it in enumerate(obj[:3]):
                    find_rate_keys(it, path + f"[{i}]")
        find_rate_keys(data)
except Exception as e:
    print(f"✗ 蛋卷异常: {e}")

# ============ 2) 天天基金 F10 jjfl 静态页 ============
print("\n--- 2) 天天基金 F10 jjfl 静态页 ---")
try:
    url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
    req = urllib.request.Request(url, headers={**h, "Referer": url})
    with o.open(req, timeout=8) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    print(f"返回长度: {len(html)}")
    print(f"含'管理费率': {'是' if '管理费率' in html else '否'}")
    print(f"含'管理费': {'是' if '管理费' in html else '否'}")
    print(f"含'托管费': {'是' if '托管费' in html else '否'}")
    for kw in ['管理费率', '管理费', '托管费']:
        pos = html.find(kw)
        if pos >= 0:
            print(f"  '{kw}' 上下文: {repr(html[max(0,pos-30):pos+120])}")
except Exception as e:
    print(f"✗ F10 异常: {e}")

# ============ 3) 天天基金主页 ============
print("\n--- 3) 天天基金主页 ---")
try:
    url = f"https://fund.eastmoney.com/{code}.html"
    req = urllib.request.Request(url, headers={**h, "Referer": url})
    with o.open(req, timeout=8) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    print(f"返回长度: {len(html)}")
    for kw in ['管理费', '托管费', '费率']:
        print(f"  含'{kw}': {'是' if kw in html else '否'}")
except Exception as e:
    print(f"✗ 主页异常: {e}")

# ============ 4) AkShare 雪球 ============
print("\n--- 4) AkShare 雪球 ---")
try:
    import akshare as ak
    df = ak.fund_individual_basic_info_xq(symbol=code)
    if df is not None and not df.empty:
        info = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
        for k, v in info.items():
            print(f"  {k}: {v}")
    else:
        print("✗ 雪球返回空")
except Exception as e:
    print(f"✗ 雪球异常: {e}")

# ============ 5) 天天基金移动端 FundMNBasicInformation ============
print("\n--- 5) 移动端 FundMNBasicInformation ---")
try:
    url = (f"https://fundmobapi.eastmoney.com/FundMNewApi/FundMNBasicInformation"
           f"?FCODE={code}&deviceid=3&plat=Iphone&product=EFund&version=6.6.6")
    req = urllib.request.Request(url, headers={"User-Agent": "EMTianTianFund/6.6.6 (iPhone; iOS 16.0; Scale/3.00)"})
    with o.open(req, timeout=6) as resp:
        j = json.loads(resp.read().decode('utf-8'))
    d = j.get("Datas") or {}
    # 打印费率相关字段
    for k, v in d.items():
        ks = str(k).lower()
        if any(x in ks for x in ["rate", "fee", "nav"]) or "费" in str(k):
            print(f"  {k} = {v}")
except Exception as e:
    print(f"✗ 移动端异常: {e}")

print(f"\n{'='*70}\n")