import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape
import chardet
import numpy as np
import random
import shapely

# Preprocess the Hansen data and filter out only the forest loss years 2022, 2023 and 2024
# in order to: a) have a smaller dataset to process later on.
#               b) to have less chaotic dataset during the labelling

#get the map of the overlapping 2024 forest loss pixels and 2024 forest parcels with clear driver

Hansen_path_50N_10E = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Data/Labelling/Hansen_GFC-2024-v1.12_lossyear_50N_010E.tif"
        # Evidence of the logging activity for the year
SK_foresty_2024 = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Scripts/Datasets/LHE_2024_Slovakia_defo_events.gpkg"

years = [2022,2023,2024]
with rasterio.open(Hansen_path_50N_10E) as src:
        Hansen_raster_50N_10E = src.read()

mask = np.isin(Hansen_raster_50N_10E, years)

forestry = gpd.read_file(SK_foresty_2024)
print(forestry.head())
# Filtered data (True where pixel matches one of the years)
Filtered_data = Hansen_raster_50N_10E[mask]

with rasterio.open(Hansen_path_50N_10E) as src:
        image = src.read(1)
        results = (
                {'properties': {'raster_val': v}, 'geometry': s}
                for i, (s, v)
                in enumerate(
                shapes(image, mask=mask, transform=src.transform)))

geoms = list(results)
print(geoms[0])




