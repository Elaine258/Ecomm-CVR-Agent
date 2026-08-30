import pandas as pd

PATH = r"E:\agent\data\events_old.csv"

df = pd.read_csv(
    PATH,
    usecols=[
        "session_id",
        "event_type"
    ]
)

# =========================
# 1. 商品访问 Session
# =========================

product_sessions = set(
    df.loc[
        df["event_type"] == "product",
        "session_id"
    ].dropna().unique()
)

# =========================
# 2. 加购 Session
# =========================

cart_sessions = set(
    df.loc[
        df["event_type"] == "cart",
        "session_id"
    ].dropna().unique()
)

# =========================
# 3. 购买 Session
# =========================

purchase_sessions = set(
    df.loc[
        df["event_type"] == "purchase",
        "session_id"
    ].dropna().unique()
)

# =========================
# 4. 必须以访问过商品为前提
# =========================

product_to_cart_sessions = (
    product_sessions
    & cart_sessions
)

product_to_purchase_sessions = (
    product_sessions
    & purchase_sessions
)

cart_to_purchase_sessions = (
    cart_sessions
    & purchase_sessions
)

# =========================
# 5. 指标计算
# =========================

product_session_count = len(product_sessions)

cart_session_count = len(product_to_cart_sessions)

purchase_session_count = len(
    product_to_purchase_sessions
)

product_to_cart_rate = (
    cart_session_count
    / product_session_count
)

purchase_cvr = (
    purchase_session_count
    / product_session_count
)

cart_to_purchase_rate = (
    len(cart_to_purchase_sessions)
    / len(cart_sessions)
)

# =========================
# 6. 输出
# =========================

print("========== 全站行为漏斗 ==========")

print(
    "Product Session:",
    product_session_count
)

print(
    "Cart Session:",
    cart_session_count
)

print(
    "Purchase Session:",
    purchase_session_count
)

print("\n========== 转化指标 ==========")

print(
    "Product → Cart 加购率:",
    f"{product_to_cart_rate:.2%}"
)

print(
    "Product → Purchase CVR:",
    f"{purchase_cvr:.2%}"
)

print(
    "Cart → Purchase 转化率:",
    f"{cart_to_purchase_rate:.2%}"
)
