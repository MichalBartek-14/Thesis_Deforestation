import rasterio
from rasterio.features import shapes
import geopandas as gpd
import numpy as np
from shapely.geometry import shape

#alternative script to analyse year 2024 - 7.12.2025
#testing out improvements:
#          00) load two rasters of GFC and merge them into one dataset
#           clip to the extent of slovakia)
# ---      a) make a multipart dissolved feature with only the given driver
#          a2) add buffer to the LHE polygons to make GFC also just outside of LHE
#           # polygons be in the output
#          b) if overlay between two drivers larger than 3 pixels dont assign any driver
#          b) Conditions for the driver assigning
#           c) Remove all smaller polygons than
# ---      B)

# ----------------------------------------------------------
# 1. DATA LOADER
# ----------------------------------------------------------
def data_loader(path_forestry, path_GFC):
    LHE_2024 = gpd.read_file(path_forestry)
    GFC_2024 = path_GFC
    print(LHE_2024._metadata)

    gfc_vector = vectorize_gfc(GFC_2024, 24)
    final = overlay(LHE_2024, gfc_vector)
    return final

# ----------------------------------------------------------
# 2. VECTORIZE GFC FOR A GIVEN YEAR
# ----------------------------------------------------------
def vectorize_gfc(GFC, year):
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

    # convert form to gdf so algorithm can make buffer
    #Buffer the forestry polygons
    #buffered_forestry = LHE.buffer(50)

    # Clip GFC polygons by forestry polygons
    clipped = gpd.overlay(gfc_gdf, buffered_forestry, how="intersection")

    # Add driver column (empty now, filled in post_process)
    clipped["driver"] = None

    # Run final classification
    clipped = post_process(clipped)

    #remove small polygons
    if clipped.geometry < 20:
        clipped["driver"] = "small"
        clipped.drop("small")


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

final_gpkg = data_loader(r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\Forestry\LHE_2024_Slovakia_deforestation_events.gpkg",
            r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Data\Labelling\Hansen_GFC-2024-v1.12_lossyear_50N_010E.tif")
#save_output(final_gpkg, "AUTO_Forest_Disturbance_events_2024.gpkg")




