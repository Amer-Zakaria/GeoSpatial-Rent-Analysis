import json
import os
import pandas as pd
import folium
from folium.plugins import MarkerCluster
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


class MarkerTheme(MacroElement):
    """Dark-theme styling for the restored property marker cluster/popups,
    so they match the rest of the map's look."""

    def __init__(self):
        super().__init__()
        self._template = Template("""
            {% macro header(this, kwargs) %}
            <style>
                .marker-cluster-custom {
                    background: transparent;
                }
                .marker-cluster-custom .cluster-marker {
                    background: rgba(189, 0, 38, 0.85);
                    border: 2px solid #eee;
                    border-radius: 50%;
                    width: 36px;
                    height: 36px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #fff;
                    font-family: -apple-system, "Segoe UI", sans-serif;
                    font-weight: 700;
                    font-size: 13px;
                }
                .property-popup {
                    font-family: -apple-system, "Segoe UI", sans-serif;
                    font-size: 12px;
                    line-height: 1.5;
                    color: #eee;
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


class PredictCaption(MacroElement):
    """Bottom-center hint. Transparent (no background box) — legible via a
    text-shadow against the dark tiles instead — and a bit larger than the
    old inline caption."""

    def __init__(self):
        super().__init__()
        self._template = Template("""
            {% macro header(this, kwargs) %}
            <style>
                .predict-caption {
                    position: absolute;
                    bottom: 22px;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 900;
                    color: #f2f2f2;
                    font-family: -apple-system, "Segoe UI", sans-serif;
                    font-size: 14px;
                    font-style: italic;
                    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.85), 0 0 10px rgba(0, 0, 0, 0.5);
                    pointer-events: none;
                    text-align: center;
                    white-space: nowrap;
                }
            </style>
            {% endmacro %}

            {% macro script(this, kwargs) %}
                (function() {
                    var map = {{this._parent.get_name()}};
                    var caption = document.createElement('div');
                    caption.className = 'predict-caption';
                    caption.textContent = 'Click any coordinate on the map to predict the rental price';
                    map._container.appendChild(caption);
                })();
            {% endmacro %}
            """)


class ToggleControls(MacroElement):
    """Two small buttons (top-right) to independently show/hide the
    property marker cluster and the choropleth (community rent-color) layer."""

    def __init__(self, community_layer=None, marker_cluster=None):
        super().__init__()
        self.community_layer = community_layer
        self.marker_cluster = marker_cluster
        self._template = Template("""
            {% macro header(this, kwargs) %}
            <style>
                .map-toggle-bar {
                    display: flex;
                    flex-direction: column;
                    align-items: flex-end;
                    gap: 6px;
                }
                .map-toggle-buttons {
                    display: flex;
                    gap: 8px;
                }
                .map-toggle-btn {
                    background: rgba(31, 31, 31, 0.9);
                    color: #eee;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-family: -apple-system, "Segoe UI", sans-serif;
                    font-size: 12px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.15s ease;
                }
                .map-toggle-btn:hover { background: rgba(50, 50, 50, 0.95); }
                .map-toggle-btn.active { background: #bd0026; border-color: #bd0026; }
            </style>
            {% endmacro %}

            {% macro script(this, kwargs) %}
                (function() {
                    var map = {{this._parent.get_name()}};
                    var communityLayer = {{ this.community_layer.get_name() if this.community_layer else 'null' }};
                    var markerLayer = {{ this.marker_cluster.get_name() if this.marker_cluster else 'null' }};

                    // A real Leaflet control (not a raw absolutely-positioned div):
                    // it stacks cleanly with the legend control in the same corner
                    // instead of overlapping it, and Leaflet gives us a container
                    // we can stop click-through on.
                    var ToggleControl = L.Control.extend({
                        options: { position: 'topright' },
                        onAdd: function() {
                            var bar = L.DomUtil.create('div', 'map-toggle-bar');

                            // Without this, clicks on the buttons fall through to
                            // the map's own click handler and open the predict popup.
                            L.DomEvent.disableClickPropagation(bar);
                            L.DomEvent.disableScrollPropagation(bar);

                            var buttonsRow = L.DomUtil.create('div', 'map-toggle-buttons', bar);

                            if (communityLayer) {
                                // Capture each sub-layer's original (colored) style once,
                                // so "Full" can be restored exactly after "Outline" flattens it.
                                communityLayer.eachLayer(function(layer) {
                                    layer._fullStyle = {
                                        fillColor: layer.options.fillColor,
                                        color: layer.options.color,
                                        weight: layer.options.weight,
                                        fillOpacity: layer.options.fillOpacity
                                    };
                                });

                                // 0 = Full (colors + legend), 1 = Outline (boundaries only,
                                // no fill/legend), 2 = Off (layer hidden entirely).
                                // Cycle order starting from the default (Off) is:
                                // Off -> Outline -> Full -> Off ...
                                var COLOR_STATES = ['Full', 'Outline', 'Off'];
                                var COLOR_NEXT = { 2: 1, 1: 0, 0: 2 };
                                var colorState = 2;
                                var colorBtn = L.DomUtil.create('button', 'map-toggle-btn', buttonsRow);
                                colorBtn.type = 'button';

                                function applyColorState(state) {
                                    colorState = state;
                                    colorBtn.textContent = 'Rent Colors: ' + COLOR_STATES[state];
                                    colorBtn.classList.toggle('active', state !== 2);

                                    var legendEl = document.querySelector('.leaflet-control.legend');

                                    if (state === 2) {
                                        map.removeLayer(communityLayer);
                                        if (legendEl) legendEl.style.display = 'none';
                                        return;
                                    }

                                    if (!map.hasLayer(communityLayer)) {
                                        map.addLayer(communityLayer);
                                    }

                                    if (state === 0) {
                                        communityLayer.eachLayer(function(layer) {
                                            layer.setStyle(layer._fullStyle);
                                        });
                                        if (legendEl) legendEl.style.display = '';
                                    } else {
                                        communityLayer.eachLayer(function(layer) {
                                            layer.setStyle({
                                                fillColor: 'transparent',
                                                color: layer._fullStyle.color,
                                                weight: layer._fullStyle.weight,
                                                fillOpacity: 0
                                            });
                                        });
                                        if (legendEl) legendEl.style.display = 'none';
                                    }
                                }

                                colorBtn.addEventListener('click', function() {
                                    applyColorState(COLOR_NEXT[colorState]);
                                });

                                applyColorState(2);
                            }

                            if (markerLayer) {
                                var markersOn = false;
                                map.removeLayer(markerLayer);
                                var markerBtn = L.DomUtil.create('button', 'map-toggle-btn', buttonsRow);
                                markerBtn.type = 'button';
                                markerBtn.textContent = 'Properties';
                                markerBtn.addEventListener('click', function() {
                                    markersOn = !markersOn;
                                    if (markersOn) {
                                        map.addLayer(markerLayer);
                                    } else {
                                        map.removeLayer(markerLayer);
                                    }
                                    markerBtn.classList.toggle('active', markersOn);
                                });
                            }

                            return bar;
                        }
                    });

                    map.addControl(new ToggleControl());
                })();
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


def build_map(dubai_geojson, dubai_wide_geojson, df=None):
    carto_api_key = os.environ.get(
        "CARTO_API_KEY", "cb1_2bhz_1_568999064f58e34559d29936"
    )

    tiles_url = f"https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png?key={carto_api_key}"

    attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

    dubai_map = folium.Map(
        location=[25.011921, 55.349367],
        zoom_start=10,
        tiles=tiles_url,
        attr=attribution,
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

    # Restored property marker cluster (dark-themed to match the rest of
    # the map). Non-fatal if no property data was loaded.
    marker_cluster = None
    if df is not None and not df.empty:
        marker_cluster = MarkerCluster(
            name="Properties",
            icon_create_function="""
            function(cluster) {
                return L.divIcon({
                    html: '<div class="cluster-marker">' + cluster.getChildCount() + '</div>',
                    className: 'marker-cluster-custom',
                    iconSize: L.point(36, 36)
                });
            }
            """,
        ).add_to(dubai_map)

        for _, row in df.iterrows():
            popup_text = f"""
            <div class="property-popup">
                <b>{row.get('Address', 'N/A')}</b><br>
                {row.get('Rent', 'N/A')} AED &middot; {row.get('Beds', 'N/A')} Beds<br>
                {row.get('Location', '')}
            </div>
            """
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=5,
                color="#eeeeee",
                weight=1,
                fill=True,
                fill_color="#bd0026",
                fill_opacity=0.9,
                popup=folium.Popup(popup_text, max_width=260),
            ).add_to(marker_cluster)

        dubai_map.add_child(MarkerTheme())

    dubai_map.add_child(DynamicStyling(community_layer, dubai_wide_layer))
    dubai_map.add_child(PredictHandler())
    dubai_map.add_child(ToggleControls(community_layer, marker_cluster))
    dubai_map.add_child(PredictCaption())

    return dubai_map
