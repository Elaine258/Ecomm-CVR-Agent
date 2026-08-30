import os
import pandas as pd


DATA_DIR = r"E:\agent\data"


# ==================================================
# 已知表用途说明
# ==================================================

TABLE_DESCRIPTIONS = {
    "events_old.csv":
        "用户行为事件表：记录用户在 Session 中发生的浏览、加购、购买等行为事件。",

    "orders.csv":
        "订单表：记录订单级信息，一个订单对应一条订单记录。",

    "order_items.csv":
        "订单商品明细表：记录订单中的具体商品，一个订单可能对应多条商品明细。",

    "products_old.csv":
        "商品表：记录商品名称、品类、品牌、零售价等商品属性。",

    "inventory_items_old.csv":
        "库存商品表：记录具体库存实例及其对应商品、成本、销售状态等信息。",

    "distribution_centers.csv":
        "配送中心表：记录配送中心名称及地理位置等信息。"
}


# ==================================================
# 自动寻找所有CSV
# ==================================================

csv_files = sorted(
    [
        file
        for file in os.listdir(DATA_DIR)
        if file.lower().endswith(".csv")
    ]
)


print(
    f"共找到 {len(csv_files)} 个 CSV 文件"
)


# ==================================================
# 逐表检查
# ==================================================

for file_name in csv_files:

    file_path = os.path.join(
        DATA_DIR,
        file_name
    )


    print(
        "\n"
        + "=" * 100
    )

    print(
        f"表名：{file_name}"
    )


    print(
        "表用途：",
        TABLE_DESCRIPTIONS.get(
            file_name,
            "暂未定义，后续根据实际字段判断。"
        )
    )


    try:

        df = pd.read_csv(
            file_path,
            nrows=5
        )


        print(
            f"\n字段数量：{len(df.columns)}"
        )


        print(
            "\n字段列表："
        )

        for index, column in enumerate(
            df.columns,
            start=1
        ):

            print(
                f"{index}. {column}"
            )


        print(
            "\n前5行数据："
        )

        print(
            df.to_string(
                index=False
            )
        )


        print(
            "\n字段类型："
        )

        print(
            df.dtypes.to_string()
        )


    except Exception as e:

        print(
            f"读取失败：{e}"
        )


print(
    "\n"
    + "=" * 100
)

print(
    "检查完成"
)
