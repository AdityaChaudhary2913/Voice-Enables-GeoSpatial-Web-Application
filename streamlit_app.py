import streamlit as st
from streamlit_option_menu import option_menu
from apps import home, heatmap, upload  # import your app modules here

st.set_page_config(page_title="Streamlit Geospatial", layout="wide")

apps = [
    {"func": home.app, "title": "Home", "icon": "house"},
    {"func": heatmap.app, "title": "Heatmap", "icon": "map"},
    # {"func": upload.app, "title": "Upload", "icon": "cloud-upload"},
]

titles = [app["title"] for app in apps]
icons = [app["icon"] for app in apps]

params = st.query_params

# Set default page to home.app if no query parameter is found
default_index = 0  # Default to Home
if "page" in params:
    try:
        default_index = int(titles.index(params["page"][0].lower()))
    except ValueError:
        pass  # Keep default_index as 0 if the page param is invalid
    
selected = titles[default_index]  # Auto-select default page without sidebar

for app in apps:
    if app["title"] == selected:
        app["func"]()
        break
