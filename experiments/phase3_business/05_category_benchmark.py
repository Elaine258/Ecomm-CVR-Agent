import pandas as pd

EVENTS_PATH = r"E:\agent\data\events_old.csv"
PRODUCTS_PATH = r"E:\agent\data\products_old.csv"

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
        "category"
    ]
)

# =========================
# 2. 提取Product事件
# =========================

product_events = events[
    events["event_type"] == "product"
].copy()

# /product/7535 → 7535
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
# 4. 关联商品Category
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
# 5. 获取Cart / Purchase Session
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
# 6. 给每个商品Session打标签
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
# 7. 按Category聚合
# =========================

category_benchmark = (
    session_products
    .groupby("category")
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

# =========================
# 8. 计算Category转化指标
# =========================

category_benchmark["cart_rate"] = (
    category_benchmark["cart_sessions"]
    / category_benchmark["product_sessions"]
)

category_benchmark["purchase_cvr"] = (
    category_benchmark["purchase_sessions"]
    / category_benchmark["product_sessions"]
)

category_benchmark["cart_to_purchase_rate"] = (
    category_benchmark["purchase_sessions"]
    / category_benchmark["cart_sessions"]
)

# =========================
# 9. 按CVR排序
# =========================

category_benchmark = (
    category_benchmark
    .sort_values(
        "purchase_cvr",
        ascending=False
    )
    .reset_index(drop=True)
)

# =========================
# 10. 输出
# =========================

print("========== Category Benchmark ==========")

display_result = category_benchmark.copy()

display_result["cart_rate"] = (
    display_result["cart_rate"]
    .map(lambda x: f"{x:.2%}")
)

display_result["purchase_cvr"] = (
    display_result["purchase_cvr"]
    .map(lambda x: f"{x:.2%}")
)

display_result["cart_to_purchase_rate"] = (
    display_result["cart_to_purchase_rate"]
    .map(lambda x: f"{x:.2%}")
)

print(
    display_result.to_string(
        index=False
    )
)

print(
    "\nCategory数量:",
    len(category_benchmark)
)
