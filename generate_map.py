import pandas as pd
import folium
from folium.plugins import MarkerCluster
import json
from branca.element import MacroElement
from jinja2 import Template

# 1. Load property data
df = pd.read_csv("uae_properties.csv")

# 2. Filter for Dubai only
df = df[df["City"] == "Dubai"]

# 3. Clean coordinate data
df = df.dropna(subset=["Latitude", "Longitude"])

# 4. Initialize Folium map centered on Dubai (Dark Mode)
dubai_map = folium.Map(
    location=[25.011921, 55.349367],
    zoom_start=10,
    tiles="CartoDB dark_matter",
    control_scale=True,
)

# 5. Load GeoJSON boundaries
with open("dubai.geojson", "r", encoding="utf-8") as f:
    dubai_geojson = json.load(f)

with open("dubai-boundary.geojson", "r", encoding="utf-8") as f:
    dubai_wide_geojson = json.load(f)

# 6. Add GeoJSON boundaries with gray lines and minimal styling
community_layer = folium.GeoJson(
    dubai_geojson,
    name="Dubai Communities",
    style_function=lambda x: {
        "fillColor": "transparent",
        "color": "#444444",  # Gray boundaries
        "weight": 0.8,
        "fillOpacity": 0,
    },
    tooltip=folium.GeoJsonTooltip(fields=["CNAME_E"], aliases=["Community:"]),
).add_to(dubai_map)

# Add Dubai-wide boundary (notably thicker)
dubai_wide_layer = folium.GeoJson(
    dubai_wide_geojson,
    name="Dubai Boundary",
    style_function=lambda x: {
        "fillColor": "transparent",
        "color": "#666666",  # Slightly lighter gray for the main boundary
        "weight": 2.5,
        "fillOpacity": 0,
        "interactive": False,  # Make it non-interactive so it doesn't block tooltips
    },
).add_to(dubai_map)


# 7. Add Zoom-dependent boundary thickness and remove focus outline
class DynamicStyling(MacroElement):
    def __init__(self, community_layer, city_layer):
        super(DynamicStyling, self).__init__()
        self.community_layer = community_layer
        self.city_layer = city_layer
        self._template = Template(
            """
            {% macro script(this, kwargs) %}
                var community_layer = {{this.community_layer.get_name()}};
                var city_layer = {{this.city_layer.get_name()}};
                var map = {{this._parent.get_name()}};

                function updateStyle() {
                    var zoom = map.getZoom();
                    
                    // Community boundaries dynamic weight
                    var commWeight = 0.5 + (zoom - 10) * 0.5;
                    if (commWeight < 0.5) commWeight = 0.5;
                    if (commWeight > 4) commWeight = 4;
                    
                    community_layer.setStyle({
                        weight: commWeight
                    });

                    // City boundary dynamic weight (notably thicker)
                    var cityWeight = 2.0 + (zoom - 10) * 1.0;
                    if (cityWeight < 2.0) cityWeight = 2.0;
                    if (cityWeight > 8) cityWeight = 8;

                    city_layer.setStyle({
                        weight: cityWeight
                    });
                }

                updateStyle(); // Initial call
                map.on('zoomend', updateStyle); // Update on zoom changes

                // Remove the focus rectangle/outline on click/drag
                var style = document.createElement('style');
                style.innerHTML = '.leaflet-interactive { outline: none !important; }';
                document.getElementsByTagName('head')[0].appendChild(style);
            {% endmacro %}
            """
        )


dubai_map.add_child(DynamicStyling(community_layer, dubai_wide_layer))

# 8. Add Marker Clusters for properties
marker_cluster = MarkerCluster(name="Properties").add_to(dubai_map)

for idx, row in df.iterrows():
    popup_text = f"""
    <b>Address:</b> {row['Address']}<br>
    <b>Rent:</b> {row['Rent']} AED<br>
    <b>Beds:</b> {row['Beds']}<br>
    <b>Location:</b> {row['Location']}
    """
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=folium.Popup(popup_text, max_width=300),
    ).add_to(marker_cluster)


# 9. Add Click Handler
class ClickHandler(MacroElement):
    _template = Template(
        """
            {% macro script(this, kwargs) %}
            function decimalToDMS(decimal) {
                var abs_dec = Math.abs(decimal);
                var degrees = Math.floor(abs_dec);
                var minutes = Math.floor((abs_dec - degrees) * 60);
                var seconds = ((abs_dec - degrees - minutes / 60) * 3600).toFixed(2);
                return { deg: degrees, min: minutes, sec: seconds };
            }

            function convertCoordinates(lat, lng) {
                var lat_dms = decimalToDMS(lat);
                var lng_dms = decimalToDMS(lng);
                var lat_dir = lat >= 0 ? "N" : "S";
                var lng_dir = lng >= 0 ? "E" : "W";
                
                var lat_str = lat_dms.deg + "° " + lat_dms.min + "' " + lat_dms.sec + '" ' + lat_dir;
                var lng_str = lng_dms.deg + "° " + lng_dms.min + "' " + lng_dms.sec + '" ' + lng_dir;
                
                return { lat: lat_str, lng: lng_str };
            }

            {{this._parent.get_name()}}.on('click', function(e) {
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                var dms = convertCoordinates(lat, lng);
                
                var content = `
                    <div style="font-family: sans-serif; min-width: 200px;">
                        <b>Decimal:</b> ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>
                        <b>DMS Lat:</b> ${dms.lat}<br>
                        <b>DMS Lon:</b> ${dms.lng}
                    </div>
                `;
                
                L.popup()
                    .setLatLng(e.latlng)
                    .setContent(content)
                    .openOn({{this._parent.get_name()}});
            });
            {% endmacro %}
        """
    )

    def __init__(self):
        super(ClickHandler, self).__init__()


dubai_map.add_child(ClickHandler())

# 10. Save map
dubai_map.save("dubai_interactive_map.html")
print("Map has been generated as 'dubai_interactive_map.html'")
