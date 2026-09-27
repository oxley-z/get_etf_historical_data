# CFTC 最新及历史持仓数据获取与分析

自动化抓取 CFTC 期货持仓数据（Leveraged Funds / Managed Money），
生成单周报告与可交互的深度分析面板。

## 运行环境

* Windows 11 / macOS / Linux
* Python 3.10+（推荐 3.11 / 3.12）
* 依赖库：`pandas` `numpy` `requests` `yfinance` `beautifulsoup4` `akshare`

快速安装依赖：

```bash
pip install pandas numpy requests yfinance beautifulsoup4 akshare
```

# 目录结构

```项目根/
├── cftc_position_analysis.py          # 抓取 + 生成单周报告
├── cftc_generate_dashboard.py         # 汇总生成交互式分析面板
├── README.md
│
├── cftc_dashboard.html       # 面板输出（根目录，含日历）
│
└── report/                            # 所有报告与缓存
    ├── cftc_持仓报告_2025-01-07.html
    ├── cftc_持仓报告_2025-01-14.html
    ├── ...
    ├── cftc_价格历史缓存.json
    └── cftc_面板完整数据.json
```

> ⚠️ 注意：**面板在根目录，周报在 `report/` 子目录**。
> 面板里的日历点击会跳转到 `report/cftc_持仓报告_YYYY-MM-DD.html`；
> 每份周报顶部有「← 返回分析面板」按钮可跳回根目录面板。
> 两个文件互相之间用**相对路径**引用，整个文件夹可以整体打包/上传 GitHub。

## 一、获取持仓报告

### 1.1 最新一期

```bash
python cftc_position_analysis.py
```

自动抓取 CFTC 已发布的最新一期报告，生成到：

```text
report/cftc_持仓报告_YYYY-MM-DD.html
```

### 1.2 指定单个日期

```bash
# 推荐写法
python cftc_position_analysis.py --date 2025-02-04

# 位置参数写法（等效）
python cftc_position_analysis.py 2025-02-04
```

### 1.3 批量获取一段区间内所有周二

```bash
# 推荐写法
python cftc_position_analysis.py --start 2025-01-01 --end 2026-04-10

# 位置参数写法（兼容旧版 cftc_batch_executor.py 的用法）
python cftc_position_analysis.py 2025-01-01 2026-04-10
```

**批量模式特点**：

- CFTC 原始数据**只抓取一次**（比循环调用快得多）
- 已存在的报告文件**自动跳过**
- 遇节假日（该周二无新数据）**自动跳过**，不会生成重复文件
- 支持 `Ctrl+C` 安全中断，已完成的数据保留

### 1.4 帮助信息

```bash
python cftc_position_analysis.py -h
python cftc_position_analysis.py --help
```

------

## 二、生成交互式分析面板

```bash
python cftc_generate_dashboard.py
```

脚本会：

1. 扫描 `report/` 下所有 `cftc_持仓报告_*.html`
2. 解析每期的多头 / 空头 / 净持仓数据
3. 按资产匹配历史价格（多源策略 + 本地缓存）
4. 生成交互式面板到**项目根目录**：

```text
cftc_dashboard.html
```

### 面板功能

| 功能                 | 说明                                                 |
| :------------------- | :--------------------------------------------------- |
| 🏠 数据总览（首页）   | 统计卡片 + 全资产最新持仓概览表                      |
| 📅 报告日历（侧边栏） | 有报告的日期蓝底可点击，跳转到对应周报；今日橙框标记 |
| 📈 单资产详情         | 多空头 + 净持仓柱状图 + 价格叠加（双 Y 轴）          |
| 🔗 双向跳转           | 面板 ↔ 周报互相跳转，路径相对                        |