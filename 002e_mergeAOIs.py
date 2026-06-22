# ============================
# SCRIPT HEADER
# ============================
"""
This script produces a deforestation driver tif file that includes the drivers from both the  
00c_manual2024_added.gpkg and also the original 00b_manual2024_defo_AOIs.gpkg files storing the AOI boundaries

Combines the two GeoPackage files, merges them, and creates a rasterized output at 10m resolution.
"""

import os
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds

# ============================
# CONFIGURATION
# ============================
# Input driver vectors (these contain the actual deforestation polygons with drivers)
GPKG_PATH = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\Complete_deforestation_drivers_2024.gpkg"
DRIVER_COLUMN = "driver"

# AOI boundary files (these define the spatial extent)
AOI_FILE_ORIGINAL = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\00b_manual2024_defo_AOIs.gpkg"
AOI_FILE_ADDED = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\00c_manual2024_added.gpkg"

# Output paths
OUTPUT_RASTER_10M = "00c_2024_drivers_rasterized_all_10m.tif"
LOOKUP_FILE = "00c_Complete2024_drivers_lookup_table.txt"

# Sentinel-2 resolution (meters)
S2_RESOLUTION = 10.0

# Drivers to keep
DRIVERS_TO_KEEP = ["bb", "fm", "wt"]

# Target CRS (e.g., UTM zone for your area)
TARGET_CRS = "EPSG:32633"  # UTM zone 33N

# ============================
# LOAD DRIVER VECTORS
# ============================
print("=" * 60)
print("STEP 1: LOADING DRIVER VECTOR DATA")
print("=" * 60)
print(f"Loading driver vectors from: {GPKG_PATH}")
gdf = gpd.read_file(GPKG_PATH)

if DRIVER_COLUMN not in gdf.columns:
    raise ValueError(f"Column '{DRIVER_COLUMN}' not found in GPKG. Available columns: {list(gdf.columns)}")

print(f"Vector CRS: {gdf.crs}")
print(f"Total driver features: {len(gdf)}")
print(f"Driver categories: {gdf[DRIVER_COLUMN].unique()}")

# ============================
# FILTER FOR DESIRED DRIVERS
# ============================
print("\n" + "=" * 60)
print("STEP 2: FILTERING FOR DESIRED DRIVERS")
print("=" * 60)
print(f"Keeping only: {DRIVERS_TO_KEEP}")
gdf = gdf[gdf[DRIVER_COLUMN].isin(DRIVERS_TO_KEEP)].copy()
print(f"Filtered features: {len(gdf)}")
print(f"Remaining drivers: {gdf[DRIVER_COLUMN].unique()}")

# ============================
# LOAD AND COMBINE AOI BOUNDARIES
# ============================
print("\n" + "=" * 60)
print("STEP 3: LOADING AND COMBINING AOI BOUNDARIES")
print("=" * 60)

# Load original AOI
print(f"Loading original AOI: {os.path.basename(AOI_FILE_ORIGINAL)}")
aoi_original = gpd.read_file(AOI_FILE_ORIGINAL)
print(f"  Original AOI CRS: {aoi_original.crs}")
print(f"  Original AOI features: {len(aoi_original)}")

# Load added AOI
print(f"Loading added AOI: {os.path.basename(AOI_FILE_ADDED)}")
aoi_added = gpd.read_file(AOI_FILE_ADDED)
print(f"  Added AOI CRS: {aoi_added.crs}")
print(f"  Added AOI features: {len(aoi_added)}")

# Ensure both AOIs are in the same CRS before combining
if aoi_original.crs != TARGET_CRS:
    print(f"  Reprojecting original AOI from {aoi_original.crs} → {TARGET_CRS}")
    aoi_original = aoi_original.to_crs(TARGET_CRS)

if aoi_added.crs != TARGET_CRS:
    print(f"  Reprojecting added AOI from {aoi_added.crs} → {TARGET_CRS}")
    aoi_added = aoi_added.to_crs(TARGET_CRS)

# Combine AOIs
print("Combining AOI boundaries...")
# Keep only geometry column for combining
aoi_combined = gpd.GeoDataFrame(
    geometry=list(aoi_original.geometry) + list(aoi_added.geometry),
    crs=TARGET_CRS
)
print(f"  Combined AOI features: {len(aoi_combined)}")

# Create a single unified boundary (union of all geometries)
print("Creating unified AOI boundary...")
aoi_union = aoi_combined.unary_union
print("  Unified boundary created")

# ============================
# REPROJECT DRIVER VECTORS TO TARGET CRS
# ============================
print("\n" + "=" * 60)
print("STEP 4: REPROJECTING DRIVER VECTORS TO TARGET CRS")
print("=" * 60)

if gdf.crs != TARGET_CRS:
    print(f"Reprojecting driver vectors from {gdf.crs} → {TARGET_CRS}")
    gdf = gdf.to_crs(TARGET_CRS)
else:
    print("Driver vectors already in target CRS")

# ============================
# CLIP DRIVERS TO COMBINED AOI
# ============================
print("\n" + "=" * 60)
print("STEP 5: CLIPPING DRIVERS TO COMBINED AOI")
print("=" * 60)
print(f"Features before clipping: {len(gdf)}")
gdf = gpd.clip(gdf, aoi_union)
print(f"Features after clipping: {len(gdf)}")
print(f"Drivers in clipped data: {gdf[DRIVER_COLUMN].unique()}")

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

# Check for any remaining issues
print(f"Driver_int range: {gdf['driver_int'].min()} - {gdf['driver_int'].max()}")
print(f"Unique driver_int values: {sorted(gdf['driver_int'].unique())}")

# Save lookup table
print(f"\nSaving lookup table: {LOOKUP_FILE}")
with open(LOOKUP_FILE, "w", encoding='utf-8') as f:
    f.write("Integer_Code\tDriver_Category\tDescription\n")
    f.write("0\tBackground\tNo deforestation / Background\n")
    for cat, code in sorted(val_to_int.items(), key=lambda x: x[1]):
        description = {
            'bb': 'Boomkap (logging)',
            'fm': 'Fire/Mining',
            'wt': 'Windthrow'
        }.get(cat, cat)
        f.write(f"{code}\t{cat}\t{description}\n")

print("Lookup table saved")

# ============================
# CALCULATE RASTER GRID FOR 10M RESOLUTION (CLIPPED TO COMBINED AOI)
# ============================
print("\n" + "=" * 60)
print("STEP 7: CALCULATING 10M RASTER GRID (CLIPPED TO COMBINED AOI)")
print("=" * 60)

# Get bounds of the combined AOI
aoi_bounds = aoi_combined.total_bounds
print(f"Combined AOI bounds (minx, miny, maxx, maxy):")
print(f"  {aoi_bounds}")

# Calculate dimensions at 10m resolution
width = int(np.ceil((aoi_bounds[2] - aoi_bounds[0]) / S2_RESOLUTION))
height = int(np.ceil((aoi_bounds[3] - aoi_bounds[1]) / S2_RESOLUTION))

print(f"10m raster dimensions: {width} x {height} pixels")
print(f"10m raster size: {width * height:,} pixels")

# Calculate transform for 10m resolution
transform = from_bounds(
    aoi_bounds[0], aoi_bounds[1], aoi_bounds[2], aoi_bounds[3],
    width, height
)

print(f"Transform: {transform}")
print(f"Pixel size: {transform[0]:.2f} x {-transform[4]:.2f} meters")

# ============================
# RASTERIZE TO 10M RESOLUTION (CLIPPED TO COMBINED AOI)
# ============================
print("\n" + "=" * 60)
print("STEP 8: RASTERIZING TO 10M RESOLUTION")
print("=" * 60)

# Prepare shapes for rasterization
shapes = [
    (geom, int(val))
    for geom, val in zip(gdf.geometry, gdf["driver_int"])
    if geom is not None and val > 0
]

print(f"Number of shapes to rasterize: {len(shapes)}")

# Rasterize
print("Rasterizing...")
driver_raster_10m = rasterize(
    shapes=shapes,
    out_shape=(height, width),
    transform=transform,
    fill=0,  # Background value
    dtype=np.uint8
)

print(f"Rasterization complete")
print(f"Raster shape: {driver_raster_10m.shape}")
print(f"Raster dtype: {driver_raster_10m.dtype}")

# ============================
# SAVE OUTPUT RASTER
# ============================
print("\n" + "=" * 60)
print("STEP 9: SAVING OUTPUT RASTER")
print("=" * 60)

profile = {
    "driver": "GTiff",
    "dtype": np.uint8,
    "count": 1,
    "crs": TARGET_CRS,
    "transform": transform,
    "width": driver_raster_10m.shape[1],
    "height": driver_raster_10m.shape[0],
    "nodata": 0,
    "compress": "lzw"
}

print(f"Writing 10m raster: {OUTPUT_RASTER_10M}")
with rasterio.open(OUTPUT_RASTER_10M, "w", **profile) as dst:
    dst.write(driver_raster_10m, 1)

print("Raster saved successfully")

# ============================
# RASTER STATISTICS
# ============================
print("\n" + "=" * 60)
print("RASTER STATISTICS")
print("=" * 60)

print(f"Min value: {driver_raster_10m.min()}")
print(f"Max value: {driver_raster_10m.max()}")

unique_values, counts = np.unique(driver_raster_10m, return_counts=True)
total_pixels = driver_raster_10m.size

print(f"\nUnique values in raster: {unique_values}")
print(f"\nPixel counts by driver:")
for val, count in zip(unique_values, counts):
    percentage = (count / total_pixels) * 100
    if val == 0:
        label = "Background"
    else:
        # Find driver name from mapping
        label = [k for k, v in val_to_int.items() if v == val]
        label = label[0] if label else f"Unknown ({val})"

    print(f"  {val} ({label}): {count:,} pixels ({percentage:.2f}%)")

# ============================
# SUMMARY
# ============================
print("\n" + "=" * 60)
print("PROCESSING COMPLETE")
print("=" * 60)
print(f"Output files:")
print(f"  - 10m raster (S2): {OUTPUT_RASTER_10M}")
print(f"  - Lookup table: {LOOKUP_FILE}")
print(f"\nRaster properties:")
print(f"  - Resolution: {S2_RESOLUTION}m")
print(f"  - CRS: {TARGET_CRS}")
print(f"  - Dimensions: {width} x {height} pixels")
print(f"  - Data type: uint8")
print(f"  - Compression: LZW")
print("=" * 60)