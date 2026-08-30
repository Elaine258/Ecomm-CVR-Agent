import os
import pandas as pd


DATA_DIR = r"E:\agent\data"

EVENTS_PATH = os.path.join(
    DATA_DIR,
    "events_old.csv"
)


# ==================================================
# 1. 读取需要的事件
# ==================================================

events = pd.read_csv(
    EVENTS_PATH,
    usecols=[
        "session_id",
        "event_type"
    ]
)


events = events[
    events["event_type"].isin(
        [
            "cart",
            "purchase"
        ]
    )
]


# ==================================================
# 2. 构造 Session 集合
# ==================================================

cart_sessions = set(
    events.loc[
        events["event_type"] == "cart",
        "session_id"
    ]
)


purchase_sessions = set(
    events.loc[
        events["event_type"] == "purchase",
        "session_id"
    ]
)


# ==================================================
# 3. 检查 Purchase 是否全部包含在 Cart 中
# ==================================================

purchase_without_cart = (
    purchase_sessions
    -
    cart_sessions
)


purchase_with_cart = (
    purchase_sessions
    &
    cart_sessions
)


# ==================================================
# 4. 输出结果
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "Purchase → Cart 完整性检查"
)

print(
    "=" * 100
)


print(
    f"Cart Session 数量："
    f"{len(cart_sessions):,}"
)


print(
    f"Purchase Session 数量："
    f"{len(purchase_sessions):,}"
)


print(
    f"同时存在 Cart 的 Purchase Session："
    f"{len(purchase_with_cart):,}"
)


print(
    f"没有 Cart 的 Purchase Session："
    f"{len(purchase_without_cart):,}"
)


if purchase_sessions:

    coverage_rate = (
        len(purchase_with_cart)
        /
        len(purchase_sessions)
    )

else:

    coverage_rate = 0


print(
    f"Purchase 前存在 Cart 的覆盖率："
    f"{coverage_rate:.2%}"
)


# ==================================================
# 5. 判断结果
# ==================================================

print(
    "\n"
    + "-" * 100
)


if len(purchase_without_cart) == 0:

    print(
        "PASS：所有 Purchase Session 都属于 Cart Session。"
    )

    print(
        "即：Purchase Sessions ⊆ Cart Sessions"
    )


else:

    print(
        "WARNING：存在 Purchase Session 没有对应 Cart。"
    )


    print(
        "\n前10个异常 Session："
    )


    for session_id in list(
        purchase_without_cart
    )[:10]:

        print(
            session_id
        )


print(
    "=" * 100
)
