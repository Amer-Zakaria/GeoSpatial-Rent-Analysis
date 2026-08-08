import os
from flask import Flask, request, jsonify

from generate_map import load_data, build_map
from run_demo import predict_rent_density

app = Flask(__name__)

DATA_DIR = os.environ.get("DUBAI_DATA_DIR", ".")
MODELS_DIR = os.environ.get("DUBAI_MODELS_DIR", "models")

_map_html_cache = None


def get_map_html():
    global _map_html_cache
    if _map_html_cache is None:
        df, communities_geojson, boundary_geojson = load_data(
            csv_path=os.path.join(DATA_DIR, "dubai_properties.csv"),
            communities_geojson_path=os.path.join(
                DATA_DIR, "communities_with_rent.geojson"
            ),
            boundary_geojson_path=os.path.join(DATA_DIR, "dubai-boundary.geojson"),
        )
        dubai_map = build_map(df, communities_geojson, boundary_geojson)
        _map_html_cache = dubai_map.get_root().render()
    return _map_html_cache


@app.route("/")
def index():
    return get_map_html()


@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(force=True, silent=True) or {}

    required = ["latitude", "longitude", "beds", "furnishing", "type"]
    missing = [k for k in required if payload.get(k) in ("", None)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
        beds = float(payload["beds"])
    except (TypeError, ValueError):
        return jsonify({"error": "latitude, longitude and beds must be numbers"}), 400

    furnishing = str(payload["furnishing"])
    prop_type = str(payload["type"])

    try:
        rent_per_sqft = predict_rent_density(
            latitude=latitude,
            longitude=longitude,
            furnishing=furnishing,
            beds=beds,
            prop_type=prop_type,
            models_dir=MODELS_DIR,
        )
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Prediction failed: {e}"}), 500

    assumed_size = 1000 if beds <= 1 else (1500 if beds == 2 else 3500)
    return jsonify(
        {
            "rent_per_sqft": rent_per_sqft,
            "assumed_size_sqft": assumed_size,
            "estimated_annual_rent": rent_per_sqft * assumed_size,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
