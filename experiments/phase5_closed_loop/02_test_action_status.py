import os
import sys

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../.."
    )
)

if ROOT not in sys.path:
    sys.path.insert(
        0,
        ROOT
    )


from src.diagnosis_history import (
    get_product_history,
    update_action_status
)


product_id = 7498


# ==================================================
# 1. 获取历史记录
# ==================================================

history = get_product_history(
    product_id
)


if not history:
    raise ValueError(
        f"product_id={product_id}没有诊断历史"
    )


latest_record = history[-1]

diagnosis_id = latest_record[
    "diagnosis_id"
]


print(
    "\n========== Before =========="
)

print(
    "Diagnosis ID:",
    diagnosis_id
)

print(
    "Action Status:",
    latest_record.get(
        "action_status"
    )
)


# ==================================================
# 2. 更新状态
# ==================================================

updated_record = update_action_status(
    diagnosis_id=
        diagnosis_id,

    new_status=
        "completed"
)


print(
    "\n========== After =========="
)

print(
    "Diagnosis ID:",
    updated_record[
        "diagnosis_id"
    ]
)

print(
    "Action Status:",
    updated_record[
        "action_status"
    ]
)
