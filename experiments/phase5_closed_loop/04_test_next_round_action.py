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
    build_next_round_action
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
        "至少需要两次诊断记录"
    )


previous_record = history[-2]
current_record = history[-1]


# ==================================================
# 2. 获取上一轮验证结果
# ==================================================

validation_result = previous_record.get(
    "validation_result"
)


print(
    "\n========== Validation Result =========="
)

print(
    validation_result
)


# ==================================================
# 3. 构造当前诊断
# ==================================================

current_diagnosis = {
    "status":
        current_record.get(
            "status"
        ),

    "weak_stage":
        current_record.get(
            "weak_stage"
        ),

    "purchase_cvr":
        current_record.get(
            "purchase_cvr"
        )
}


# ==================================================
# 4. 生成下一轮Action
# ==================================================

next_round_action = build_next_round_action(
    validation_result=
        validation_result,

    current_diagnosis=
        current_diagnosis,

    previous_action=
        previous_record.get(
            "next_action"
        )
)


print(
    "\n========== Next Round Action =========="
)

print(
    next_round_action
)
