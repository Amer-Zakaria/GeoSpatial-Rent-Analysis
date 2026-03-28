import geopandas as gpd
from process_location_averages import process_location_averages

# ── 1. Load files ──────────────────────────────────────────────────────────────
communities = gpd.read_file("dubai.geojson")
rentals = process_location_averages("dubai_properties.csv")

# ── 2. Convert rentals CSV → GeoDataFrame ─────────────────────────────────────
rentals_gdf = gpd.GeoDataFrame(
    rentals,
    geometry=gpd.points_from_xy(rentals["Longitude"], rentals["Latitude"]),
    crs="EPSG:4326",
)

# Align CRS just in case
if communities.crs != rentals_gdf.crs:
    rentals_gdf = rentals_gdf.to_crs(communities.crs)

# ── 3. Spatial join ────────────────────────────────────────────────────────────
joined = gpd.sjoin(rentals_gdf, communities, how="inner", predicate="within")

# Warn about unmatched points
unmatched = len(rentals_gdf) - len(joined)
if unmatched > 0:
    print(f"⚠️  {unmatched} point(s) didn't fall within any community and were dropped.")

# ── 4. Aggregate per community index ──────────────────────────────────────────
agg = (
    joined.groupby("index_right")
    .agg(
        Avg_Rent_per_sqft=("Avg_Rent_per_sqft", "mean"),
        Properties_Count=("Properties_Count", "sum"),
    )
    .reset_index()
)

# ── 5. Merge back onto communities using its index ────────────────────────────
communities = communities.reset_index()  # makes the index a column called "index"
result = communities.merge(agg, left_on="index", right_on="index_right", how="left")
result = result.drop(columns=["index_right"])

# ── 6. Export ──────────────────────────────────────────────────────────────────
result.to_file("communities_with_rent.geojson", driver="GeoJSON")
print("✅ Done — communities_with_rent.geojson written.")
