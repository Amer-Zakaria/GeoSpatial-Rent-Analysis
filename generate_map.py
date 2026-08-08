import json
import pandas as pd
import folium
from branca.element import MacroElement
from branca.colormap import LinearColormap
from jinja2 import Template


def load_data(
    csv_path="dubai_properties.csv",
    communities_geojson_path="communities_with_rent.geojson",
    boundary_geojson_path="dubai-boundary.geojson",
):
    try:
        df = pd.read_csv(csv_path)
        df = df[df["City"] == "Dubai"]
        df = df.dropna(subset=["Latitude", "Longitude"])
    except FileNotFoundError:
        # Property markers are not currently rendered on the map, so this
        # is non-fatal — an empty frame keeps the app usable without it.
        df = pd.DataFrame()

    with open(communities_geojson_path, "r", encoding="utf-8") as f:
        dubai_geojson = json.load(f)

    with open(boundary_geojson_path, "r", encoding="utf-8") as f:
        dubai_wide_geojson = json.load(f)

    return df, dubai_geojson, dubai_wide_geojson


class LegendStyle(MacroElement):
    def __init__(self):
        super().__init__()
        self._template = Template("""
            {% macro header(this, kwargs) %}
            <style>
                .legend {
                    background-color: rgba(255, 255, 255, 0.8) !important;
                    padding: 10px !important;
                    border-radius: 5px !important;
                    color: black !important;
                }
            </style>
            {% endmacro %}
            """)


class DynamicStyling(MacroElement):
    def __init__(self, community_layer, city_layer):
        super().__init__()
        self.community_layer = community_layer
        self.city_layer = city_layer
        self._template = Template("""
            {% macro script(this, kwargs) %}
                var community_layer = {{this.community_layer.get_name()}};
                var city_layer = {{this.city_layer.get_name()}};
                var map = {{this._parent.get_name()}};

                function updateStyle() {
                    var zoom = map.getZoom();

                    var commWeight = 0.5 + (zoom - 10) * 0.5;
                    if (commWeight < 0.5) commWeight = 0.5;
                    if (commWeight > 4) commWeight = 4;

                    community_layer.setStyle({ weight: commWeight });

                    var cityWeight = 2.0 + (zoom - 10) * 1.0;
                    if (cityWeight < 2.0) cityWeight = 2.0;
                    if (cityWeight > 8) cityWeight = 8;

                    city_layer.setStyle({ weight: cityWeight });
                }

                updateStyle();
                map.on('zoomend', updateStyle);

                var style = document.createElement('style');
                style.innerHTML = '.leaflet-interactive { outline: none !important; }';
                document.getElementsByTagName('head')[0].appendChild(style);
            {% endmacro %}
            """)


class PredictHandler(MacroElement):
    """
    On map click: drops a marker, opens a popup with a small form
    (Beds / Furnishing / Type), and on submit POSTs to /predict and
    renders the prediction back into the popup.
    """

    _template = Template(r"""
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{this._parent.get_name()}};
            var activeMarker = null;

            function popupHtml(lat, lng) {
                return (
                    '<div class="predict-popup" data-lat="' + lat + '" data-lng="' + lng + '">' +
                        '<div class="pp-coords">' + lat.toFixed(5) + ', ' + lng.toFixed(5) + '</div>' +
                        '<label>Beds</label>' +
                        '<input class="pp-beds" type="number" min="0" step="1" value="2" />' +
                        '<label>Furnishing</label>' +
                        '<select class="pp-furnishing">' +
                            '<option value="0">Furnished</option>' +
                            '<option value="1">Unfurnished</option>' +
                        '</select>' +
                        '<label>Type</label>' +
                        '<select class="pp-type">' +
                            '<option value="1">Apartment</option>' +
                            '<option value="5">Villa</option>' +
                            '<option value="4">Townhouse</option>' +
                            '<option value="3">Penthouse</option>' +
                            '<option value="2">Hotel Apartment</option>' +
                            '<option value="0">Other</option>' +
                        '</select>' +
                        '<button class="pp-btn" type="button">Predict rent</button>' +
                        '<div class="pp-result"></div>' +
                    '</div>'
                );
            }

            map.on('click', function(e) {
                if (activeMarker) { map.removeLayer(activeMarker); }
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;

                activeMarker = L.marker(e.latlng).addTo(map);
                L.popup({ minWidth: 240, closeOnClick: false })
                    .setLatLng(e.latlng)
                    .setContent(popupHtml(lat, lng))
                    .openOn(map);
            });

            // Event delegation: one listener on the document catches clicks
            // on .pp-btn regardless of when/how the popup DOM was inserted
            // (popup 'add' events aren't reliably fired for popups opened
            // via L.popup().openOn(map) rather than layer.bindPopup()).
            document.addEventListener('click', function(e) {
                var btn = e.target.closest ? e.target.closest('.pp-btn') : null;
                if (!btn) return;

                var root = btn.closest('.predict-popup');
                if (!root) return;

                var lat = parseFloat(root.getAttribute('data-lat'));
                var lng = parseFloat(root.getAttribute('data-lng'));
                var beds = root.querySelector('.pp-beds').value;
                var furnishing = root.querySelector('.pp-furnishing').value;
                var type = root.querySelector('.pp-type').value;
                var result = root.querySelector('.pp-result');

                if (beds === '' || type === '') {
                    result.innerHTML = '<span class="pp-error">Fill in Beds and Type first.</span>';
                    return;
                }

                result.textContent = 'Predicting…';
                btn.disabled = true;

                fetch('/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        latitude: lat,
                        longitude: lng,
                        beds: beds,
                        furnishing: furnishing,
                        type: type
                    })
                })
                .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
                .then(function(res) {
                    btn.disabled = false;
                    if (!res.ok) {
                        result.innerHTML = '<span class="pp-error">' + (res.data.error || 'Prediction failed') + '</span>';
                        return;
                    }
                    var d = res.data;
                    result.innerHTML =
                        '<b>' + d.rent_per_sqft.toFixed(2) + ' AED/sqft</b><br>' +
                        'Est. annual rent (' + d.assumed_size_sqft + ' sqft): ' +
                        Math.round(d.estimated_annual_rent).toLocaleString() + ' AED';
                })
                .catch(function() {
                    btn.disabled = false;
                    result.innerHTML = '<span class="pp-error">Request failed</span>';
                });
            });
        })();
        {% endmacro %}

        {% macro header(this, kwargs) %}
        <style>
            .leaflet-popup-content-wrapper { background: #1f1f1f; color: #eee; }
            .leaflet-popup-tip { background: #1f1f1f; }
            .predict-popup { font-family: -apple-system, "Segoe UI", sans-serif; min-width: 210px; }
            .predict-popup .pp-coords { font-size: 11px; color: #aaa; margin-bottom: 6px; }
            .predict-popup label { display: block; font-size: 12px; margin-top: 6px; color: #ccc; }
            .predict-popup .pp-hint { font-size: 10px; color: #888; }
            .predict-popup input, .predict-popup select {
                width: 100%; box-sizing: border-box; padding: 4px 6px; margin-top: 2px;
                background: #2b2b2b; color: #eee; border: 1px solid #444; border-radius: 3px;
            }
            .predict-popup .pp-btn {
                margin-top: 10px; width: 100%; padding: 6px; background: #bd0026; color: #fff;
                border: none; border-radius: 4px; cursor: pointer; font-weight: 600;
            }
            .predict-popup .pp-btn:disabled { opacity: 0.6; cursor: default; }
            .predict-popup .pp-result { margin-top: 8px; font-size: 13px; line-height: 1.4; }
            .predict-popup .pp-error { color: #ff6b6b; }
        </style>
        {% endmacro %}
        """)

    def __init__(self):
        super().__init__()


def build_map(df, dubai_geojson, dubai_wide_geojson):
    dubai_map = folium.Map(
        location=[25.011921, 55.349367],
        zoom_start=10,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )

    rent_values = [
        feature["properties"]["Avg_Rent_per_sqft"]
        for feature in dubai_geojson["features"]
        if feature["properties"].get("Avg_Rent_per_sqft") is not None
    ]

    colormap = None
    if rent_values:
        min_rent, max_rent = min(rent_values), max(rent_values)
        colormap = LinearColormap(
            colors=["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
            vmin=min_rent,
            vmax=max_rent,
            caption="Avg Rent per sqft (AED)",
        )
        colormap.add_to(dubai_map)
        dubai_map.add_child(LegendStyle())

    for feature in dubai_geojson["features"]:
        rent = feature["properties"].get("Avg_Rent_per_sqft")
        feature["properties"]["Avg_Rent_Tooltip"] = (
            f"{int(round(rent))} AED" if rent is not None else "No Data"
        )

    def community_style(feature):
        rent = feature["properties"].get("Avg_Rent_per_sqft")
        if rent is not None and colormap:
            return {
                "fillColor": colormap(rent),
                "color": "#444444",
                "weight": 0.8,
                "fillOpacity": 0.6,
            }
        return {
            "fillColor": "transparent",
            "color": "#444444",
            "weight": 0.8,
            "fillOpacity": 0,
        }

    community_layer = folium.GeoJson(
        dubai_geojson,
        name="Dubai Communities",
        style_function=community_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["CNAME_E", "Properties_Count", "Avg_Rent_Tooltip"],
            aliases=["Community:", "Number of Properties:", "Avg Rent per sqft:"],
        ),
    ).add_to(dubai_map)

    dubai_wide_layer = folium.GeoJson(
        dubai_wide_geojson,
        name="Dubai Boundary",
        style_function=lambda x: {
            "fillColor": "transparent",
            "color": "#666666",
            "weight": 2.5,
            "fillOpacity": 0,
            "interactive": False,
        },
    ).add_to(dubai_map)

    dubai_map.add_child(DynamicStyling(community_layer, dubai_wide_layer))
    dubai_map.add_child(PredictHandler())

    return dubai_map
