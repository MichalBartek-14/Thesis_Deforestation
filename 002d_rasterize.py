import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
import numpy as np
import os
from shapely.geometry import box
from sklearn.cluster import DBSCAN

# 002d_rasterize
"""
This script loads a vector dataset storing the information from the deforestation analysis in a gpkg. 
Then it loads the GFC Hansen dataset as a snap raster, then it creates a new raster and to which the driver information is appended
After an overlay.
Output is a raster with the driver information for each pixel. 
__
Adds the bboxes for the areas which have high concentration of deforestation events. Box cannot be more than 50x50km and not smaller than 20x20km

"""
#GPKG_PATH = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\AUTO_Forest_Disturbance_events_2024x.gpkg"
GPKG_PATH = r"C:\Users\misko\Documents\Forest_Disturbance_events.shp"
DRIVER_COLUMN = "driver"
GFC_RASTER = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\outputs\Processed_GFC_001b.tif"
OUTPUT_RASTER = "Test3_2024_drivers_rasterized.tif"
#0000
LOOKUP_FILE = "driver_lookup_table.txt"

# ----------------------------
# LOAD DRIVER VECTORS
# ----------------------------
print("Loading vectors...")
gdf = gpd.read_file(GPKG_PATH)

if DRIVER_COLUMN not in gdf.columns:
    raise ValueError(f"Column '{DRIVER_COLUMN}' not found in GPKG.")

print("Vector CRS:", gdf.crs)

# ----------------------------
# LOAD SNAP RASTER (GFC HANSEN)
# ----------------------------
print("Loading GFC snap raster...")
with rasterio.open(GFC_RASTER) as src:
    snap_meta = src.meta.copy()
    snap_crs = src.crs
    snap_transform = src.transform
    snap_width, snap_height = src.width, src.height

print("Snap raster CRS:", snap_crs)

# ----------------------------
# REPROJECT VECTORS TO SNAP CRS
# ----------------------------
if gdf.crs != snap_crs:
    print("Reprojecting vectors → snap CRS…")
    gdf = gdf.to_crs(snap_crs)

# ----------------------------
# CREATE INTEGER LABELS FOR DRIVERS
# ----------------------------
unique_vals = gdf[DRIVER_COLUMN].unique()
val_to_int = {v: i + 1 for i, v in enumerate(unique_vals)}

print("Category → integer mapping:", val_to_int)

# Add integer column
gdf["driver_int"] = gdf[DRIVER_COLUMN].map(val_to_int)

# Save lookup table
with open(LOOKUP_FILE, "w") as f:
    f.write("Driver_Category\tInteger_Code\n")
    for cat, code in val_to_int.items():
        f.write(f"{cat}\t{code}\n")

print("Lookup table saved:", LOOKUP_FILE)

# ----------------------------
# RASTERIZATION (USING SNAP RASTER GRID EXACTLY)
# ----------------------------
print("Rasterizing drivers...")

shapes = [
    (geom, int(val))
    for geom, val in zip(gdf.geometry, gdf["driver_int"])
]

driver_raster = rasterize(
    shapes=shapes,
    out_shape=(snap_height, snap_width),
    transform=snap_transform,
    fill=0,
    dtype=rasterio.int32
)

# ----------------------------
# SAVE OUTPUT RASTER
# ----------------------------
snap_meta.update({
    "dtype": rasterio.int32,
    "count": 1
})

print("Writing raster file:", OUTPUT_RASTER)

with rasterio.open(OUTPUT_RASTER, "w", **snap_meta) as dst:
    dst.write(driver_raster, 1)

