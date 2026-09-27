"""Robust trend statistics on short monthly series (numpy only)."""
from __future__ import annotations

import math

import numpy as np


def theil_sen(y: np.ndarray) -> float:
    """Median of pairwise slopes (per step). Robust to outliers."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3:
        return float("nan")
    i, j = np.triu_indices(n, k=1)
    return float(np.median((y[j] - y[i]) / (j - i)))


def _norm_p(z: float) -> float:
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def mann_kendall(y: np.ndarray) -> tuple[float, float]:
    """Two-sided Mann-Kendall test -> (z, p). No tie correction (continuous data)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 4:
        return 0.0, 1.0
    i, j = np.triu_indices(n, k=1)
    s = float(np.sign(y[j] - y[i]).sum())
    var = n * (n - 1) * (2 * n + 5) / 18.0
    z = (s - np.sign(s)) / math.sqrt(var) if s != 0 else 0.0
    return z, _norm_p(z)


def seasonal_mann_kendall(y: np.ndarray, period: int = 12) -> tuple[float, float]:
    """Seasonal Mann-Kendall (Hirsch 1982): sum of per-season S statistics.
    Robust to seasonality without having to model it."""
    y = np.asarray(y, dtype=float)
    s_tot, var_tot = 0.0, 0.0
    for k in range(period):
        ys = y[k::period]
        n = len(ys)
        if n < 2:
            continue
        i, j = np.triu_indices(n, k=1)
        s_tot += float(np.sign(ys[j] - ys[i]).sum())
        var_tot += n * (n - 1) * (2 * n + 5) / 18.0
    if var_tot == 0:
        return 0.0, 1.0
    z = (s_tot - np.sign(s_tot)) / math.sqrt(var_tot) if s_tot != 0 else 0.0
    return z, _norm_p(z)


def deseasonalize(y: np.ndarray, months: list[int], fit_mask: np.ndarray | None = None) -> np.ndarray:
    """Remove calendar-month effects from a log series.

    Month effects are estimated after removing a robust linear trend, so a
    steady decline is not mistaken for seasonality. Needs >= 2 years of data;
    otherwise the series is returned unchanged."""
    y = np.asarray(y, dtype=float)
    if len(y) < 24:
        return y.copy()
    fit = fit_mask if fit_mask is not None else np.ones(len(y), bool)
    t = np.arange(len(y), dtype=float)
    slope = theil_sen(y[fit])
    resid = y - slope * t
    effects = np.zeros(12)
    for m in range(1, 13):
        sel = np.array([mm == m for mm in months]) & fit
        if sel.sum() >= 2:
            effects[m - 1] = np.median(resid[sel])
    effects -= effects.mean()
    return y - np.array([effects[m - 1] for m in months])


def seasonal_profile(values: np.ndarray, months: list[int]) -> dict[int, float]:
    """Mean of each calendar month relative to the overall mean (1.0 = average)."""
    v = np.asarray(values, dtype=float)
    overall = v.mean() if v.size and v.mean() > 0 else 1.0
    prof = {}
    for m in range(1, 13):
        sel = [x for x, mm in zip(v, months) if mm == m]
        if sel:
            prof[m] = float(np.mean(sel) / overall)
    return prof


def block_bootstrap_slope_ci(y: np.ndarray, block: int = 6, n_boot: int = 400,
                             seed: int = 7, alpha: float = 0.05) -> tuple[float, float]:
    """CI for the Theil-Sen slope with a moving-block bootstrap of residuals,
    which keeps the autocorrelation that plain permutation tests ignore."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 2 * block:
        return float("nan"), float("nan")
    t = np.arange(n, dtype=float)
    slope = theil_sen(y)
    fitted = slope * t + np.median(y - slope * t)
    resid = y - fitted
    rng = np.random.default_rng(seed)
    slopes = np.empty(n_boot)
    starts_max = n - block
    for b in range(n_boot):
        idx = np.concatenate([np.arange(s, s + block)
                              for s in rng.integers(0, starts_max + 1, size=math.ceil(n / block))])[:n]
        slopes[b] = theil_sen(fitted + resid[idx])
    lo, hi = np.quantile(slopes, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def trend_with_ci(y_full: np.ndarray, months: list[int], win: slice, block: int = 6,
                  n_boot: int = 300, seed: int = 7, alpha: float = 0.05):
    """Theil-Sen slope of the deseasonalized series inside `win`, with a CI from a
    bootstrap of the whole pipeline: residual blocks are resampled and the
    seasonal effects are re-estimated each time, so uncertainty about
    seasonality widens the interval instead of being ignored."""
    y_full = np.asarray(y_full, dtype=float)
    des = deseasonalize(y_full, months)
    slope = theil_sen(des[win])
    n = len(y_full)
    if n < 2 * block or (win.stop - (win.start or 0)) < 2 * block:
        return slope, float("nan"), float("nan")
    t = np.arange(n, dtype=float)
    b_all = theil_sen(des)
    level = np.median(des - b_all * t)
    season = y_full - des                      # estimated calendar-month effects
    resid = des - (level + b_all * t)
    rng = np.random.default_rng(seed)
    slopes = np.empty(n_boot)
    for k in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=math.ceil(n / block))
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        y_star = level + b_all * t + season + resid[idx]
        slopes[k] = theil_sen(deseasonalize(y_star, months)[win])
    lo, hi = np.quantile(slopes, [alpha / 2, 1 - alpha / 2])
    # Replicates are generated around the full-period slope; re-centre them on
    # the window estimate so the interval keeps its width but not that bias.
    shift = slope - float(np.median(slopes))
    return slope, float(lo + shift), float(hi + shift)


def rolling_median(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    half = window // 2
    out = np.empty(len(x))
    for i in range(len(x)):
        out[i] = np.median(x[max(0, i - half): i + half + 1])
    return out


def rolling_mad(x: np.ndarray, window: int, med: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    half = window // 2
    out = np.empty(len(x))
    for i in range(len(x)):
        seg = x[max(0, i - half): i + half + 1]
        out[i] = np.median(np.abs(seg - med[i]))
    return out


def detect_spikes(daily: np.ndarray, window: int = 61, z_thr: float = 5.0,
                  min_views: int = 20, min_ratio: float = 4.0):
    """Robust z-score of log1p(views) against a centered rolling median.
    Returns (is_spike bool array, baseline views array)."""
    v = np.asarray(daily, dtype=float)
    lv = np.log1p(v)
    med = rolling_median(lv, window)
    mad = rolling_mad(lv, window, med)
    scale = np.maximum(1.4826 * mad, 0.15)  # floor avoids infinite z on flat series
    z = (lv - med) / scale
    base = np.expm1(med)
    spike = (z > z_thr) & (v >= min_views) & (v >= min_ratio * np.maximum(base, 1.0))
    return spike, base
