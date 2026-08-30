# import os
# import pandas as pd

# DATA_DIR = r"E:\agent\data"

# for file in os.listdir(DATA_DIR):

#     if not file.endswith(".csv"):
#         continue

#     path = os.path.join(DATA_DIR, file)

#     df = pd.read_csv(
#         path,
#         nrows=5
#     )

#     print("\n" + "=" * 60)
#     print(f"表名: {file}")
#     print(f"字段数: {len(df.columns)}")

#     for col in df.columns:
#         print(f"  - {col}")


import pandas as pd

path = r"E:\agent\data\events_old.csv"

df = pd.read_csv(path)

for event_type in df["event_type"].unique():

    print("\n" + "=" * 60)
    print("event_type:", event_type)

    sample = df[
        df["event_type"] == event_type
    ][
        [
            "user_id",
            "session_id",
            "sequence_number",
            "created_at",
            "uri",
            "event_type"
        ]
    ].head(5)

    print(sample.to_string(index=False))