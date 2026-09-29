# Adjusted-efficiency backtest

Walk-forward over test seasons 2012-2026. Each game is predicted from ratings fit on games strictly before its date; hyperparameters for season S are chosen on seasons < S; the spread model and calibrator for season S are fit on predictions of seasons < S.

## Systems (pooled over all test games)

| System | MAE | RMSE | Log loss | Brier | Accuracy |
|---|---|---|---|---|---|
| adjeff (calibrated) | 8.930 | 11.347 | 0.5289 | 0.1785 | 0.728 |
| adjeff (raw normal) | 8.930 | 11.347 | 0.5289 | 0.1785 | 0.728 |
| home team wins | 11.140 | 14.229 | 0.6536 | 0.2305 | 0.649 |
| previous-season rating only | 9.891 | 12.539 | 0.5880 | 0.2025 | 0.678 |
| simple Elo | 9.461 | 12.042 | 0.5473 | 0.1855 | 0.715 |

Spread model uses tempo: **True** (log loss const 0.5292 vs tempo-dependent 0.5289).
Calibrator chosen: **platt** (walk-forward log loss by candidate: raw 0.5289, platt 0.5289, isotonic 0.5295).
Expected calibration error: 0.0071 (uncalibrated 0.0074). Bias (pred - actual margin): 0.249.
Seasons where adjeff beats home-team-wins log loss: 15 of 15.

## Reliability (calibrated)

| Bin | Mean predicted | Observed | N |
|---|---|---|---|
| 0 | 0.066 | 0.062 | 876 |
| 1 | 0.155 | 0.154 | 2533 |
| 2 | 0.254 | 0.262 | 4348 |
| 3 | 0.353 | 0.371 | 6233 |
| 4 | 0.453 | 0.455 | 8154 |
| 5 | 0.551 | 0.556 | 10095 |
| 6 | 0.651 | 0.648 | 11807 |
| 7 | 0.750 | 0.733 | 12490 |
| 8 | 0.850 | 0.845 | 12634 |
| 9 | 0.950 | 0.946 | 12397 |

## Accuracy by confidence bucket

| Bucket | N | Mean confidence | Accuracy |
|---|---|---|---|
| 0.50-0.60 | 18249 | 0.549 | 0.551 |
| 0.60-0.70 | 18040 | 0.650 | 0.642 |
| 0.70-0.80 | 16838 | 0.749 | 0.734 |
| 0.80-0.90 | 15167 | 0.849 | 0.845 |
| 0.90-0.95 | 6855 | 0.925 | 0.919 |
| 0.95-1.00 | 6418 | 0.975 | 0.974 |

## By season (adjeff calibrated)

| Season | MAE | RMSE | Log loss | Accuracy | Home-wins log loss |
|---|---|---|---|---|---|
| 2012 | 8.50 | 10.80 | 0.5000 | 0.752 | 0.6474 |
| 2013 | 8.68 | 11.01 | 0.5173 | 0.737 | 0.6482 |
| 2014 | 8.54 | 10.84 | 0.5230 | 0.733 | 0.6526 |
| 2015 | 8.60 | 10.89 | 0.5237 | 0.730 | 0.6528 |
| 2016 | 8.75 | 11.10 | 0.5221 | 0.730 | 0.6510 |
| 2017 | 8.82 | 11.31 | 0.5258 | 0.730 | 0.6562 |
| 2018 | 9.00 | 11.45 | 0.5222 | 0.738 | 0.6457 |
| 2019 | 9.02 | 11.46 | 0.5284 | 0.731 | 0.6543 |
| 2020 | 9.02 | 11.51 | 0.5334 | 0.725 | 0.6471 |
| 2021 | 9.44 | 11.95 | 0.5537 | 0.704 | 0.6735 |
| 2022 | 8.94 | 11.35 | 0.5349 | 0.724 | 0.6607 |
| 2023 | 9.09 | 11.46 | 0.5481 | 0.718 | 0.6550 |
| 2024 | 9.17 | 11.58 | 0.5445 | 0.717 | 0.6537 |
| 2025 | 9.17 | 11.71 | 0.5290 | 0.724 | 0.6547 |
| 2026 | 9.30 | 11.82 | 0.5328 | 0.718 | 0.6559 |

NCAA tournament games: n=924, MAE 9.10, log loss 0.5439, accuracy 0.714.

## Production parameters

Config: `{"lam": 3, "halflife": null, "cap": 60, "lam_h": null, "lam_t": 3, "halflife_t": 30}`