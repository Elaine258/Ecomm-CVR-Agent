import pandas as pd

PATH = r"E:\agent\data\events_old.csv"

df = pd.read_csv(PATH)

# 按session和行为顺序排序
df = df.sort_values(
    ["session_id", "sequence_number"]
)

# 找出发生过purchase的session
purchase_sessions = (
    df.loc[
        df["event_type"] == "purchase",
        "session_id"
    ]
    .drop_duplicates()
    .head(10)
)

# 查看完整行为链
for session_id in purchase_sessions:

    session = df[
        df["session_id"] == session_id
    ]

    print("\n" + "=" * 80)
    print("Session:", session_id)

    print(
        session[
            [
                "sequence_number",
                "event_type",
                "uri",
                "created_at"
            ]
        ].to_string(index=False)
    )
