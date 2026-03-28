from helioguard.analysis import classify_xray, clamp, compute_local_risk_percent, estimate_kp_from_solar_wind


def test_classify_xray_thresholds() -> None:
    assert classify_xray(2e-5).startswith("M")
    assert classify_xray(2e-6).startswith("C")


def test_clamp_bounds() -> None:
    assert clamp(-2.0, 0.0, 1.0) == 0.0
    assert clamp(4.0, 0.0, 1.0) == 1.0


def test_estimate_kp_from_solar_wind_grows_with_storm_strength() -> None:
    quiet = estimate_kp_from_solar_wind(bz=2.0, speed=340.0, density=3.0)
    storm = estimate_kp_from_solar_wind(bz=-18.0, speed=820.0, density=16.0)
    assert quiet < storm
    assert 0.0 <= quiet <= 9.0
    assert 0.0 <= storm <= 9.0


def test_compute_local_risk_percent_rewards_early_detection() -> None:
    without_trigger = compute_local_risk_percent(estimated_kp=6.5, bz=-12.0, speed=650.0, density=10.0, magnetic_latitude=27.0, early_detection=False)
    with_trigger = compute_local_risk_percent(estimated_kp=6.5, bz=-12.0, speed=650.0, density=10.0, magnetic_latitude=27.0, early_detection=True)
    assert with_trigger > without_trigger
