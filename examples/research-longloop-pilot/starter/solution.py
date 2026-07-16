def predict(features: list[float]) -> int:
    return int(features[4] >= 0.0)
