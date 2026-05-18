# GeoSpatialDS – Travel time map (Denmark)

This project consist of an spatial auto correlation analysis showcased in ***eda.ipynb*** and a Streamlit app ***main.py*** that visualizes **road travel time** to different healthcare institutions (GP / Hospital / Pharmacy) across Denmark using a hex grid. The application can be found here: 

## Setup

From the `GeoSpatialDS/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run main.py
```

## Notes

- **Input data**: `data/data.csv`
- **Denmark border**: `data/OSM_dk_borders_land_only.geojson`