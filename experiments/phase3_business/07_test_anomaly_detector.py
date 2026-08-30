import sys
import os

# 从脚本位置往上两级，定位到项目根目录 E:\agent
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(ROOT)


from src.rules.conversion_anomaly import (
    detect_conversion_anomaly
)


# =========================
# Case 1：严重异常
# =========================

result = detect_conversion_anomaly(
    product_sessions=23,
    purchase_cvr=0.0870,
    category_cvr=0.2693
)

print("Case 1:")
print(result)


# =========================
# Case 2：普通异常
# =========================

result = detect_conversion_anomaly(
    product_sessions=22,
    purchase_cvr=0.18,
    category_cvr=0.2693
)

print("\nCase 2:")
print(result)


# =========================
# Case 3：正常
# =========================

result = detect_conversion_anomaly(
    product_sessions=25,
    purchase_cvr=0.26,
    category_cvr=0.2693
)

print("\nCase 3:")
print(result)


# =========================
# Case 4：样本不足
# =========================

result = detect_conversion_anomaly(
    product_sessions=13,
    purchase_cvr=0.1538,
    category_cvr=0.2693
)

print("\nCase 4:")
print(result)
