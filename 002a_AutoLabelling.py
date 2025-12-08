import rasterio
from rasterio.features import shapes
import geopandas as gpd
import numpy as np
from shapely.geometry import shape

#working script 28.11.2025
#possible improvements:
# ---      a) add buffer to the LHE polygons (if they are not close to each other) to make GFC also just outside of LHE
# polygons be in the output
# ---      B)

# ----------------------------------------------------------
# 1. DATA LOADER
# ----------------------------------------------------------
def data_loader(path_forestry, path_GFC):
    LHE_2023 = gpd.read_file(path_forestry)
    GFC_2023 = path_GFC

    gfc_vector = vectorize_gfc(LHE_2023, GFC_2023, 23)
    final = overlay(LHE_2023, gfc_vector)
    return final

# ----------------------------------------------------------
# 2. VECTORIZE GFC FOR A GIVEN YEAR
# ----------------------------------------------------------
def vectorize_gfc(LHE, GFC, year):
    """
    Reads raster, selects pixels with value==year,
    converts them to polygons, returns GeoDataFrame.
    """

    with rasterio.open(GFC) as src:
        band = src.read(1)

        # mask only the year of deforestation
        mask = (band == year)

        # polygonize raster regions where mask is True
        results = (
            {'properties': {'year': year}, 'geometry': shape(geom)}
            for geom, val in shapes(band, mask=mask, transform=src.transform)
            if val == year
        )

        gdf = gpd.GeoDataFrame.from_features(results, crs=src.crs)

    return gdf

# ----------------------------------------------------------
# 3. CLIP GFC POLYGONS WITH LHE FORESTRY AREAS
# ----------------------------------------------------------
def overlay(LHE, gfc_gdf):

    # Ensure identical CRS
    LHE = LHE.to_crs("EPSG:4326")
    gfc_gdf = gfc_gdf.to_crs("EPSG:4326")

    # Clip GFC polygons by forestry polygons
    clipped = gpd.overlay(gfc_gdf, LHE, how="intersection")

    # Add driver column (empty now, filled in post_process)
    clipped["driver"] = None

    # Run final classification
    clipped = post_process(clipped)

    return clipped



# ----------------------------------------------------------
# 4. POST-PROCESSING: CLASSIFICATION OF DRIVERS
# ----------------------------------------------------------
def post_process(gdf):
    """
    Assigns attribute 'driver' based on forestry attributes:
        - If "Pricina nahodnej tazby" contains "LS" → driver = "bb"
        - If Druh ťažby == "OU" AND "Pricina nahodnej tazby" is empty → driver = "fm"
        - If "Pricina nahodnej tazby" == "VT" → driver = "wt"
    """

    # clean input strings
    gdf["Príčina náhodnej ťažby"] = gdf["Príčina náhodnej ťažby"].fillna("")
    gdf["Druh ťažby"] = gdf["Druh ťažby"].fillna("")

    # 1. LS → bb
    mask_bb = gdf["Príčina náhodnej ťažby"].str.contains("LS", case=False, na=False)
    gdf.loc[mask_bb, "driver"] = "bb"

    # 2. OU + empty cause → fm
    mask_fm = (gdf["Druh ťažby"] == "OU") & (gdf["Príčina náhodnej ťažby"].str.strip() == "")
    gdf.loc[mask_fm, "driver"] = "fm"

    # 3. VT → wt
    mask_wt = gdf["Príčina náhodnej ťažby"].str.contains("VT", case=False, na=False)
    gdf.loc[mask_wt, "driver"] = "wt"

    return gdf

# ----------------------------------------------------------
# 5. SAVE RESULT
# ----------------------------------------------------------
def save_output(gdf, out_path):
    """
    Saves the final geopackage with driver + original LHE attributes.
    """
    gdf.to_file(out_path, driver="GPKG")

final_gpkg = data_loader(r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\Forestry\LHE_2023_Slovakia_deforestation_events.gpkg",
            r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Data\Labelling\Hansen_GFC-2024-v1.12_lossyear_50N_010E.tif")
save_output(final_gpkg, "AUTO_Forest_Disturbance_events_2023.gpkg")




