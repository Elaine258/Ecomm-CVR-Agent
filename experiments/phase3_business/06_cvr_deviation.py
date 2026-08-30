import pandas as pd

EVENTS_PATH = r"E:\agent\data\events_old.csv"
PRODUCTS_PATH = r"E:\agent\data\products_old.csv"

MIN_SESSIONS = 20


# =========================
# 1. 读取数据
# =========================

events = pd.read_csv(
    EVENTS_PATH,
    usecols=[
        "session_id",
        "event_type",
        "uri"
    ]
)

products = pd.read_csv(
    PRODUCTS_PATH,
    usecols=[
        "id",
        "name",
        "category",
        "brand",
        "retail_price"
    ]
)


# =========================
# 2. 提取Product事件
# =========================

product_events = events[
    events["event_type"] == "product"
].copy()

product_events["product_id"] = (
    product_events["uri"]
    .str.extract(r"/product/(\d+)")[0]
)

product_events["product_id"] = pd.to_numeric(
    product_events["product_id"],
    errors="coerce"
)

product_events = product_events.dropna(
    subset=["product_id"]
)

product_events["product_id"] = (
    product_events["product_id"]
    .astype(int)
)


# =========================
# 3. 一个Session只保留一个商品
# =========================

session_products = (
    product_events[
        ["session_id", "product_id"]
    ]
    .drop_duplicates()
)


# =========================
# 4. 关联商品信息
# =========================

products = products.rename(
    columns={
        "id": "product_id"
    }
)

session_products = session_products.merge(
    products,
    on="product_id",
    how="left"
)


# =========================
# 5. Cart / Purchase Session
# =========================

cart_sessions = set(
    events.loc[
        events["event_type"] == "cart",
        "session_id"
    ]
    .dropna()
    .unique()
)

purchase_sessions = set(
    events.loc[
        events["event_type"] == "purchase",
        "session_id"
    ]
    .dropna()
    .unique()
)


# =========================
# 6. 给每个Session打标签
# =========================

session_products["has_cart"] = (
    session_products["session_id"]
    .isin(cart_sessions)
)

session_products["has_purchase"] = (
    session_products["session_id"]
    .isin(purchase_sessions)
)


# =========================
# 7. SKU级CVR
# =========================

sku_cvr = (
    session_products
    .groupby(
        [
            "product_id",
            "name",
            "category",
            "brand",
            "retail_price"
        ],
        dropna=False
    )
    .agg(
        product_sessions=(
            "session_id",
            "nunique"
        ),
        cart_sessions=(
            "has_cart",
            "sum"
        ),
        purchase_sessions=(
            "has_purchase",
            "sum"
        )
    )
    .reset_index()
)

sku_cvr["purchase_cvr"] = (
    sku_cvr["purchase_sessions"]
    / sku_cvr["product_sessions"]
)


# =========================
# 8. Category Benchmark
# =========================

category_benchmark = (
    session_products
    .groupby("category")
    .agg(
        category_product_sessions=(
            "session_id",
            "nunique"
        ),
        category_purchase_sessions=(
            "has_purchase",
            "sum"
        )
    )
    .reset_index()
)

category_benchmark["category_cvr"] = (
    category_benchmark[
        "category_purchase_sessions"
    ]
    /
    category_benchmark[
        "category_product_sessions"
    ]
)


# =========================
# 9. SKU合并Category Benchmark
# =========================

result = sku_cvr.merge(
    category_benchmark[
        [
            "category",
            "category_cvr"
        ]
    ],
    on="category",
    how="left"
)


# =========================
# 10. 计算CVR偏离程度
# =========================

result["cvr_deviation"] = (
    (
        result["purchase_cvr"]
        - result["category_cvr"]
    )
    /
    result["category_cvr"]
)


# =========================
# 11. 样本量资格
# =========================

result["sample_status"] = (
    result["product_sessions"]
    .apply(
        lambda x:
        "eligible"
        if x >= MIN_SESSIONS
        else "insufficient_data"
    )
)


# =========================
# 12. 输出展示
# =========================

display = result[
    [
        "product_id",
        "name",
        "category",
        "product_sessions",
        "purchase_sessions",
        "purchase_cvr",
        "category_cvr",
        "cvr_deviation",
        "sample_status"
    ]
].copy()

for col in [
    "purchase_cvr",
    "category_cvr",
    "cvr_deviation"
]:
    display[col] = (
        display[col]
        .map(lambda x: f"{x:.2%}")
    )


print(
    "========== SKU vs Category Benchmark =========="
)

print(
    display.head(30).to_string(
        index=False
    )
)


# =========================
# 13. 查看合格SKU数量
# =========================

eligible_count = (
    result["sample_status"]
    == "eligible"
).sum()

print(
    "\n合格SKU数量:",
    eligible_count
)

print(
    "合格SKU占比:",
    f"{eligible_count / len(result):.2%}"
)


# =========================
# 14. 查看偏离最低的SKU
# =========================

eligible = result[
    result["sample_status"]
    == "eligible"
].copy()

lowest = (
    eligible
    .sort_values(
        "cvr_deviation"
    )
    .head(20)
)

lowest_display = lowest[
    [
        "product_id",
        "name",
        "category",
        "product_sessions",
        "purchase_cvr",
        "category_cvr",
        "cvr_deviation"
    ]
].copy()

for col in [
    "purchase_cvr",
    "category_cvr",
    "cvr_deviation"
]:
    lowest_display[col] = (
        lowest_display[col]
        .map(lambda x: f"{x:.2%}")
    )

print(
    "\n========== CVR偏离最低SKU =========="
)

print(
    lowest_display.to_string(
        index=False
    )
)

# =========================
# 15. eligible SKU偏离分布
# =========================

eligible = result[
    result["sample_status"] == "eligible"
].copy()

print("\n========== CVR偏离分位数 ==========")

quantiles = eligible["cvr_deviation"].quantile(
    [
        0.01,
        0.05,
        0.10,
        0.20,
        0.25,
        0.50,
        0.75,
        0.80,
        0.90,
        0.95,
        0.99
    ]
)

for q, value in quantiles.items():
    print(
        f"P{int(q * 100):02d}:",
        f"{value:.2%}"
    )


# =========================
# 16. 查看不同偏离区间的SKU数量
# =========================

print("\n========== CVR偏离区间分布 ==========")

ranges = {
    "<= -50%": (
        eligible["cvr_deviation"] <= -0.50
    ),

    "-50% ~ -30%": (
        (eligible["cvr_deviation"] > -0.50)
        &
        (eligible["cvr_deviation"] <= -0.30)
    ),

    "-30% ~ -20%": (
        (eligible["cvr_deviation"] > -0.30)
        &
        (eligible["cvr_deviation"] <= -0.20)
    ),

    "-20% ~ 0%": (
        (eligible["cvr_deviation"] > -0.20)
        &
        (eligible["cvr_deviation"] < 0)
    ),

    ">= 0%": (
        eligible["cvr_deviation"] >= 0
    )
}

for name, condition in ranges.items():

    count = condition.sum()

    ratio = count / len(eligible)

    print(
        f"{name:15s}",
        f"{count:5d} SKU",
        f"({ratio:.2%})"
    )
