# _test_fee.py  ← 确保内容是这个
from import_re import get_direct_opener, fetch_fund_detail_meta

opener = get_direct_opener()
for code in ['004320', '160213', '001438']:
    meta = fetch_fund_detail_meta(opener, code)
    print(f"{code}  {meta['name']}")
    print(f"   赎回费 = {meta['fee_redemption']}")