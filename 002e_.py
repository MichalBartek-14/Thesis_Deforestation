import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import Point, box
from sklearn.cluster import DBSCAN

# -----------------------------
# USER INPUTS
# -----------------------------
INPUT_RASTER = "Test3_2024_drivers_rasterized.tif"
OUTPUT_GPKG = "test3_2024_defo_bboxes.gpkg"

BOX_SIZE_KM = 50        # Fixed box size (50x50 km)
N_BOXES = 10            # Number of boxes the user wants
DBSCAN_EPS_METERS = 5000
DBSCAN_MIN_SAMPLES = 20

# -----------------------------
# LOAD THE DRIVER RASTER
# -----------------------------
print("Loading raster:", INPUT_RASTER)

with rasterio.open(INPUT_RASTER) as src:
    raster = src.read(1)
    transform = src.transform
    raster_crs = src.crs

print("Raster CRS:", raster_crs)

# -----------------------------
# EXTRACT HOTSPOT PIXELS
# -----------------------------
print("Extracting hotspot pixels...")

rows, cols = np.where(raster > 0)

if len(rows) == 0:
    raise ValueError("No hotspot pixels found (>0).")

xs, ys = rasterio.transform.xy(transform, rows, cols)

points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs, ys), crs=raster_crs)

# Ensure projected coordinates for distances
if not points.crs.is_projected:
    print("CRS not projected. Reprojecting to EPSG:3857 for clustering...")
    points = points.to_crs(3857)

# -----------------------------
# CLUSTER HOTSPOT PIXELS (DBSCAN)
# -----------------------------
print("Running DBSCAN...")

coords = np.vstack([points.geometry.x, points.geometry.y]).T

db = DBSCAN(
    eps=DBSCAN_EPS_METERS,
    min_samples=DBSCAN_MIN_SAMPLES
).fit(coords)

points["cluster"] = db.labels_

clusters = points[points["cluster"] != -1].dissolve(by="cluster")

print(f"Detected {len(clusters)} hotspot clusters.")

# -----------------------------
# GENERATE FIXED-SIZE BOUNDING BOXES
# -----------------------------
print("Generating fixed 50x50 km bounding boxes...")

BOX_M = BOX_SIZE_KM * 1000
half = BOX_M / 2

bboxes = []

for idx, row in clusters.iterrows():
    cx, cy = row.geometry.centroid.x, row.geometry.centroid.y

    new_box = box(cx - half, cy - half, cx + half, cy + half)
    bboxes.append((idx, new_box))

# -----------------------------
# REMOVE OVERLAPPING BOXES
# -----------------------------
print("Removing overlapping boxes...")

selected_boxes = []
for cluster_id, b in bboxes:
    if all(not b.intersects(existing) for existing in selected_boxes):
        selected_boxes.append(b)

    if len(selected_boxes) >= N_BOXES:
        break

print(f"Selected {len(selected_boxes)} non-overlapping boxes.")

# -----------------------------
# SAVE OUTPUT
# -----------------------------
print("Saving GPKG:", OUTPUT_GPKG)

bbox_gdf = gpd.GeoDataFrame(
    {"id": list(range(len(selected_boxes)))},
    geometry=selected_boxes,
    crs=points.crs
)

# Export in projected CRS *and* WGS84
bbox_gdf.to_file(OUTPUT_GPKG, driver="GPKG")

# Also produce a WGS84 version
bbox_gdf_4326 = bbox_gdf.to_crs(4326)

print("\nBBOX COORDINATES (EPSG:4326, Earth Engine compatible):\n")
for i, geom in enumerate(bbox_gdf_4326.geometry):
    print(f"BBOX {i}: {geom.bounds}")

print("\nDone.")
