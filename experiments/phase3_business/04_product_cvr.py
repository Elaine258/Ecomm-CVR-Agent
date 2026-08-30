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
        "name",
        "category",
        "brand",
        "retail_price"
    ]
)

# =========================
# 2. 提取每个Session对应的product_id
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
    product_events["product_id"].astype(int)
)

# 一个Session只对应一个商品
# 同一个Session重复访问同一商品，只保留一次
session_products = (
    product_events[
        ["session_id", "product_id"]
    ]
    .drop_duplicates()
)

# =========================
# 3. 找出Cart / Purchase Session
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
# 4. 给每个商品Session打标签
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
# 5. 按product_id聚合
# =========================

product_cvr = (
    session_products
    .groupby("product_id")
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
# 6. 计算三个转化指标
# =========================

product_cvr["cart_rate"] = (
    product_cvr["cart_sessions"]
    / product_cvr["product_sessions"]
)

product_cvr["purchase_cvr"] = (
    product_cvr["purchase_sessions"]
    / product_cvr["product_sessions"]
)

product_cvr["cart_to_purchase_rate"] = (
    product_cvr["purchase_sessions"]
    / product_cvr["cart_sessions"]
)

# =========================
# 7. 关联商品信息
# =========================

products = products.rename(
    columns={
        "id": "product_id"
    }
)

result = product_cvr.merge(
    products,
    on="product_id",
    how="left"
)

# =========================
# 8. 调整字段顺序
# =========================

result = result[
    [
        "product_id",
        "name",
        "category",
        "brand",
        "retail_price",
        "product_sessions",
        "cart_sessions",
        "purchase_sessions",
        "cart_rate",
        "purchase_cvr",
        "cart_to_purchase_rate"
    ]
]

# =========================
# 9. 查看结果
# =========================

print("========== SKU级转化率 ==========")

print(
    result.head(20).to_string(
        index=False
    )
)

print("\n========== 基础统计 ==========")

print(
    "SKU数量:",
    len(result)
)

print(
    "平均SKU CVR:",
    f'{result["purchase_cvr"].mean():.2%}'
)

print(
    "SKU CVR中位数:",
    f'{result["purchase_cvr"].median():.2%}'
)

print(
    "最少Product Session:",
    result["product_sessions"].min()
)

print(
    "最多Product Session:",
    result["product_sessions"].max()
)

print("\n========== 样本量分布 ==========")

for threshold in [5, 10, 15, 20, 25, 30, 40, 50]:

    count = (
        result["product_sessions"] >= threshold
    ).sum()

    ratio = count / len(result)

    print(
        f">= {threshold:2d} Sessions:",
        f"{count:5d} SKU",
        f"({ratio:.2%})"
    )
