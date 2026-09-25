import import_re, urllib.request, json, re

codes = ["002164", "024648", "017968", "025500", "017028"]
o = import_re.get_direct_opener()

def check(code):
    url = f"https://danjuanfunds.com/djapi/fund/detail/{code}"
    headers = {
        "User-Agent": import_re.DEFAULT_HEADERS["User-Agent"],
        "Referer": f"https://danjuanfunds.com/detail/{code}",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with o.open(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"❌ 请求失败: {e}"

    rate_table = None
    def _walk(obj):
        nonlocal rate_table
        if rate_table is not None:
            return
        if isinstance(obj, dict):
            if "other_rate_table" in obj and isinstance(obj["other_rate_table"], list):
                rate_table = obj["other_rate_table"]
                return
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for it in obj:
                _walk(it)
    _walk(data)

    if not rate_table:
        return "❌ 无 other_rate_table"
    lines = []
    for item in rate_table:
        if isinstance(item, dict):
            lines.append(f"{item.get('name')}={item.get('value')}")
    return "✅ " + " | ".join(lines)

for c in codes:
    print(f"{c}: {check(c)}")