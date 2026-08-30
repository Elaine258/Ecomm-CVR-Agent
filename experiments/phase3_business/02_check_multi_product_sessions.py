import pandas as pd

PATH = r"E:\agent\data\events_old.csv"

# 只读取需要的字段，减少内存占用
df = pd.read_csv(
    PATH,
    usecols=[
        "session_id",
        "sequence_number",
        "event_type",
        "uri"
    ]
)

# 只保留product事件
products = df[
    df["event_type"] == "product"
].copy()

# 从 /product/7535 提取 product_id
products["product_id"] = (
    products["uri"]
    .str.extract(r"/product/(\d+)")[0]
)

# 每个session访问了多少个不同商品
session_product_count = (
    products
    .groupby("session_id")["product_id"]
    .nunique()
)

# 统计
total_sessions = len(session_product_count)

single_product_sessions = (
    session_product_count == 1
).sum()

multi_product_sessions = (
    session_product_count > 1
).sum()

print("========== 统计结果 ==========")

print("访问过商品的Session总数:", total_sessions)

print(
    "只访问1个商品的Session:",
    single_product_sessions
)

print(
    "访问多个商品的Session:",
    multi_product_sessions
)

print(
    "单商品Session占比:",
    round(
        single_product_sessions
        / total_sessions
        * 100,
        2
    ),
    "%"
)

print(
    "多商品Session占比:",
    round(
        multi_product_sessions
        / total_sessions
        * 100,
        2
    ),
    "%"
)


# 查看访问商品数量分布
print("\n========== 商品数量分布 ==========")

print(
    session_product_count
    .value_counts()
    .sort_index()
    .head(20)
)


# 随机查看5个多商品Session
multi_session_ids = (
    session_product_count[
        session_product_count > 1
    ]
    .index
)

print("\n========== 多商品Session样例 ==========")

for session_id in multi_session_ids[:5]:

    sample = df[
        df["session_id"] == session_id
    ].sort_values("sequence_number")

    print("\n" + "=" * 80)
    print("Session:", session_id)

    print(
        sample[
            [
                "sequence_number",
                "event_type",
                "uri"
            ]
        ].to_string(index=False)
    )
