from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from forecaster import build_mu_hat as build_mu_hat_module
from forecaster.build_mu_hat import build_mu_hat, load_price_index, retrain_dates
from forecaster.config import DATA, MODEL, TRAIN, WALK_FORWARD
from forecaster.dataset import chronological_split
from forecaster.features import build_feature_panel, build_latest_feature_row
from forecaster.forecast import get_mu_hat, load_forecaster, save_forecaster
from forecaster.train import train_forecaster

# Small enough to train in seconds; the leakage properties don't depend on model quality.
FAST_TRAIN = replace(TRAIN, epochs=3, batch_size=512)
FAST_WALK_FORWARD = replace(WALK_FORWARD, min_train_years=2)


def _write_returns(path, returns: pd.DataFrame) -> str:
    returns.rename_axis("date").to_csv(path)
    return str(path)


def _synthetic_returns() -> pd.DataFrame:
    dates = pd.bdate_range("2000-01-03", periods=252 * 4)
    rng = np.random.default_rng(0)
    data = rng.normal(0.0003, 0.01, size=(len(dates), 3))
    return pd.DataFrame(data, index=dates, columns=["Cnsmr", "Manuf", "HiTec"])


def _build(tmp_path, name: str, returns: pd.DataFrame) -> pd.DataFrame:
    prices = load_price_index(_write_returns(tmp_path / name, returns))
    return build_mu_hat(prices, DATA, FAST_TRAIN, FAST_WALK_FORWARD)


@pytest.mark.parametrize("where", ["retrain_date", "mid_period"])
def test_mu_hat_for_date_ignores_returns_after_it(tmp_path, where):
    returns = _synthetic_returns()
    base = _build(tmp_path, "base.csv", returns)

    # t on a retrain date catches leakage into training; t mid-period catches leakage into the
    # features, and puts the next retrain's training data after t.
    retrains = retrain_dates(returns.index, FAST_WALK_FORWARD.min_train_years)
    assert len(retrains) >= 2
    if where == "retrain_date":
        t = retrains[1]
    else:
        first_period = base.index[base.index < retrains[1]]
        t = first_period[len(first_period) // 2]

    changed = returns.copy()
    changed.loc[changed.index > t] = -2.0 * changed.loc[changed.index > t] + 0.01
    after = _build(tmp_path, "changed.csv", changed)

    pd.testing.assert_frame_equal(base.loc[:t], after.loc[:t], check_exact=True)
    # Not vacuous: later rows do see the change.
    assert not np.allclose(base.loc[base.index > t].values, after.loc[after.index > t].values)


def test_each_model_trains_only_on_prices_up_to_its_retrain_date(tmp_path, monkeypatch):
    # The test above can't see a leak that only reaches the early-stopping tail of a
    # training window, so check the training input directly.
    seen = []

    def recording_build_feature_panel(prices, cfg):
        seen.append(prices.index.max())
        return build_feature_panel(prices, cfg)

    monkeypatch.setattr(build_mu_hat_module, "build_feature_panel", recording_build_feature_panel)
    returns = _synthetic_returns()
    _build(tmp_path, "returns.csv", returns)

    assert seen == retrain_dates(returns.index, FAST_WALK_FORWARD.min_train_years)


def test_mu_hat_file_layout(tmp_path):
    returns = _synthetic_returns()
    table = _build(tmp_path, "returns.csv", returns)

    first_retrain = retrain_dates(returns.index, FAST_WALK_FORWARD.min_train_years)[0]
    fridays = returns.index[(returns.index.dayofweek == 4) & (returns.index >= first_retrain)]

    assert list(table.columns) == list(returns.columns)
    assert table.index.name == "date"
    assert table.index.equals(pd.DatetimeIndex(fridays))
    assert not table.isna().any().any()


def test_saved_forecaster_reproduces_predictions(tmp_path):
    prices = (1.0 + _synthetic_returns()).cumprod()
    bundle = chronological_split(build_feature_panel(prices))
    model, _ = train_forecaster(bundle, FAST_TRAIN)
    latest = build_latest_feature_row(prices)

    path = str(tmp_path / "forecaster.pt")
    save_forecaster(model, bundle, path, MODEL)
    loaded_model, loaded_bundle = load_forecaster(path)

    pd.testing.assert_series_equal(get_mu_hat(model, latest, bundle),
                                   get_mu_hat(loaded_model, latest, loaded_bundle))
