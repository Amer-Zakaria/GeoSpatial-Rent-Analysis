import pandas as pd
import folium
from folium.plugins import MarkerCluster
import json

# 1. Load property data
df = pd.read_csv("uae_properties.csv")

# 2. Filter for Dubai only as requested
df = df[df["City"] == "Dubai"]

# 3. Clean coordinate data
df = df.dropna(subset=["Latitude", "Longitude"])

# 4. Initialize Folium map centered on Dubai
dubai_map = folium.Map(location=[25.2048, 55.2708], zoom_start=11)

# 5. Load GeoJSON boundaries
with open("dubai.geojson", "r", encoding="utf-8") as f:
    dubai_geojson = json.load(f)

# 6. Add GeoJSON boundaries to the map
# We'll use CNAME_E for the location column link if needed for Choropleth,
# but for now, we just plot the boundaries.
folium.GeoJson(
    dubai_geojson,
    name="Dubai Communities",
    style_function=lambda x: {
        "fillColor": "#ffaf00",
        "color": "blue",
        "weight": 1,
        "fillOpacity": 0.1,
    },
    tooltip=folium.GeoJsonTooltip(fields=["CNAME_E"], aliases=["Community:"]),
).add_to(dubai_map)

# 7. Add Marker Clusters for properties
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

# 8. Add Click interaction for Coordinates and Location
# We use a custom JavaScript macro to handle the click and display info
click_js = """
function onClick(e) {
    var lat = e.latlng.lat.toFixed(4);
    var lng = e.latlng.lng.toFixed(4);
    
    // Create a popup at the clicked location
    L.popup()
        .setLatLng(e.latlng)
        .setContent("<b>Coordinates:</b> " + lat + ", " + lng)
        .openOn(this);
        
    console.log("Clicked at: " + lat + ", " + lng);
}
"""

# 8. Add Click interaction for Coordinates
# Folium's LatLngPopup already provides click-to-get-coordinates.
dubai_map.add_child(folium.LatLngPopup())

# For more advanced "Location Name" on click, Folium doesn't easily map back to GeoJSON properties
# in static HTML without a complex search. But LatLngPopup is a good start.
dubai_map.add_child(folium.LatLngPopup())

# 9. Save map
dubai_map.save("dubai_interactive_map.html")
print("Map has been generated as 'dubai_interactive_map.html'")
