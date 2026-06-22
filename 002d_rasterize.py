import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import calculate_default_transform, reproject
from rasterio.enums import Resampling
import numpy as np
import os

# ============================
# SCRIPT HEADER
# ============================
"""
This script loads a vector dataset of deforestation drivers,
reprojects it to a projected CRS (e.g., UTM),
clips the drivers to the desired AOI,
filters for only the 3 main drivers (bb, fm, wt),
and rasterizes it to 10m resolution (Sentinel-2) using a space-saving datatype.
Output: A 10m raster with driver labels, clipped to AOI.
"""

# ============================
# CONFIGURATION
# ============================
# Input paths
GPKG_PATH = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\Complete_deforestation_drivers_2023.gpkg"
DRIVER_COLUMN = "driver"
#general AOI files
#AOI_FILE = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\00b_manual2024_defo_AOIs.gpkg"
# adidtional drivers
AOI_FILE = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\00b_Complete2023_AOIs.gpkg"



# Output paths
# new driver raster needs to be made herefor GT year 209-03-2026
OUTPUT_RASTER_10M = "00c_2023_drivers_rasterized_added_10m.tif"

LOOKUP_FILE = "00c_Complete2023_drivers_lookup_table.txt"

# Sentinel-2 resolution (meters)
S2_RESOLUTION = 10.0
# Drivers to keep
DRIVERS_TO_KEEP = ["bb", "fm", "wt"]

# Target CRS (e.g., UTM zone for your area)
TARGET_CRS = "EPSG:32633"  # Example: UTM zone 33N (adjust for your area)

# ============================
# LOAD DRIVER VECTORS
# ============================
print("=" * 60)
print("STEP 1: LOADING VECTOR DATA")
print("=" * 60)
print(f"Loading vectors from: {GPKG_PATH}")
gdf = gpd.read_file(GPKG_PATH)

if DRIVER_COLUMN not in gdf.columns:
    raise ValueError(f"Column '{DRIVER_COLUMN}' not found in GPKG. Available columns: {list(gdf.columns)}")

print(f"Vector CRS: {gdf.crs}")
print(f"Total features: {len(gdf)}")
print(f"Driver categories: {gdf[DRIVER_COLUMN].unique()}")

# ============================
# FILTER FOR DESIRED DRIVERS
# ============================
print("\n" + "=" * 60)
print("STEP 2: FILTERING FOR DESIRED DRIVERS")
print("=" * 60)
gdf = gdf[gdf[DRIVER_COLUMN].isin(DRIVERS_TO_KEEP)]
print(f"Filtered features: {len(gdf)}")

# ============================
# LOAD AND REPROJECT AOI
# ============================
print("\n" + "=" * 60)
print("STEP 3: LOADING AND REPROJECTING AOI")
print("=" * 60)
aoi = gpd.read_file(AOI_FILE)
if aoi.crs != TARGET_CRS:
    print(f"Reprojecting AOI from {aoi.crs} → {TARGET_CRS}")
    aoi = aoi.to_crs(TARGET_CRS)
else:
    print("AOI already in target CRS")

# ============================
# REPROJECT VECTORS TO TARGET CRS
# ============================
print("\n" + "=" * 60)
print("STEP 4: REPROJECTING VECTORS TO TARGET CRS")
print("=" * 60)

if gdf.crs != TARGET_CRS:
    print(f"Reprojecting vectors from {gdf.crs} → {TARGET_CRS}")
    gdf = gdf.to_crs(TARGET_CRS)
else:
    print("Vectors already in target CRS")

# ============================
# CLIP DRIVERS TO AOI
# ============================
print("\n" + "=" * 60)
print("STEP 5: CLIPPING DRIVERS TO AOI")
print("=" * 60)
gdf = gpd.clip(gdf, aoi.unary_union)
print(f"Clipped features: {len(gdf)}")

# ============================
# CREATE INTEGER LABELS FOR DRIVERS
# ============================
print("\n" + "=" * 60)
print("STEP 6: CREATING INTEGER LABELS")
print("=" * 60)

unique_vals = sorted(DRIVERS_TO_KEEP)
val_to_int = {v: i + 1 for i, v in enumerate(unique_vals)}

print("Category → integer mapping:")
for cat, code in val_to_int.items():
    print(f"  {code}: {cat}")

# Add integer column
gdf["driver_int"] = gdf[DRIVER_COLUMN].map(val_to_int)

# Handle any NaN or missing values
gdf["driver_int"] = gdf["driver_int"].fillna(0).astype(np.uint8)

# Save lookup table
with open(LOOKUP_FILE, "w", encoding='utf-8') as f:
    f.write("Integer_Code\tDriver_Category\n")
    f.write("0\tNo Data / Background\n")
    for cat, code in val_to_int.items():
        f.write(f"{code}\t{cat}\n")

print(f"Lookup table saved: {LOOKUP_FILE}")

# ============================
# CALCULATE RASTER GRID FOR 10M RESOLUTION (CLIPPED TO AOI)
# ============================
print("\n" + "=" * 60)
print("STEP 7: CALCULATING 10M RASTER GRID (CLIPPED TO AOI)")
print("=" * 60)

# Get bounds of the AOI in the target CRS
aoi_bounds = aoi.total_bounds
print(f"AOI bounds: {aoi_bounds}")

# Calculate transform and dimensions for 10m resolution
transform = from_bounds(
    aoi_bounds[0], aoi_bounds[1], aoi_bounds[2], aoi_bounds[3],
    int((aoi_bounds[2] - aoi_bounds[0]) / S2_RESOLUTION),
    int((aoi_bounds[3] - aoi_bounds[1]) / S2_RESOLUTION)
)

print(f"10m raster dimensions: {transform[0]}, {transform[4]}")
print(f"10m raster shape: {int((aoi_bounds[2] - aoi_bounds[0]) / S2_RESOLUTION)} x {int((aoi_bounds[3] - aoi_bounds[1]) / S2_RESOLUTION)}")

# ============================
# RASTERIZE TO 10M RESOLUTION (CLIPPED TO AOI)
# ============================
print("\n" + "=" * 60)
print("STEP 8: RASTERIZING TO 10M RESOLUTION (CLIPPED TO AOI)")
print("=" * 60)

shapes = [
    (geom, int(val))
    for geom, val in zip(gdf.geometry, gdf["driver_int"])
    if geom is not None and val > 0
]

driver_raster_10m = rasterize(
    shapes=shapes,
    out_shape=(
        int((aoi_bounds[3] - aoi_bounds[1]) / S2_RESOLUTION),
        int((aoi_bounds[2] - aoi_bounds[0]) / S2_RESOLUTION)
    ),
    transform=transform,
    fill=0,
    dtype=np.uint8  # Space-saving datatype
)

# ============================
# SAVE OUTPUT RASTER
# ============================
print("\n" + "=" * 60)
print("STEP 9: SAVING OUTPUT RASTER")
print("=" * 60)

profile = {
    "driver": "GTiff",
    "dtype": np.uint8,  # Space-saving datatype
    "count": 1,
    "crs": TARGET_CRS,
    "transform": transform,
    "width": driver_raster_10m.shape[1],
    "height": driver_raster_10m.shape[0],
    "nodata": 0,
    "compress": "lzw"  # Additional compression
}

print(f"Writing 10m raster: {OUTPUT_RASTER_10M}")
with rasterio.open(OUTPUT_RASTER_10M, "w", **profile) as dst:
    dst.write(driver_raster_10m, 1)

print(f"10m raster stats: min={driver_raster_10m.min()}, max={driver_raster_10m.max()}")
unique_values_10m = np.unique(driver_raster_10m)
print(f"Unique values in 10m raster: {unique_values_10m}")

# ============================
# SUMMARY
# ============================
print("\n" + "=" * 60)
print("PROCESSING COMPLETE")
print("=" * 60)
print(f"Output files:")
print(f"  - 10m raster (S2): {OUTPUT_RASTER_10M}")
print(f"  - Lookup table: {LOOKUP_FILE}")
print("=" * 60)
