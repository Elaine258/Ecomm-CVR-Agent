import os
import re
import pandas as pd


DATA_DIR = r"E:\agent\data"

EVENTS_PATH = os.path.join(
    DATA_DIR,
    "events_old.csv"
)

TARGET_EVENTS = [
    "product",
    "cart",
    "purchase"
]

USECOLS = [
    "id",
    "user_id",
    "sequence_number",
    "session_id",
    "created_at",
    "uri",
    "event_type"
]

CHUNK_SIZE = 200000


# ==================================================
# 1. 初始化统计容器
# ==================================================

event_counts = {
    event_type: 0
    for event_type in TARGET_EVENTS
}

user_notnull_counts = {
    event_type: 0
    for event_type in TARGET_EVENTS
}

samples = {
    event_type: []
    for event_type in TARGET_EVENTS
}

uri_counts = {
    event_type: {}
    for event_type in TARGET_EVENTS
}

session_event_types = {}


# ==================================================
# 2. 第一遍扫描 events
# ==================================================

print(
    "\n开始扫描 events_old.csv..."
)


for chunk in pd.read_csv(
    EVENTS_PATH,
    usecols=USECOLS,
    chunksize=CHUNK_SIZE
):

    chunk = chunk[
        chunk["event_type"].isin(
            TARGET_EVENTS
        )
    ].copy()


    # ----------------------------------------------
    # A. 每类事件统计
    # ----------------------------------------------

    for event_type in TARGET_EVENTS:

        part = chunk[
            chunk["event_type"]
            == event_type
        ]


        event_counts[
            event_type
        ] += len(part)


        user_notnull_counts[
            event_type
        ] += (
            part["user_id"]
            .notna()
            .sum()
        )


        # ------------------------------------------
        # 保存前5条样本
        # ------------------------------------------

        remaining = (
            5
            -
            len(
                samples[
                    event_type
                ]
            )
        )


        if remaining > 0:

            rows = (
                part
                .head(
                    remaining
                )
                .to_dict(
                    "records"
                )
            )

            samples[
                event_type
            ].extend(
                rows
            )


        # ------------------------------------------
        # URI频率
        # ------------------------------------------

        uri_value_counts = (
            part["uri"]
            .fillna(
                "<NULL>"
            )
            .value_counts()
        )


        for uri, count in (
            uri_value_counts.items()
        ):

            uri_counts[
                event_type
            ][uri] = (
                uri_counts[
                    event_type
                ].get(
                    uri,
                    0
                )
                +
                count
            )


    # ----------------------------------------------
    # B. 收集Session包含哪些目标事件
    # ----------------------------------------------

    grouped = (
        chunk
        .groupby(
            "session_id"
        )["event_type"]
        .agg(
            set
        )
    )


    for session_id, event_set in (
        grouped.items()
    ):

        if session_id not in (
            session_event_types
        ):

            session_event_types[
                session_id
            ] = set()


        session_event_types[
            session_id
        ].update(
            event_set
        )


print(
    "第一遍扫描完成。"
)


# ==================================================
# 3. 打印三类事件基础统计
# ==================================================

print(
    "\n"
    +
    "=" * 100
)

print(
    "一、product / cart / purchase 事件统计"
)

print(
    "=" * 100
)


for event_type in TARGET_EVENTS:

    count = event_counts[
        event_type
    ]

    nonnull = (
        user_notnull_counts[
            event_type
        ]
    )


    if count > 0:

        nonnull_rate = (
            nonnull
            /
            count
        )

    else:

        nonnull_rate = 0


    print(
        f"\n事件类型：{event_type}"
    )

    print(
        f"事件数量：{count:,}"
    )

    print(
        f"user_id 非空数量：{nonnull:,}"
    )

    print(
        f"user_id 非空比例：{nonnull_rate:.2%}"
    )


# ==================================================
# 4. 打印前5条事件
# ==================================================

print(
    "\n"
    +
    "=" * 100
)

print(
    "二、每种事件前5条样本"
)

print(
    "=" * 100
)


for event_type in TARGET_EVENTS:

    print(
        f"\n--- {event_type.upper()} ---"
    )


    df = pd.DataFrame(
        samples[
            event_type
        ]
    )


    if df.empty:

        print(
            "没有找到数据"
        )

        continue


    print(
        df[
            [
                "user_id",
                "session_id",
                "sequence_number",
                "created_at",
                "uri",
                "event_type"
            ]
        ].to_string(
            index=False
        )
    )


# ==================================================
# 5. URI模式
# ==================================================

print(
    "\n"
    +
    "=" * 100
)

print(
    "三、每种事件最常见 URI"
)

print(
    "=" * 100
)


for event_type in TARGET_EVENTS:

    print(
        f"\n--- {event_type.upper()} URI TOP 10 ---"
    )


    sorted_uris = sorted(
        uri_counts[
            event_type
        ].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]


    for uri, count in sorted_uris:

        print(
            f"{uri:<40} {count:,}"
        )


# ==================================================
# 6. 检查URI能否提取product_id
# ==================================================

print(
    "\n"
    +
    "=" * 100
)

print(
    "四、URI 是否包含 product_id"
)

print(
    "=" * 100
)


product_pattern = re.compile(
    r"/product/(\d+)"
)


for event_type in TARGET_EVENTS:

    total = 0
    matched = 0
    examples = []


    for uri, count in (
        uri_counts[
            event_type
        ].items()
    ):

        total += count


        match = product_pattern.search(
            str(
                uri
            )
        )


        if match:

            matched += count


            if len(
                examples
            ) < 5:

                examples.append(
                    (
                        uri,
                        match.group(
                            1
                        )
                    )
                )


    if total > 0:

        match_rate = (
            matched
            /
            total
        )

    else:

        match_rate = 0


    print(
        f"\n事件类型：{event_type}"
    )

    print(
        f"URI可提取product_id比例：{match_rate:.2%}"
    )


    if examples:

        print(
            "示例："
        )


        for uri, product_id in examples:

            print(
                f"  {uri} → product_id={product_id}"
            )


    else:

        print(
            "未发现可直接提取product_id的URI"
        )


# ==================================================
# 7. 找完整漏斗Session
# product + cart + purchase
# ==================================================

complete_sessions = []


required_set = {
    "product",
    "cart",
    "purchase"
}


for session_id, event_set in (
    session_event_types.items()
):

    if required_set.issubset(
        event_set
    ):

        complete_sessions.append(
            session_id
        )


    if len(
        complete_sessions
    ) >= 5:

        break


print(
    "\n"
    +
    "=" * 100
)

print(
    "五、找到的完整漏斗 Session"
)

print(
    "=" * 100
)


print(
    f"本次准备查看 {len(complete_sessions)} 个 Session"
)


for session_id in complete_sessions:

    print(
        session_id
    )


# ==================================================
# 8. 第二遍读取
# 打印这些Session的完整事件路径
# ==================================================

if complete_sessions:

    session_rows = []


    for chunk in pd.read_csv(
        EVENTS_PATH,
        usecols=USECOLS,
        chunksize=CHUNK_SIZE
    ):

        part = chunk[
            chunk["session_id"]
            .isin(
                complete_sessions
            )
        ].copy()


        if not part.empty:

            session_rows.append(
                part
            )


    all_session_events = (
        pd.concat(
            session_rows,
            ignore_index=True
        )
    )


    all_session_events = (
        all_session_events
        .sort_values(
            [
                "session_id",
                "sequence_number"
            ]
        )
    )


    # ----------------------------------------------
    # 从URI提取product_id
    # ----------------------------------------------

    all_session_events[
        "uri_product_id"
    ] = (
        all_session_events["uri"]
        .astype(
            str
        )
        .str.extract(
            r"/product/(\d+)",
            expand=False
        )
    )


    print(
        "\n"
        +
        "=" * 100
    )

    print(
        "六、完整 Session 行为路径"
    )

    print(
        "=" * 100
    )


    for session_id in (
        complete_sessions
    ):

        print(
            "\n"
            +
            "-" * 100
        )

        print(
            f"SESSION：{session_id}"
        )

        print(
            "-" * 100
        )


        one_session = (
            all_session_events[
                all_session_events[
                    "session_id"
                ]
                == session_id
            ]
        )


        print(
            one_session[
                [
                    "user_id",
                    "sequence_number",
                    "created_at",
                    "event_type",
                    "uri",
                    "uri_product_id"
                ]
            ].to_string(
                index=False
            )
        )


        viewed_products = (
            one_session[
                "uri_product_id"
            ]
            .dropna()
            .unique()
            .tolist()
        )


        print(
            "\n该Session浏览过的商品：",
            viewed_products
        )


print(
    "\n"
    +
    "=" * 100
)

print(
    "检查完成"
)

print(
    "=" * 100
)
