import rasterio
from rasterio.features import shapes
import geopandas as gpd
import numpy as np
from shapely.geometry import shape

#working script 28.11.2025

"""
This script loads all of the labelled vector features, removes the redundant features with the priority given to the manually labelled data
Output is the merged dataset of the vector files"""
def data_loader():

def overlay():
    #remove the redundant polygons

def save(gpkg,out_path):



#Paths
#The manually labelled
manual_2023_path = r"C:\Users\misko\Documents\Forest Disturbance events 2023.shp"
manual_2024_path = r"C:\Users\misko\Documents\Forest_Disturbance_events.shp"
#Auto labelled patches
auto_2023_path = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\AUTO_Forest_Disturbance_events_2023x.gpkg"
auto_2024_path = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\AUTO_Forest_Disturbance_events_2024x.gpkg"

save(final_gpkg, "Complete_deforestation_23_24.tiff")




