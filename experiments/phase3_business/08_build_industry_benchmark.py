import pandas as pd

INPUT_PATH = r"E:\agent\data\dynamic_yield_benchmarks.xlsx"
OUTPUT_PATH = r"E:\agent\data\industry_benchmark_comparison.xlsx"

# =========================
# 1. 读取Dynamic Yield月度数据
# =========================

df = pd.read_excel(
    INPUT_PATH,
    sheet_name="月度基准",
    header=3
)

# =========================
# 2. 只保留2025年
# =========================

df = df[
    df["月份"]
    .astype(str)
    .str.startswith("2025-")
].copy()

# =========================
# 3. 只保留项目需要的范围
# =========================

TARGET_SCOPES = [
    "Fashion/Apparel｜全球",
    "电商通用｜全球｜全行业"
]

df = df[
    df["范围"].isin(TARGET_SCOPES)
].copy()

# =========================
# 4. 只保留核心指标
# =========================

TARGET_METRICS = [
    "购买转化率（访客口径）",
    "加购率（商品页浏览口径）",
    "购物车放弃率",
    "购物车完成率代理（派生）"
]

df = df[
    df["指标"].isin(TARGET_METRICS)
].copy()

# =========================
# 5. 整理月度明细
# =========================

monthly = df[
    [
        "范围",
        "行业",
        "地区",
        "月份",
        "指标",
        "值",
        "来源"
    ]
].copy()

monthly = monthly.rename(
    columns={
        "范围": "行业范围",
        "月份": "时间",
        "值": "benchmark_value"
    }
)

# =========================
# 6. 增加与TheLook的用途说明
# =========================

def get_thelook_metric(metric):

    mapping = {
        "购买转化率（访客口径）":
            "Product→Purchase CVR",

        "加购率（商品页浏览口径）":
            "Product→Cart Rate",

        "购物车放弃率":
            "Cart→Purchase Rate（反向参考）",

        "购物车完成率代理（派生）":
            "Cart→Purchase Rate"
    }

    return mapping.get(metric, "")


monthly["TheLook对应指标"] = (
    monthly["指标"]
    .apply(get_thelook_metric)
)

monthly["可比性"] = "不可直接数值比较"

monthly["用途"] = (
    "外部行业参考，不参与SKU low/severe异常阈值判断"
)

# =========================
# 7. 计算2025行业平均Benchmark
# =========================

summary = (
    monthly
    .groupby(
        [
            "行业范围",
            "行业",
            "地区",
            "指标",
            "TheLook对应指标",
            "可比性",
            "用途"
        ],
        dropna=False
    )
    .agg(
        benchmark_value=(
            "benchmark_value",
            "mean"
        ),
        month_count=(
            "时间",
            "nunique"
        )
    )
    .reset_index()
)

summary["时间"] = "2025"

summary["来源"] = (
    "Dynamic Yield XP² Ecommerce Benchmarks"
)

# 调整顺序
summary = summary[
    [
        "行业范围",
        "行业",
        "地区",
        "时间",
        "指标",
        "benchmark_value",
        "month_count",
        "来源",
        "TheLook对应指标",
        "可比性",
        "用途"
    ]
]

# =========================
# 8. 百分比显示字段
# =========================

summary["Benchmark"] = (
    summary["benchmark_value"]
    .apply(
        lambda x: f"{x:.2%}"
    )
)

monthly["Benchmark"] = (
    monthly["benchmark_value"]
    .apply(
        lambda x: f"{x:.2%}"
    )
)

# =========================
# 9. 最终行业基准对比表
# =========================

final_table = summary[
    [
        "行业范围",
        "地区",
        "时间",
        "指标",
        "Benchmark",
        "TheLook对应指标",
        "来源",
        "可比性",
        "用途"
    ]
].copy()

# =========================
# 10. 输出Excel
# =========================

with pd.ExcelWriter(
    OUTPUT_PATH,
    engine="openpyxl"
) as writer:

    final_table.to_excel(
        writer,
        sheet_name="行业基准对比表",
        index=False
    )

    monthly.to_excel(
        writer,
        sheet_name="2025月度明细",
        index=False
    )

print("生成完成：")
print(OUTPUT_PATH)

print("\n========== 行业基准对比表 ==========")

print(
    final_table.to_string(
        index=False
    )
)
