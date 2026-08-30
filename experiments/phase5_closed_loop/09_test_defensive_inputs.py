import sys
import os

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from src.diagnosis_history import (
    build_next_round_action
)


PREVIOUS_ACTION = {
    "priority": "P1",
    "action_type": "collect_data",
    "target_stage": "cart_to_purchase",
    "required_data": [
        "checkout_step_funnel"
    ],
    "reason":
        "Cart→Purchase被识别为当前主要异常阶段",
    "goal":
        "进一步定位购物车至购买环节中的具体转化阻力"
}


CURRENT_DIAGNOSIS = {
    "status": "severe",
    "weak_stage": "cart_to_purchase"
}


# ==================================================
# Case 1
# 非法 validation_result
# ==================================================

print(
    "\n========== Case 1: Invalid Validation Result =========="
)

try:

    result = build_next_round_action(
        validation_result=
            "invalid_status",

        current_diagnosis=
            CURRENT_DIAGNOSIS,

        previous_action=
            PREVIOUS_ACTION
    )

    print(
        "Result:",
        result
    )

    print(
        "Behavior: RETURNED_RESULT"
    )

except Exception as e:

    print(
        "Exception Type:",
        type(e).__name__
    )

    print(
        "Exception:",
        str(e)
    )

    print(
        "Behavior: RAISED_EXCEPTION"
    )


# ==================================================
# Case 2
# previous_action = None
# ==================================================

print(
    "\n========== Case 2: Missing Previous Action =========="
)

try:

    result = build_next_round_action(
        validation_result=
            "unchanged",

        current_diagnosis=
            CURRENT_DIAGNOSIS,

        previous_action=
            None
    )

    print(
        "Result:",
        result
    )

    print(
        "Behavior: RETURNED_RESULT"
    )

except Exception as e:

    print(
        "Exception Type:",
        type(e).__name__
    )

    print(
        "Exception:",
        str(e)
    )

    print(
        "Behavior: RAISED_EXCEPTION"
    )


# ==================================================
# Case 3
# current_diagnosis 缺 weak_stage
# ==================================================

print(
    "\n========== Case 3: Missing Weak Stage =========="
)

try:

    result = build_next_round_action(
        validation_result=
            "unchanged",

        current_diagnosis={
            "status":
                "severe"
        },

        previous_action=
            PREVIOUS_ACTION
    )

    print(
        "Result:",
        result
    )

    print(
        "Behavior: RETURNED_RESULT"
    )

except Exception as e:

    print(
        "Exception Type:",
        type(e).__name__
    )

    print(
        "Exception:",
        str(e)
    )

    print(
        "Behavior: RAISED_EXCEPTION"
    )


print(
    "\n========== Step 4.10 Observation Complete =========="
)
