from helioguard.predictor import EXTENDED_FEATURE_COLUMNS, _series_features, build_feature_frame
import pandas as pd

def test_series_features_empty():
    empty_series = pd.Series([], dtype=float)
    features = _series_features(empty_series, "test", default_val=42.0)
    assert features["test_last"] == 42.0
    assert features["test_mean"] == 42.0
    assert features["test_min"] == 42.0
    assert features["test_max"] == 42.0
    # standard deviation and slope are 0 by default when empty
    assert features["test_std"] == 0.0
    assert features["test_slope"] == 0.0

def test_series_features_valid():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    features = _series_features(series, "test")
    assert features["test_last"] == 5.0
    assert features["test_mean"] == 3.0
    assert features["test_min"] == 1.0
    assert features["test_max"] == 5.0
    # slope = (last - first) / max(len - 1, 1) = (5 - 1) / 4 = 1.0
    assert features["test_slope"] == 1.0

def test_build_feature_frame_imputation():
    # If a dataframe lacks columns, it gets physically meaningful defaults instead of 0
    empty_history = pd.DataFrame()
    frame = build_feature_frame(
        empty_history,
        local_magnetic_latitude=35.0,
        feature_columns=EXTENDED_FEATURE_COLUMNS,
    )
    
    # Verify exact default imputations
    assert frame["speed_10m_mean"].iloc[0] == 400.0
    assert frame["density_60m_mean"].iloc[0] == 5.0
    assert frame["bt_10m_last"].iloc[0] == 5.0
    assert frame["temperature_10m_last"].iloc[0] == 100000.0
    assert frame["bz_360m_last"].iloc[0] == 0.0
    assert frame["local_magnetic_latitude"].iloc[0] == 35.0
    assert frame["sample_count"].iloc[0] == 0.0
    assert frame["sample_count_360m"].iloc[0] == 0.0
    assert 0.0 <= frame["local_solar_hour"].iloc[0] < 24.0
    assert frame["is_daylight"].iloc[0] in (0.0, 1.0)
