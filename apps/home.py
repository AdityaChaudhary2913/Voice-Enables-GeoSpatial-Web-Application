import streamlit as st
import leafmap.foliumap as leafmap
from geopy.geocoders import Nominatim
import requests
import folium
import polyline
import tempfile
import os
from audio_to_text import process_audio
from audio_recorder_streamlit import audio_recorder

# India geographical constraints
INDIA_BOUNDS = {
    "min_lat": 8.0,
    "max_lat": 37.6,
    "min_lon": 68.7,
    "max_lon": 97.25
}

def is_within_india(lat, lon):
    """Check if coordinates are within India's boundaries"""
    return (INDIA_BOUNDS["min_lat"] <= lat <= INDIA_BOUNDS["max_lat"] and
            INDIA_BOUNDS["min_lon"] <= lon <= INDIA_BOUNDS["max_lon"])

def get_route(start_coords, end_coords):
    """Get driving route coordinates and distance using OSRM API"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full"
        response = requests.get(url)
        data = response.json()

        if data.get('code') == 'Ok' and data.get('routes'):
            route_coords = polyline.decode(data['routes'][0]['geometry'])
            distance = data['routes'][0]['distance']  # in meters
            
            # Check if all route points are within India
            if not all(is_within_india(p[0], p[1]) for p in route_coords):
                return None, None
                
            return route_coords, distance
        return None, None
    except Exception as e:
        st.error(f"Routing error: {str(e)}")
        return None, None

def app():
    st.title("Geospatial Command Processor")
    
    # Initialize session state
    session_defaults = {
        "zoom": 4,
        "center": [20.5937, 78.9629],  # Default center (India)
        "basemap": "ROADMAP",
        "markers": [],
        "route": None,
        "distance": None,
        "bounds": None,
        "road_layer": None,
        "nh_layer": None,
        "nh_number": None
    }
    for key, val in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
            
    # Voice input section
    st.subheader("Voice Commands")
    audio_bytes = audio_recorder(text="Click to record command", pause_threshold=2.0)
    
    command = None
    
    if audio_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
            fp.write(audio_bytes)
            temp_path = fp.name
        
        with st.spinner("Processing voice command..."):
            try:
                command = process_audio(temp_path)
                print(command)
                st.session_state.command = command
                st.success(f"Detected command: {command}")
            except Exception as e:
                st.error(f"Error processing audio: {str(e)}")
        
        os.unlink(temp_path)

    # Input box for preprocessed command
    # command = st.text_input("Enter command (e.g., 'Jaipur', 'Road Layer', 'NH32'):")

    if command:
        cmd = command.strip().lower()
        
        # Clear previous results for new commands
        if cmd not in ["satellite", "zoom in", "zoom out"]:
            st.session_state.markers = []
            st.session_state.route = None
            st.session_state.distance = None
            st.session_state.bounds = None
            if cmd != "road layer" and not cmd.startswith("NH"):
                st.session_state.road_layer = None
                st.session_state.nh_layer = None
                st.session_state.nh_number = None

        # Process the command
        if cmd == "satellite":
            st.session_state.basemap = "SATELLITE"
        elif cmd == "zoom in":
            st.session_state.zoom = min(st.session_state.zoom + 1, 18)
        elif cmd == "zoom out":
            st.session_state.zoom = max(st.session_state.zoom - 1, 1)
        elif cmd == "road layer":
            try:
                overpass_query = """
                    [out:json];
                    way["highway"~"motorway|trunk|primary|secondary|tertiary"](8.4,68.7,37.6,97.3);
                    out geom;
                """
                response = requests.post(
                    'http://overpass-api.de/api/interpreter',
                    data={'data': overpass_query},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                features = []
                for element in data.get('elements', []):
                    if element['type'] == 'way' and 'geometry' in element:
                        coordinates = [(node['lon'], node['lat']) for node in element['geometry']]
                        feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": coordinates
                            },
                            "properties": element.get('tags', {})
                        }
                        features.append(feature)
                st.session_state.road_layer = {"type": "FeatureCollection", "features": features}
            except Exception as e:
                st.error(f"Error fetching road layer: {str(e)}")
                st.session_state.road_layer = None
        elif cmd.startswith("NH"):
            nh_num = cmd[2:].strip()
            if nh_num.isdigit():
                try:
                    st.session_state.nh_number = nh_num
                    overpass_query = f"""
                        [out:json];
                        way["ref"="NH{nh_num}"](8.4,68.7,37.6,97.3);
                        out geom;
                    """
                    response = requests.post(
                        'http://overpass-api.de/api/interpreter',
                        data={'data': overpass_query},
                        timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()
                    features = []
                    for element in data.get('elements', []):
                        if element['type'] == 'way' and 'geometry' in element:
                            coordinates = [(node['lon'], node['lat']) for node in element['geometry']]
                            feature = {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": coordinates
                                },
                                "properties": element.get('tags', {})
                            }
                            features.append(feature)
                    st.session_state.nh_layer = {"type": "FeatureCollection", "features": features}
                except Exception as e:
                    st.error(f"Error fetching NH{nh_num} data: {str(e)}")
                    st.session_state.nh_layer = None
            else:
                st.error("Invalid National Highway number. Please use format like 'NH32'.")
        else:
            # Handle city names
            cities = command.strip().split(" ")
            geolocator = Nominatim(user_agent="geo_command")
            
            if len(cities) == 1:
                # Single city (Type1)
                location = geolocator.geocode(cities[0], country_codes='in')
                if location:
                    if is_within_india(location.latitude, location.longitude):
                        st.session_state.markers.append(
                            (location.latitude, location.longitude, cities[0])
                        )
                        st.session_state.center = [location.latitude, location.longitude]
                        st.session_state.zoom = 12
                    else:
                        st.error(f"Location '{cities[0]}' is outside India")
                else:
                    st.error(f"Location '{cities[0]}' not found in India")
                    
            elif len(cities) == 2:
                # Two cities (Type3)
                start = geolocator.geocode(cities[0], country_codes='in')
                end = geolocator.geocode(cities[1], country_codes='in')
                
                valid = True
                if not start:
                    st.error(f"Start location '{cities[0]}' not found in India")
                    valid = False
                elif not is_within_india(start.latitude, start.longitude):
                    st.error(f"Start location '{cities[0]}' is outside India")
                    valid = False
                    
                if not end:
                    st.error(f"End location '{cities[1]}' not found in India")
                    valid = False
                elif not is_within_india(end.latitude, end.longitude):
                    st.error(f"End location '{cities[1]}' is outside India")
                    valid = False
                
                if valid:
                    route_coords, distance = get_route(
                        (start.latitude, start.longitude),
                        (end.latitude, end.longitude)
                    )
                    if route_coords:
                        st.session_state.route = {
                            "start": (start.latitude, start.longitude),
                            "end": (end.latitude, end.longitude),
                            "coords": route_coords,
                            "start_name": cities[0],
                            "end_name": cities[1]
                        }
                        st.session_state.distance = distance
                        
                        # Calculate bounds for the route
                        lats = [p[0] for p in route_coords] + [start.latitude, end.latitude]
                        lons = [p[1] for p in route_coords] + [start.longitude, end.longitude]
                        st.session_state.bounds = [
                            [min(lats), min(lons)], 
                            [max(lats), max(lons)]
                        ]

    # Map initialization
    m = leafmap.Map(center=st.session_state.center, zoom=st.session_state.zoom)
    m.add_basemap(st.session_state.basemap)

    # Add road layer
    if st.session_state.road_layer:
        folium.GeoJson(
            st.session_state.road_layer,
            name='Roads Layer',
            style_function=lambda x: {'color': '#90EE90', 'weight': 2, 'opacity': 0.7}
        ).add_to(m)

    # Add NH layer
    if st.session_state.nh_layer and st.session_state.nh_number:
        folium.GeoJson(
            st.session_state.nh_layer,
            name=f'NH{st.session_state.nh_number}',
            style_function=lambda x: {
                'color': 'blue',
                'weight': 5,
                'opacity': 0.7
            }
        ).add_to(m)

    # Add markers and features
    if st.session_state.markers:
        for marker in st.session_state.markers:
            lat, lon, name = marker
            m.add_marker(
                [lat, lon],
                popup=f"Location: {name}",
                icon=folium.Icon(color="red", icon="info-sign")
            )

    if st.session_state.route:
        # Add route markers
        m.add_marker(
            st.session_state.route["start"],
            popup=f"Start: {st.session_state.route['start_name']}",
            icon=folium.Icon(color="green", icon="play")
        )
        m.add_marker(
            st.session_state.route["end"],
            popup=f"End: {st.session_state.route['end_name']}",
            icon=folium.Icon(color="red", icon="stop")
        )
        # Draw route
        folium.PolyLine(
            locations=st.session_state.route["coords"],
            color="blue",
            weight=5,
            opacity=0.7
        ).add_to(m)
        
        # Display distance
        if st.session_state.distance:
            st.success(f"Route Distance: {st.session_state.distance/1000:.2f} km")

    # Adjust map bounds if route exists
    if st.session_state.bounds:
        m.fit_bounds(st.session_state.bounds)

    # Display the map
    m.to_streamlit(height=700)

if __name__ == "__main__":
    app()
