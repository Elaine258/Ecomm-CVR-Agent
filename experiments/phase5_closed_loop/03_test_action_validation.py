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
    validate_action
)


product_id = 7498


# ==================================================
# 1. 获取历史
# ==================================================

history = get_product_history(
    product_id
)


if len(history) < 2:
    raise ValueError(
        "至少需要两次诊断记录才能进行验证"
    )


previous_record = history[-2]
current_record = history[-1]


# ==================================================
# 2. 构造对比结果
# ==================================================

comparison = {
    "has_previous": True,

    "previous_status":
        previous_record.get("status"),

    "current_status":
        current_record.get("status"),

    "purchase_cvr_change":
        (
            current_record.get("purchase_cvr")
            -
            previous_record.get("purchase_cvr")
        )
}


print(
    "\n========== Before Validation =========="
)

print(
    "Previous Diagnosis ID:",
    previous_record["diagnosis_id"]
)

print(
    "Action Status:",
    previous_record.get(
        "action_status"
    )
)


# ==================================================
# 3. 验证Action
# ==================================================

updated_record = validate_action(
    diagnosis_id=
        previous_record[
            "diagnosis_id"
        ],

    comparison=
        comparison
)


print(
    "\n========== After Validation =========="
)

print(
    "Action Status:",
    updated_record[
        "action_status"
    ]
)

print(
    "Validation Result:",
    updated_record[
        "validation_result"
    ]
)
