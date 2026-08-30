# src/rules/conversion_anomaly.py

MIN_SESSIONS = 20
LOW_THRESHOLD = -0.30
SEVERE_THRESHOLD = -0.50


def detect_conversion_anomaly(
    product_sessions: int,
    purchase_cvr: float,
    category_cvr: float
) -> dict:
    """
    根据SKU转化率和Category Benchmark判断转化异常。

    参数：
    product_sessions:
        SKU商品详情页访问Session数

    purchase_cvr:
        SKU Product → Purchase CVR

    category_cvr:
        所属Category的Product → Purchase CVR

    返回：
        结构化异常检测结果
    """

    # =========================
    # 1. 样本量检查
    # =========================

    if product_sessions < MIN_SESSIONS:

        return {
            "status": "insufficient_data",
            "product_sessions": product_sessions,
            "purchase_cvr": purchase_cvr,
            "category_cvr": category_cvr,
            "cvr_deviation": None,
            "is_anomaly": False,
            "severity": None,
            "reason": (
                f"Product Sessions仅{product_sessions}，"
                f"低于最低样本量{MIN_SESSIONS}，"
                "暂不进行转化异常判断。"
            )
        }

    # =========================
    # 2. Benchmark有效性检查
    # =========================

    if category_cvr <= 0:

        return {
            "status": "invalid_benchmark",
            "product_sessions": product_sessions,
            "purchase_cvr": purchase_cvr,
            "category_cvr": category_cvr,
            "cvr_deviation": None,
            "is_anomaly": False,
            "severity": None,
            "reason": "Category Benchmark无效。"
        }

    # =========================
    # 3. 计算CVR偏离
    # =========================

    deviation = (
        purchase_cvr - category_cvr
    ) / category_cvr

    # =========================
    # 4. 严重异常
    # =========================

    if deviation <= SEVERE_THRESHOLD:

        status = "severe"
        is_anomaly = True
        severity = "severe"

    # =========================
    # 5. 一般异常
    # =========================

    elif deviation <= LOW_THRESHOLD:

        status = "low"
        is_anomaly = True
        severity = "low"

    # =========================
    # 6. 正常
    # =========================

    else:

        status = "normal"
        is_anomaly = False
        severity = None

    # =========================
    # 7. 返回结构化结果
    # =========================

    return {
        "status": status,
        "product_sessions": product_sessions,
        "purchase_cvr": round(purchase_cvr, 4),
        "category_cvr": round(category_cvr, 4),
        "cvr_deviation": round(deviation, 4),
        "is_anomaly": is_anomaly,
        "severity": severity,
        "reason": (
            f"SKU CVR为{purchase_cvr:.2%}，"
            f"Category Benchmark为{category_cvr:.2%}，"
            f"相对偏离{deviation:.2%}。"
        )
    }