import os
import json
import pandas as pd
import numpy as np
import streamlit as st
import networkx as nx
import osmnx as ox
import pydeck as pdk
import h3
import matplotlib.colors as mcolors

MAP_INSTITUTION = {
    "GP":       "General Practitoner",
    "Hospital": "Hospital",
    "Pharmacy": "Pharmacy",
}

TYPE_MAP = {
    "GP": "General Practitoner",
    "Hospital": "Hospital",
    "Pharmacy": "Pharmacy",
}

# Using this for color reference https://colorbrewer2.org/#type=diverging&scheme=RdBu&n=6
COLOUR_RANGE = [
    [254,229,217],
    [252,187,161],
    [252,146,114],
    [251,106,74],
    [222,45,38],
    [165,15,21]
]

CMAP = mcolors.LinearSegmentedColormap.from_list(
    "travel",
    [[r / 255, g / 255, b / 255] for r, g, b in COLOUR_RANGE],
)

#Load health institution data only with
@st.cache_data
def load_data():
    df = pd.read_csv("data/data.csv")
    df.columns = df.columns.str.strip()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    return df.dropna(subset=["lat", "lon"])

# Load border data
@st.cache_data
def load_border():
    with open("data/OSM_dk_borders_land_only.geojson") as f:
        return json.load(f)

# Implementation concepts from this blogpost: https://medium.com/@callumjamesscoby/accessibility-analyses-using-h3-db4bf4818a3

# Get hex cells for the map that lies within the border of Denmark
@st.cache_data
def get_hex_cells(resolution):
    gj = load_border()
    geometry = gj["features"][0]["geometry"]
    cells = set()
    coord_lists = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    for poly_coords in coord_lists:
        cells |= set(
            h3.geo_to_cells(
                {"type": "Polygon", "coordinates": poly_coords},
                resolution,
            )
        )
    return list(cells)

#Get road netowrk from osmnx
@st.cache_resource(show_spinner=False)
def load_road_network():
    if os.path.exists("data/denmark_drive.graphml"):
        G = ox.load_graphml("data/denmark_drive.graphml")
    else:
        G = ox.graph_from_place("Denmark", network_type="drive")
        ox.save_graphml(G, "data/denmark_drive.graphml")

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G


# Using djjikstra's algorithm to calculate travel times from each institution to each hex cell
def calculate_travel_times(inst_coords, resolution = 7):

    G = load_road_network()

    coords = np.array(inst_coords)

    inst_lon = coords[:, 1]
    inst_lat = coords[:, 0]

    # snap institutions to nearest road nodes
    inst_nodes = ox.nearest_nodes(
        G,
        inst_lon,
        inst_lat,
    )

    # multi-source shortest path
    node_times = nx.multi_source_dijkstra_path_length(
        G,
        sources=set(inst_nodes),
        weight="travel_time",
    )

    # snap hex centroids
    cells = get_hex_cells(resolution)

    clat_arr = np.array(
        [h3.cell_to_latlng(c)[0] for c in cells]
    )

    clon_arr = np.array(
        [h3.cell_to_latlng(c)[1] for c in cells]
    )

    hex_nodes = ox.nearest_nodes(
        G,
        clon_arr,
        clat_arr,
    )

    rows = [
        {
            "hex": cell,
            "travel_min": node_times.get(node, np.nan) / 60.0,
        }
        for cell, node in zip(cells, hex_nodes)
    ]

    return pd.DataFrame(rows).dropna()


# colour mapping function for travel times
def apply_colour_map(series):
    normalised = mcolors.Normalize(vmin=0, vmax=float(series.quantile(0.95)))
    return [
        [int(c * 255) for c in CMAP(normalised(v))[:3]] + [200]
        for v in series
    ]


# --- User interface ---
st.title("Travel time to Healthcare Institutions in Denmark")

#Load data
df = load_data()

# Institution type selector
selected = st.segmented_control(
    "Institution type",
    options=list(MAP_INSTITUTION.keys()),
    default="GP",
    label_visibility="hidden",
)

#Load road network
with st.spinner("Loading road network…"):
    load_road_network()

#Filter df based on selected institution type
filtered = df[
    df["EntityTypeName"] == TYPE_MAP[selected]
]

inst_tuple = tuple(
    zip(
        filtered["lat"].values,
        filtered["lon"].values,
    )
)

# Show number of institutions
st.caption(f"{len(filtered):,} {selected} locations")

# Compute travel times
with st.spinner("Computing travel times…"):
    tt_df = calculate_travel_times(
        inst_tuple,
        resolution = 7, # similar to 1km hexagons
    )

# Map travel times to colors for visualization
tt_df["colour"] = apply_colour_map(tt_df["travel_min"])
tt_df["travel_min_str"] = tt_df["travel_min"].map(lambda x: f"{x:.1f}")

# tooltip for hex layer
tt_df["tooltip"] = tt_df["travel_min"].map(lambda x: f"<b>{x:.1f} min</b> by road")

#Scatter layer data for institutions
scatter_data = filtered.rename(columns={"lon": "longitude", "lat": "latitude", "EntityName": "entity_name"}).copy()
scatter_data["tooltip"] = scatter_data["entity_name"]

#https://deckgl.readthedocs.io/en/latest/gallery/h3_hexagon_layer.html
# Pydeck layers
hex_layer = pdk.Layer(
    "H3HexagonLayer",
    data=tt_df,
    get_hexagon="hex",
    get_fill_color="colour",
    extruded=False,
    pickable=True,
    auto_highlight=True,
    opacity=1,
)

#https://deckgl.readthedocs.io/en/latest/gallery/scatterplot_layer.html
scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=scatter_data,
    get_position=["longitude", "latitude"],
    get_fill_color=[255, 255, 255, 180],
    get_radius=400,
    radius_min_pixels=2,
    radius_max_pixels=8,
    pickable=True,
)


tooltip = {
    "html": "{tooltip}",
    "style": {
        "backgroundColor": "#1a1a2e",
        "color": "white",
        "fontSize": "13px",
        "padding": "6px 10px",
        "borderRadius": "4px",
    },
}


st.pydeck_chart(
    pdk.Deck(
        layers=[hex_layer, scatter_layer],
        initial_view_state=pdk.ViewState(
            latitude=56.0,
            longitude=11.5,
            zoom=5.5,
            #pitch=0,
        ),
        map_style="dark",
        tooltip=tooltip,
    ),
    width="stretch",
    height=800,
)