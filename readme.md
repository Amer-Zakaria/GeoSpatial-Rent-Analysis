# GeoSpatial Rent Analysis

Interactive map and machine-learning pipeline that estimates **rental price density (AED per sqft)** for residential listings in Dubai from a clicked location and a few property attributes.

Click anywhere on the map, choose beds / furnishing / type, and the app returns predicted AED/sqft plus an estimated annual rent using a size assumption.

---

## Quick summary

This project turns a Kaggle-style Dubai rental listings dataset into:

1. **Cleaned, geo-enriched training data** (`Data_Preprocessing.ipynb` → `final.csv`)
2. **A tuned Gradient Boosting regressor** that predicts `Rent_per_sqft` (`models_v2.ipynb` → `models/`)
3. **A Flask + Folium web app** (`app.py`) with community choropleth colors, optional listing markers, and click-to-predict

The model does **not** take a neighborhood name. Location is encoded from coordinates: distance to Dubai center, a K-Means geo-cluster, and a **location score** based on proximity to the highest-rent communities.

---

## How to run locally

### Requirements

- Python 3.11+ recommended
- The trained artifacts under `models/` (`final_model.pkl`, `categorical_encoder.pkl`, `geo_kmeans.pkl`, `geo_metadata.pkl`)
- Map data in the project root:
  - `communities_with_rent.geojson`
  - `dubai-boundary.geojson`
  - `dubai_properties.csv` (optional; used only if you turn on property markers)

### Setup (Windows / PowerShell)

```powershell
cd GeoSpatial-Rent-Analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### Setup (macOS / Linux)

```bash
cd GeoSpatial-Rent-Analysis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in a browser.

On the map:

- Click a point to drop a marker and open the prediction form
- Use **Rent Colors** (top-right) to cycle choropleth: Off → Outline → Full
- Use **Properties** to toggle listing markers (requires `dubai_properties.csv`)

Optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DUBAI_DATA_DIR` | `.` | Folder containing the CSV / GeoJSON files |
| `DUBAI_MODELS_DIR` | `models` | Folder containing trained artifacts |
| `CARTO_API_KEY` | (built-in fallback) | Carto dark basemap tiles |

### Retrain the model (optional)

```powershell
# 1) Explore / clean (writes insights; training uses final.csv)
jupyter notebook Data_Preprocessing.ipynb

# 2) Compare models, tune, and export artifacts into models/
jupyter notebook models_v2.ipynb
```

`models_v2.ipynb` expects `data/final.csv`. A copy also lives at the repo root as `final.csv`.

### Rebuild community rent polygons (optional)

```powershell
python averages_to_geo_boundries.py
```

This spatial-joins listing averages onto `dubai.geojson` and writes `communities_with_rent.geojson`.

---

## Tech stack

| Layer | Tools |
|---|---|
| App / API | Flask 3, Flask-CORS |
| Map UI | Folium, Leaflet (via Folium), Branca, Carto dark tiles, OpenStreetMap |
| Geospatial | GeoPandas, Shapely, PyProj, GeoPy |
| ML | scikit-learn (Gradient Boosting, Random Forest, K-Means, OrdinalEncoder), XGBoost, LightGBM |
| Data / viz | Pandas, NumPy, Matplotlib, Seaborn, Plotly |
| Notebooks | Jupyter |

The old planned stack (React + FastAPI) was **not** used. The shipped product is a single Flask process that serves a Folium map and a `POST /predict` endpoint.

---

## How prediction works

```
Map click (lat, lon) + Beds + Furnishing + Type
        │
        ▼
  run_demo.predict_rent_density()
        │  • Haversine distance to Dubai center (25.2048, 55.2708)
        │  • K-Means geo-cluster (15 clusters, fit on training coords)
        │  • Location_score from distance to top high-rent community centers
        │  • Ordinal-encode Furnishing / Type
        │  • Interaction terms (score×beds, distance×beds, …)
        ▼
  GradientBoosting → Rent_per_sqft (clipped at 0)
        ▼
  Assumed size → estimated annual rent
```

Assumed sizes used only for the annual-rent display (the model itself predicts density):

| Beds | Assumed size |
|---|---|
| ≤ 1 | 1,000 sqft |
| 2 | 1,500 sqft |
| ≥ 3 | 3,500 sqft |

### `POST /predict`

```json
{
  "latitude": 25.2048,
  "longitude": 55.2708,
  "beds": 2,
  "furnishing": "0",
  "type": "1"
}
```

Furnishing and type are the **already-encoded** category codes used at training time:

| Field | Codes |
|---|---|
| `furnishing` | `0` Furnished, `1` Unfurnished |
| `type` | `0` Other, `1` Apartment, `2` Hotel Apartment, `3` Penthouse, `4` Townhouse, `5` Villa |

Example response:

```json
{
  "rent_per_sqft": 118.42,
  "assumed_size_sqft": 1500,
  "estimated_annual_rent": 177630.0
}
```

---

## Dataset and preprocessing

Source file: **`dubai_properties.csv`** — 34,250 Dubai rental listings with address, rent, beds, baths, type, area, furnishing, listing age, community name, and coordinates.

Cleaning (`Data_Preprocessing.ipynb`):

| Step | Result |
|---|---|
| Drop rows missing latitude / longitude | 31 rows |
| Drop constant columns (`Frequency`, `Purpose`, `City`) | no signal |
| Deduplicate near-identical listings (keep newest by listing age) | 3,875 removed → 30,344 |
| Remove only extreme / likely-error outliers (rent > 10M AED, rent/sqft > 1,000, area > 100,000 sqft, listing age > 600 days) | 29 removed |
| **Modeling table** | **30,301 rows** in `final.csv` |

Legitimate luxury listings were kept. IQR flags were treated as exploratory, not as a blanket delete rule.

Engineered features:

- **Distance_to_center** — great-circle km to downtown Dubai
- **Geo_cluster** — K-Means on lat/lon (15 clusters in the trained pipeline; silhouette analysis in EDA also explored larger `k`)
- **Location_score** — proximity-weighted score toward the top-5 communities by median rent/sqft (fit on **training data only** to avoid leakage)
- **Interactions** — `LocationScore_Beds`, `Distance_Beds`, `LocationScore_Furnishing`, `Distance_Type`

---

## Notable results and findings

Held-out test set (20% split, `random_state=42`) for the shipped model:

| Metric | Value |
|---|---|
| Model | scikit-learn **GradientBoostingRegressor** |
| Feature set | **Interaction** (12 features) |
| Target | `Rent_per_sqft` (raw; log1p did **not** help) |
| Test **R²** | **0.592** |
| Test RMSE | **42.48** AED/sqft |
| Test MAE | **25.86** AED/sqft |
| Test median AE | **16.59** AED/sqft |
| Tuned 3-fold CV R² | 0.578 |

Hyperparameters: `n_estimators=80`, `max_depth=6`, `learning_rate≈0.113`, `min_samples_leaf=5`, `subsample≈0.986`.

### Model comparison (5-fold CV, before final tuning)

All four families (Gradient Boosting, Random Forest, LightGBM, XGBoost) landed in a tight band around **R² ≈ 0.57**. The interaction feature set was the most consistent winner; Gradient Boosting + Interaction led CV (**R² 0.574**, RMSE 44.77). A naive “predict the mean” baseline would sit near RMSE ≈ 68, so the models do capture real structure.

### What actually drives rent density

- **Location dominates.** Mutual information ranked longitude / latitude far above beds and baths. The trained Gradient Boosting model puts **`Location_score` first by a wide margin**, then `Distance_Type` and `LocationScore_Beds`.
- **Larger units are cheaper per square foot.** `Area_in_sqft` and `Beds` correlate **negatively** with `Rent_per_sqft` even though area has high mutual information — density, not total rent, is the target.
- **Baths and listing age are weak.** They were not needed in the final feature set.
- **The target is right-skewed**, concentrated around ~80–160 AED/sqft with a long luxury tail. Residuals are centered near zero for typical listings; **very expensive outliers are under-predicted**.
- **Raw target beat log1p** for every model family tried.

Diagnostic plots in the repo: `model_comparison.png`, `feature_importance.png`, `actual_vs_predicted.png`, `residuals_plot.png`, `residual_distribution.png`, `target_distribution.png`.

---

## Project layout

```
GeoSpatial-Rent-Analysis/
├── app.py                         # Flask: map at /  and  POST /predict
├── generate_map.py                # Folium map, choropleth, click-to-predict UI
├── run_demo.py                    # Inference: load artifacts, build features, predict
├── process_location_averages.py   # Per-location mean rent/sqft
├── averages_to_geo_boundries.py   # Spatial join → communities_with_rent.geojson
├── Data_Preprocessing.ipynb       # Cleaning, EDA, geo feature design
├── models_v2.ipynb                # CV, tuning, export of models/
├── requirements.txt
├── dubai_properties.csv           # Raw listings
├── final.csv                      # Clean modeling table (30,301 rows)
├── dubai.geojson                  # Community polygons
├── dubai-boundary.geojson         # City outline
├── communities_with_rent.geojson  # Communities + avg rent / listing counts
├── models/
│   ├── final_model.pkl
│   ├── categorical_encoder.pkl
│   ├── geo_kmeans.pkl
│   ├── geo_metadata.pkl
│   ├── model_info.txt
│   └── features_list.txt
└── *.png                          # Training / evaluation figures
```

---

## Team

| Role | Name |
|---|---|
| Contributor | Amer Zakaria |
| Contributor | Bilal Alasha |
| Contributor | Mahdi Alwis |
| Supervisor  | Ahmad M. Os |

---

## Notes

- Predictions are **AED per sqft**, not a full rental contract. Annual rent in the popup is an illustration from assumed size.
- Coordinates in the source listings are community-level in many rows, so nearby clicks can share the same location signal.
- The app is intended for local demo / course use (`debug=True`); it is not a production deployment.
