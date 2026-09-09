import os
import joblib
import numpy as np
import pandas as pd

DUBAI_CENTER = (25.2048, 55.2708)
EARTH_RADIUS = 6371.0

FEATURES_ORDERED = [
    "Location_score",
    "Distance_to_center",
    "Beds",
    "Furnishing",
    "Type",
    "Geo_cluster",
    "Latitude",
    "Longitude",
    "LocationScore_Beds",
    "Distance_Beds",
    "LocationScore_Furnishing",
    "Distance_Type",
]

_ARTIFACT_CACHE = {}


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometers."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS * np.arcsin(np.sqrt(a))


def _load_artifacts(models_dir="models"):
    """Load and cache the trained model + encoder + kmeans + geo metadata."""
    if models_dir in _ARTIFACT_CACHE:
        return _ARTIFACT_CACHE[models_dir]

    paths = {
        "model": os.path.join(models_dir, "final_model.pkl"),
        "encoder": os.path.join(models_dir, "categorical_encoder.pkl"),
        "kmeans": os.path.join(models_dir, "geo_kmeans.pkl"),
        "geo_meta": os.path.join(models_dir, "geo_metadata.pkl"),
    }
    missing = [p for p in paths.values() if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"Could not find required model artifacts: {missing}")

    artifacts = {key: joblib.load(path) for key, path in paths.items()}
    _ARTIFACT_CACHE[models_dir] = artifacts
    return artifacts


def predict_rent_density(
    latitude, longitude, furnishing, beds, prop_type, models_dir="models"
):
    """
    Predicts Rent_per_sqft for a property in Dubai.

    NOTE: unlike the original demo signature, this does NOT take a
    'location' argument. The trained feature set never uses the raw
    Location id — only Location_score (derived here from latitude/
    longitude against geo_metadata's community centers) is used.
    """
    artifacts = _load_artifacts(models_dir)
    model = artifacts["model"]
    encoder = artifacts["encoder"]
    kmeans = artifacts["kmeans"]
    geo_meta = artifacts["geo_meta"]

    df = pd.DataFrame(
        [
            {
                "Latitude": latitude,
                "Longitude": longitude,
                "Furnishing": furnishing,
                "Beds": beds,
                "Type": prop_type,
            }
        ]
    )

    df["Distance_to_center"] = haversine(
        df["Latitude"].values, df["Longitude"].values, DUBAI_CENTER[0], DUBAI_CENTER[1]
    )
    df["Geo_cluster"] = kmeans.predict(df[["Latitude", "Longitude"]])

    location_weights = geo_meta["location_weights"]
    location_centers = geo_meta["location_centers"]
    score_min = geo_meta["location_score_min"]
    score_max = geo_meta["location_score_max"]

    raw_score = 0.0
    for loc, weight in location_weights.items():
        center_lat = location_centers["Latitude"][loc]
        center_lon = location_centers["Longitude"][loc]
        dist = haversine(
            df["Latitude"].values, df["Longitude"].values, center_lat, center_lon
        )
        raw_score += weight * (1.0 / (dist + 1.0))

    if score_max == score_min:
        df["Location_score"] = 0.0
    else:
        df["Location_score"] = (raw_score - score_min) / (score_max - score_min)

    encoded_cats = encoder.transform(df[["Furnishing", "Type"]].astype(str))
    df["Furnishing"] = encoded_cats[:, 0]
    df["Type"] = encoded_cats[:, 1]

    df["LocationScore_Beds"] = df["Location_score"] * df["Beds"]
    df["Distance_Beds"] = df["Distance_to_center"] * df["Beds"]
    df["LocationScore_Furnishing"] = df["Location_score"] * df["Furnishing"]
    df["Distance_Type"] = df["Distance_to_center"] * df["Type"]

    prediction = model.predict(df[FEATURES_ORDERED])[0]
    return max(0.0, float(prediction))
