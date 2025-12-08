import geopandas as gpd
import rasterio
from rasterio.features import shapes
import numpy as np
from shapely.geometry import shape
import shapely
import warnings
import pandas as pd

""""
description:
This script will load the preprocessed forestry data stored as gpkg. file
in which the driver of the forest disturbance is explicitlly mentioned under attribute "driver".
Then the scripts vecotrizes and overlays the forestry polygons with the (vectoirzed) GFC forest disturbance alerts and assigns
these forest disturbance occurances the explicit driver. 
The conditions under which the drivers are assigned is included in the function postprocess().

specifics of the project:
a) Working with 2 years and thus 2 forestry files ()
"""

#testing out improvements:

# ---      a) make a multipart dissolved feature with only the given driver
#          a2) add buffer to the LHE polygons to make GFC also just outside of LHE
#           # polygons be in the output
#          b) if overlay between two drivers larger than 3 pixels dont assign any driver
#           c) Remove all smaller polygons than 0.5ha
# ------V2-----
# ----------------------------------------------------------
def data_loader(forestry_files: list, gfc_path: str, year: int):
    """
    forestry_files: list of GPKG files (e.g. 2023 + 2024)
    gfc_path: processed GFC raster (already filtered + clipped)
    year: GFC lossyear value to vectorize
    """

    # Load + merge forestry
    LHE = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(f) for f in forestry_files],
        ignore_index=True
    ))
    LHE = LHE.to_crs("EPSG:3857")  # meter-based CRS

    # Fix invalid geometries
    LHE["geometry"] = LHE.buffer(0)

    # Vectorize the GFC raster for the given year
    gfc_vect = vectorize_gfc(gfc_path, year)
    gfc_vect = gfc_vect.to_crs(LHE.crs)

    # Run overlay + classification
    final = overlay_and_process(LHE, gfc_vect)

    return final


# ----------------------------------------------------------
# 2. VECTORIZE GFC FOR A GIVEN YEAR
# ----------------------------------------------------------
def vectorize_gfc(gfc_path, year):
    with rasterio.open(gfc_path) as src:
        band = src.read(1)
        mask = (band == year)

        polygons = [
            {"properties": {"year": year}, "geometry": shape(geom)}
            for geom, val in shapes(band, mask=mask, transform=src.transform)
            if val == year
        ]

    return gpd.GeoDataFrame.from_features(polygons, crs=src.crs)


# ----------------------------------------------------------
# 3. OVERLAY + IMPROVEMENTS + CLASSIFICATION
# ----------------------------------------------------------
def overlay_and_process(LHE, gfc):

    # ---------------------------
    # A) Dissolve forestry by "driver"
    # ---------------------------
    if "driver" not in LHE.columns:
        LHE["driver"] = LHE["Príčina náhodnej ťažby"].fillna("")

    dissolved = LHE.dissolve(by="driver")

    # ---------------------------
    # B) Add buffer (25m default)
    # ---------------------------
    dissolved["geometry"] = dissolved.buffer(25)

    # ---------------------------
    # C) Overlay GFC with forestry
    # ---------------------------
    clipped = gpd.overlay(gfc, dissolved, how="intersection")

    # ---------------------------
    # D) Driver classification logic
    # ---------------------------
    clipped = post_process(clipped)

    # ---------------------------
    # E) Remove polygons < 0.5 ha (5000 m²)
    # ---------------------------
    clipped = clipped[clipped.area >= 5000]

    # ---------------------------
    # F) If intersecting >1 driver for same GFC → remove driver
    # ---------------------------
    clipped = remove_conflicts(clipped)

    return clipped


# ----------------------------------------------------------
# 4. CLASSIFICATION BASED ON FORESTRY ATTRIBUTES
# ----------------------------------------------------------
def post_process(gdf):

    gdf["Príčina náhodnej ťažby"] = gdf["Príčina náhodnej ťažby"].fillna("")
    gdf["Druh ťažby"] = gdf["Druh ťažby"].fillna("")

    # VT → windthrow (wt)
    mask_wt = gdf["Príčina náhodnej ťažby"].str.contains("VT", case=False)
    gdf.loc[mask_wt, "driver"] = "wt"

    # LS → bark beetle (bb)
    mask_bb = gdf["Príčina náhodnej ťažby"].str.contains("LS", case=False)
    gdf.loc[mask_bb, "driver"] = "bb"

    # OU + empty cause → forest management (fm)
    mask_fm = (gdf["Druh ťažby"] == "OU") & (gdf["Príčina náhodnej ťažby"].str.strip() == "")
    gdf.loc[mask_fm, "driver"] = "fm"

    # Others: keep original cause
    other = ~(mask_bb | mask_fm | mask_wt)
    gdf.loc[other, "driver"] = gdf.loc[other, "Príčina náhodnej ťažby"]

    return gdf


# ----------------------------------------------------------
# 5. REMOVE DRIVER ASSIGNMENT IF >1 DRIVER INTERSECTS
# ----------------------------------------------------------
def remove_conflicts(gdf):

    # Count drivers per GFC polygon
    grouped = gdf.groupby("geometry")["driver"].nunique()

    conflicting_geoms = grouped[grouped > 1].index

    gdf.loc[gdf["geometry"].isin(conflicting_geoms), "driver"] = None

    return gdf


# ----------------------------------------------------------
# 6. SAVE RESULT
# ----------------------------------------------------------
def save_output(gdf, out_path):
    gdf.to_file(out_path, driver="GPKG")
    print(f"Saved: {out_path}")


# ----------------------------------------------------------
# 7. RUN
# ----------------------------------------------------------
final_gpkg = data_loader(
    forestry_files=[
        #r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Actual_Scripts/Deforestation_Thesis/Forestry/LHE_2023_Slovakia_deforestation_events.gpkg",
        r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Actual_Scripts/Deforestation_Thesis/Forestry/LHE_2024_Slovakia_deforestation_events.gpkg"
    ],
    gfc_path=r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\outputs\Processed_GFC_001b.tif",
    year=24
)

save_output(final_gpkg, "AUTO_Forest_Disturbance_events_2024.gpkg")


