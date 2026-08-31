from src.rules.conversion_anomaly import detect_conversion_anomaly


def test_severe_anomaly():
    result = detect_conversion_anomaly(
        product_sessions=23,
        purchase_cvr=0.087,
        category_cvr=0.2693
    )

    assert result["status"] == "severe"
    assert result["is_anomaly"] is True
    assert result["severity"] == "severe"


def test_low_anomaly():
    result = detect_conversion_anomaly(
        product_sessions=22,
        purchase_cvr=0.18,
        category_cvr=0.2693
    )

    assert result["status"] == "low"
    assert result["is_anomaly"] is True
    assert result["severity"] == "low"


def test_normal():
    result = detect_conversion_anomaly(
        product_sessions=25,
        purchase_cvr=0.26,
        category_cvr=0.2693
    )

    assert result["status"] == "normal"
    assert result["is_anomaly"] is False
    assert result["severity"] is None


def test_insufficient_data():
    result = detect_conversion_anomaly(
        product_sessions=13,
        purchase_cvr=0.1538,
        category_cvr=0.2693
    )

    assert result["status"] == "insufficient_data"
    assert result["is_anomaly"] is False
    assert result["cvr_deviation"] is None