import os
import pandas as pd


DATA_DIR = r"E:\agent\data"

EVENTS_PATH = os.path.join(
    DATA_DIR,
    "events_old.csv"
)

ORDER_ITEMS_PATH = os.path.join(
    DATA_DIR,
    "order_items.csv"
)


# ==================================================
# 1. 读取事件
# 只读取本次需要的字段
# ==================================================

print(
    "\n开始读取事件数据..."
)


events = pd.read_csv(
    EVENTS_PATH,
    usecols=[
        "id",
        "user_id",
        "session_id",
        "sequence_number",
        "created_at",
        "uri",
        "event_type"
    ]
)


events = events[
    events["event_type"].isin(
        [
            "product",
            "cart",
            "purchase"
        ]
    )
].copy()


events["product_id"] = (
    events["uri"]
    .astype(str)
    .str.extract(
        r"/product/(\d+)",
        expand=False
    )
)


events["product_id"] = pd.to_numeric(
    events["product_id"],
    errors="coerce"
)


events = events.sort_values(
    [
        "session_id",
        "sequence_number"
    ]
).reset_index(
    drop=True
)


print(
    f"目标事件数量：{len(events):,}"
)


# ==================================================
# 2. Session → Unique Product 数量
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "一、Session 中唯一商品数量分布"
)

print(
    "=" * 100
)


session_product_count = (
    events[
        events["event_type"]
        == "product"
    ]
    .groupby(
        "session_id"
    )["product_id"]
    .nunique()
)


distribution = (
    session_product_count
    .value_counts()
    .sort_index()
)


total_product_sessions = len(
    session_product_count
)


for product_count, session_count in (
    distribution.items()
):

    rate = (
        session_count
        /
        total_product_sessions
    )


    print(
        f"{product_count} 个唯一商品："
        f"{session_count:,} 个 Session "
        f"({rate:.2%})"
    )


single_product_sessions = (
    session_product_count
    == 1
).sum()


multi_product_sessions = (
    session_product_count
    > 1
).sum()


print(
    "\n商品浏览 Session 总数："
    f"{total_product_sessions:,}"
)

print(
    "单商品 Session："
    f"{single_product_sessions:,} "
    f"({single_product_sessions / total_product_sessions:.2%})"
)

print(
    "多商品 Session："
    f"{multi_product_sessions:,} "
    f"({multi_product_sessions / total_product_sessions:.2%})"
)


# ==================================================
# 3. Cart Session 中是否存在多商品
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "二、Cart Session 的商品数量"
)

print(
    "=" * 100
)


cart_sessions = set(
    events.loc[
        events["event_type"]
        == "cart",
        "session_id"
    ]
)


cart_product_counts = (
    session_product_count[
        session_product_count.index.isin(
            cart_sessions
        )
    ]
)


cart_total = len(
    cart_product_counts
)


cart_single = (
    cart_product_counts
    == 1
).sum()


cart_multi = (
    cart_product_counts
    > 1
).sum()


print(
    f"Cart Session 总数：{cart_total:,}"
)


if cart_total > 0:

    print(
        "单商品 Cart Session："
        f"{cart_single:,} "
        f"({cart_single / cart_total:.2%})"
    )

    print(
        "多商品 Cart Session："
        f"{cart_multi:,} "
        f"({cart_multi / cart_total:.2%})"
    )


# ==================================================
# 4. Purchase Session 中是否存在多商品
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "三、Purchase Session 的商品数量"
)

print(
    "=" * 100
)


purchase_sessions = set(
    events.loc[
        events["event_type"]
        == "purchase",
        "session_id"
    ]
)


purchase_product_counts = (
    session_product_count[
        session_product_count.index.isin(
            purchase_sessions
        )
    ]
)


purchase_total = len(
    purchase_product_counts
)


purchase_single = (
    purchase_product_counts
    == 1
).sum()


purchase_multi = (
    purchase_product_counts
    > 1
).sum()


print(
    f"Purchase Session 总数：{purchase_total:,}"
)


if purchase_total > 0:

    print(
        "单商品 Purchase Session："
        f"{purchase_single:,} "
        f"({purchase_single / purchase_total:.2%})"
    )

    print(
        "多商品 Purchase Session："
        f"{purchase_multi:,} "
        f"({purchase_multi / purchase_total:.2%})"
    )


# ==================================================
# 5. Cart 前一个事件是不是 Product
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "四、Cart 与前一个 Product Event 的关系"
)

print(
    "=" * 100
)


events["previous_event_type"] = (
    events
    .groupby(
        "session_id"
    )["event_type"]
    .shift(1)
)


events["previous_product_id"] = (
    events
    .groupby(
        "session_id"
    )["product_id"]
    .shift(1)
)


events["previous_sequence"] = (
    events
    .groupby(
        "session_id"
    )["sequence_number"]
    .shift(1)
)


cart_events = events[
    events["event_type"]
    == "cart"
].copy()


cart_events[
    "direct_previous_product"
] = (
    (
        cart_events[
            "previous_event_type"
        ]
        == "product"
    )
    &
    (
        cart_events[
            "sequence_number"
        ]
        -
        cart_events[
            "previous_sequence"
        ]
        == 1
    )
)


direct_cart_count = (
    cart_events[
        "direct_previous_product"
    ]
    .sum()
)


print(
    f"Cart事件总数：{len(cart_events):,}"
)

print(
    "前一事件直接为Product："
    f"{direct_cart_count:,}"
)


if len(
    cart_events
) > 0:

    print(
        "直接归因比例："
        f"{direct_cart_count / len(cart_events):.2%}"
    )


print(
    "\n无法直接通过前一Product归因的Cart示例："
)


unmatched_cart = (
    cart_events[
        ~cart_events[
            "direct_previous_product"
        ]
    ]
    .head(10)
)


if unmatched_cart.empty:

    print(
        "无，全部Cart都直接跟在Product之后。"
    )


else:

    print(
        unmatched_cart[
            [
                "session_id",
                "sequence_number",
                "previous_event_type",
                "previous_sequence",
                "uri"
            ]
        ].to_string(
            index=False
        )
    )


# ==================================================
# 6. Purchase Event 与 order_items 时间关联
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "五、Purchase Event 与 order_items 的精确关联"
)

print(
    "=" * 100
)


purchase_events = events[
    events["event_type"]
    == "purchase"
][
    [
        "session_id",
        "user_id",
        "created_at"
    ]
].copy()


purchase_events["user_id"] = (
    pd.to_numeric(
        purchase_events["user_id"],
        errors="coerce"
    )
    .astype(
        "Int64"
    )
)


order_items = pd.read_csv(
    ORDER_ITEMS_PATH,
    usecols=[
        "id",
        "order_id",
        "user_id",
        "product_id",
        "created_at"
    ]
)


order_items["user_id"] = (
    pd.to_numeric(
        order_items["user_id"],
        errors="coerce"
    )
    .astype(
        "Int64"
    )
)


# ==================================================
# 使用 user_id + created_at 比较
# 不直接many-to-many merge
# 先比较每个key出现次数
# ==================================================

purchase_key_counts = (
    purchase_events
    .groupby(
        [
            "user_id",
            "created_at"
        ],
        dropna=False
    )
    .size()
    .reset_index(
        name="purchase_event_count"
    )
)


order_key_counts = (
    order_items
    .groupby(
        [
            "user_id",
            "created_at"
        ],
        dropna=False
    )
    .size()
    .reset_index(
        name="order_item_count"
    )
)


key_compare = purchase_key_counts.merge(
    order_key_counts,
    on=[
        "user_id",
        "created_at"
    ],
    how="outer"
)


key_compare[
    "purchase_event_count"
] = (
    key_compare[
        "purchase_event_count"
    ]
    .fillna(0)
)


key_compare[
    "order_item_count"
] = (
    key_compare[
        "order_item_count"
    ]
    .fillna(0)
)


key_compare[
    "matched_count"
] = key_compare[
    [
        "purchase_event_count",
        "order_item_count"
    ]
].min(
    axis=1
)


matched_purchase_events = int(
    key_compare[
        "matched_count"
    ].sum()
)


total_purchase_events = len(
    purchase_events
)


print(
    f"Purchase Event数量：{total_purchase_events:,}"
)

print(
    f"order_items数量：{len(order_items):,}"
)

print(
    "user_id + created_at 可匹配Purchase数量："
    f"{matched_purchase_events:,}"
)


if total_purchase_events > 0:

    print(
        "精确匹配覆盖率："
        f"{matched_purchase_events / total_purchase_events:.2%}"
    )


count_mismatch = (
    key_compare[
        "purchase_event_count"
    ]
    !=
    key_compare[
        "order_item_count"
    ]
).sum()


print(
    f"数量不一致的Key数量：{count_mismatch:,}"
)


# ==================================================
# 7. 唯一键匹配
# Purchase → Product
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "六、可以唯一确定商品的Purchase比例"
)

print(
    "=" * 100
)


unique_purchase_keys = (
    key_compare[
        (
            key_compare[
                "purchase_event_count"
            ]
            == 1
        )
        &
        (
            key_compare[
                "order_item_count"
            ]
            == 1
        )
    ][
        [
            "user_id",
            "created_at"
        ]
    ]
)


unique_purchase_events = (
    purchase_events.merge(
        unique_purchase_keys,
        on=[
            "user_id",
            "created_at"
        ],
        how="inner"
    )
)


unique_order_items = (
    order_items.merge(
        unique_purchase_keys,
        on=[
            "user_id",
            "created_at"
        ],
        how="inner"
    )
)


purchase_product_map = (
    unique_purchase_events.merge(
        unique_order_items[
            [
                "user_id",
                "created_at",
                "order_id",
                "product_id"
            ]
        ],
        on=[
            "user_id",
            "created_at"
        ],
        how="inner"
    )
)


print(
    "唯一匹配Purchase数量："
    f"{len(purchase_product_map):,}"
)


if total_purchase_events > 0:

    print(
        "唯一商品归因比例："
        f"{len(purchase_product_map) / total_purchase_events:.2%}"
    )


# ==================================================
# 8. Purchase商品是否在该Session浏览过
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "七、购买商品是否在对应Session中浏览过"
)

print(
    "=" * 100
)


session_products = (
    events[
        events["event_type"]
        == "product"
    ]
    .dropna(
        subset=[
            "product_id"
        ]
    )
    .groupby(
        "session_id"
    )["product_id"]
    .agg(
        lambda x: set(
            x.astype(int)
        )
    )
    .to_dict()
)


purchase_product_map[
    "viewed_products"
] = (
    purchase_product_map[
        "session_id"
    ]
    .map(
        session_products
    )
)


purchase_product_map[
    "purchase_product_viewed"
] = (
    purchase_product_map.apply(
        lambda row:
        (
            int(
                row["product_id"]
            )
            in
            row["viewed_products"]
        )
        if isinstance(
            row["viewed_products"],
            set
        )
        else False,
        axis=1
    )
)


viewed_match_count = (
    purchase_product_map[
        "purchase_product_viewed"
    ]
    .sum()
)


print(
    "唯一归因Purchase中，"
    "购买商品曾在该Session浏览："
    f"{viewed_match_count:,}"
)


if len(
    purchase_product_map
) > 0:

    print(
        "浏览-购买商品一致率："
        f"{viewed_match_count / len(purchase_product_map):.2%}"
    )


# ==================================================
# 9. 输出多商品Purchase Session样例
# ==================================================

print(
    "\n"
    + "=" * 100
)

print(
    "八、多商品 Purchase Session 示例"
)

print(
    "=" * 100
)


multi_purchase_session_ids = (
    purchase_product_counts[
        purchase_product_counts
        > 1
    ]
    .index
    .tolist()[
        :10
    ]
)


if not multi_purchase_session_ids:

    print(
        "没有发现多商品 Purchase Session。"
    )


else:

    for session_id in (
        multi_purchase_session_ids
    ):

        one_session = events[
            events["session_id"]
            == session_id
        ]


        print(
            "\n"
            + "-" * 100
        )

        print(
            f"SESSION：{session_id}"
        )


        print(
            one_session[
                [
                    "user_id",
                    "sequence_number",
                    "created_at",
                    "event_type",
                    "uri",
                    "product_id"
                ]
            ].to_string(
                index=False
            )
        )


print(
    "\n"
    + "=" * 100
)

print(
    "归因结构检查完成"
)

print(
    "=" * 100
)
