"""
Sentinel AI - PM2.5 Forecast Engine (Day 15)
Trains an XGBoost model on historical Pune hourly AQI data to predict
PM2.5 for the next 24-72 hours.

Usage:
    python train_forecast.py

Outputs:
    models/pm25_forecast.json   (the trained model)
    Prints accuracy metrics + a sample 24h forecast.
"""

import os
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, r2_score

# ---------- 1. LOAD ----------
DATA_PATH = os.path.join("data", "2024_hourly_data.csv")
df = pd.read_csv(DATA_PATH)

# Combine Date + Time into a single datetime, then sort chronologically
df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"])
df = df.sort_values("datetime").reset_index(drop=True)

# ---------- 2. CLEAN ----------
# Convert pollutant columns to numbers; bad/blank values become NaN
pollutants = ["CO", "NH3", "NO2", "OZONE", "PM10", "PM2.5", "SO2"]
for col in pollutants:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Fill small gaps by carrying the last valid reading forward, then backward
df[pollutants] = df[pollutants].ffill().bfill()

# ---------- 3. FEATURE ENGINEERING ----------
# Time features - air quality follows daily + seasonal cycles
df["hour"] = df["datetime"].dt.hour
df["day_of_week"] = df["datetime"].dt.dayofweek
df["month"] = df["datetime"].dt.month

# Lag features - what PM2.5 was 1h ago and 24h ago (strongest predictors)
df["pm25_lag1"] = df["PM2.5"].shift(1)
df["pm25_lag24"] = df["PM2.5"].shift(24)

# Rolling mean - smooths recent trend
df["pm25_roll6"] = df["PM2.5"].shift(1).rolling(window=6).mean()

# Drop the first rows that don't have lag history
df = df.dropna().reset_index(drop=True)

# ---------- 4. TRAIN / TEST SPLIT ----------
features = [
    "hour", "day_of_week", "month",
    "pm25_lag1", "pm25_lag24", "pm25_roll6",
    "PM10", "NO2", "CO", "SO2", "OZONE", "NH3",
]
target = "PM2.5"

# Time-based split: train on first 80%, test on last 20% (no shuffling - it's a time series)
split = int(len(df) * 0.8)
X_train, X_test = df[features][:split], df[features][split:]
y_train, y_test = df[target][:split], df[target][split:]

# ---------- 5. TRAIN MODEL ----------
model = XGBRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=6,
    random_state=42,
)
model.fit(X_train, y_train)

# ---------- 6. EVALUATE ----------
preds = model.predict(X_test)
mae = mean_absolute_error(y_test, preds)
r2 = r2_score(y_test, preds)

print("=" * 45)
print("  SENTINEL AI - PM2.5 FORECAST MODEL")
print("=" * 45)
print(f"  Training rows : {len(X_train)}")
print(f"  Testing rows  : {len(X_test)}")
print(f"  MAE  (avg error in AQI units) : {mae:.1f}")
print(f"  R2   (1.0 = perfect)          : {r2:.3f}")
print("=" * 45)

# ---------- 7. SAVE MODEL ----------
os.makedirs("models", exist_ok=True)
model.save_model(os.path.join("models", "pm25_forecast.json"))
print("  Model saved -> models/pm25_forecast.json")

# ---------- 8. SAMPLE FORECAST ----------
# Show the last 5 actual vs predicted, as a sanity check
print("\n  Sample (last 5 hours, actual vs predicted PM2.5):")
for actual, pred in list(zip(y_test.values, preds))[-5:]:
    print(f"    actual={actual:6.1f}   predicted={pred:6.1f}")
