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


from src.conversion_diagnosis_agent import diagnose_product

from src.diagnosis_history import (
    get_latest_diagnosis,
    update_action_status
)


PRODUCT_ID = 7498


print("\n========== Step 1: First Diagnosis ==========")

first_result = diagnose_product(
    PRODUCT_ID
)

first_record = get_latest_diagnosis(
    PRODUCT_ID
)

print(
    "Diagnosis ID:",
    first_record.get("diagnosis_id")
)

print(
    "Effective Action:",
    first_record.get("effective_action")
)

print(
    "Action Status:",
    first_record.get("action_status")
)


print("\n========== Step 2: Mark Completed ==========")

update_action_status(
    diagnosis_id=
        first_record["diagnosis_id"],

    new_status=
        "completed"
)

completed_record = get_latest_diagnosis(
    PRODUCT_ID
)

print(
    "Action Status:",
    completed_record.get("action_status")
)


print("\n========== Step 3: Re-diagnosis ==========")

second_result = diagnose_product(
    PRODUCT_ID
)

second_record = get_latest_diagnosis(
    PRODUCT_ID
)


print("\n========== Step 4: Closed Loop Result ==========")

print(
    "Validation Result:",
    second_result.get(
        "validation_result"
    )
)

print(
    "Next Round Action:",
    second_result.get(
        "next_round_action"
    )
)

print(
    "Effective Action:",
    second_result.get(
        "effective_action"
    )
)


print("\n========== Step 5: History Check ==========")

print(
    "History Effective Action:",
    second_record.get(
        "effective_action"
    )
)

print(
    "History Action Status:",
    second_record.get(
        "action_status"
    )
)


print("\n========== Step 6: Binding Check ==========")

effective_action_match = (
    second_record.get(
        "effective_action"
    )
    ==
    second_result.get(
        "effective_action"
    )
)

status_is_pending = (
    second_record.get(
        "action_status"
    )
    ==
    "pending"
)


print(
    "Effective Action Match:",
    effective_action_match
)

print(
    "New Action Status Is Pending:",
    status_is_pending
)


if (
    effective_action_match
    and status_is_pending
):

    print(
        "\nStep 4.6 PASS"
    )

else:

    print(
        "\nStep 4.6 FAIL"
    )


'''
测试逻辑完整链路:
第一次诊断
→ 找到最新记录
→ 把这条记录改成 completed（已完成）
→ 再次诊断
→ 触发 Validation（效果验证）
→ 生成 next_round_action（下一轮行动）
→ effective_action（最终生效行动）被覆盖
→ 检查新 History（历史记录）
→ action_status 是否重新是 pending（待执行）
→ pending 对应的是否正是新的 effective_action
'''
