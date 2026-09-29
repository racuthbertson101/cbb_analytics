# Adjusted-efficiency backtest

Walk-forward over test seasons 2012-2026. Each game is predicted from ratings fit on games strictly before its date; hyperparameters for season S are chosen on seasons < S; the spread model and calibrator for season S are fit on predictions of seasons < S.

## Systems (pooled over all test games)

| System | MAE | RMSE | Log loss | Brier | Accuracy |
|---|---|---|---|---|---|
| adjeff (calibrated) | 8.890 | 11.285 | 0.5263 | 0.1775 | 0.729 |
| adjeff (raw normal) | 8.890 | 11.285 | 0.5263 | 0.1775 | 0.729 |
| home team wins | 11.141 | 14.230 | 0.6536 | 0.2305 | 0.649 |
| previous-season rating only | 9.891 | 12.539 | 0.5879 | 0.2025 | 0.678 |
| simple Elo | 9.461 | 12.042 | 0.5473 | 0.1855 | 0.715 |

Spread model uses tempo: **True** (log loss const 0.5265 vs tempo-dependent 0.5263).
Calibrator chosen: **platt** (walk-forward log loss by candidate: raw 0.5263, platt 0.5263, isotonic 0.5268).
Expected calibration error: 0.0080 (uncalibrated 0.0086). Bias (pred - actual margin): 0.213.
Seasons where adjeff beats home-team-wins log loss: 15 of 15.

## Reliability (calibrated)

| Bin | Mean predicted | Observed | N |
|---|---|---|---|
| 0 | 0.065 | 0.063 | 949 |
| 1 | 0.155 | 0.159 | 2687 |
| 2 | 0.253 | 0.258 | 4421 |
| 3 | 0.352 | 0.374 | 6230 |
| 4 | 0.452 | 0.460 | 8207 |
| 5 | 0.552 | 0.560 | 10026 |
| 6 | 0.651 | 0.647 | 11628 |
| 7 | 0.750 | 0.733 | 12331 |
| 8 | 0.850 | 0.846 | 12424 |
| 9 | 0.951 | 0.949 | 12701 |

## Accuracy by confidence bucket

| Bucket | N | Mean confidence | Accuracy |
|---|---|---|---|
| 0.50-0.60 | 18233 | 0.550 | 0.551 |
| 0.60-0.70 | 17858 | 0.650 | 0.639 |
| 0.70-0.80 | 16752 | 0.749 | 0.735 |
| 0.80-0.90 | 15111 | 0.849 | 0.845 |
| 0.90-0.95 | 6856 | 0.925 | 0.920 |
| 0.95-1.00 | 6794 | 0.976 | 0.976 |

## By season (adjeff calibrated)

| Season | MAE | RMSE | Log loss | Accuracy | Home-wins log loss |
|---|---|---|---|---|---|
| 2012 | 8.50 | 10.80 | 0.5000 | 0.752 | 0.6474 |
| 2013 | 8.65 | 10.96 | 0.5145 | 0.736 | 0.6482 |
| 2014 | 8.52 | 10.80 | 0.5207 | 0.735 | 0.6526 |
| 2015 | 8.56 | 10.82 | 0.5213 | 0.733 | 0.6528 |
| 2016 | 8.70 | 11.03 | 0.5189 | 0.730 | 0.6510 |
| 2017 | 8.80 | 11.28 | 0.5243 | 0.730 | 0.6562 |
| 2018 | 8.96 | 11.39 | 0.5195 | 0.741 | 0.6457 |
| 2019 | 8.98 | 11.40 | 0.5248 | 0.733 | 0.6543 |
| 2020 | 8.99 | 11.47 | 0.5309 | 0.727 | 0.6471 |
| 2021 | 9.37 | 11.85 | 0.5513 | 0.708 | 0.6735 |
| 2022 | 8.92 | 11.31 | 0.5333 | 0.724 | 0.6607 |
| 2023 | 9.04 | 11.39 | 0.5444 | 0.717 | 0.6550 |
| 2024 | 9.12 | 11.49 | 0.5417 | 0.720 | 0.6537 |
| 2025 | 9.09 | 11.60 | 0.5249 | 0.726 | 0.6547 |
| 2026 | 9.24 | 11.71 | 0.5289 | 0.717 | 0.6559 |

NCAA tournament games: n=924, MAE 9.08, log loss 0.5432, accuracy 0.710.

## Production parameters

Config: `{"lam": 3, "halflife": null, "cap": 60, "lam_h": null, "lam_t": 3, "halflife_t": 30}`