import rasterio
import numpy as np
from rasterio.merge import merge
from rasterio.mask import mask
import geopandas as gpd
import glob
import os

"""
description:
This script loads the GFC tiles from the directory merges them into one
then it clips it to the mask of the area and filters only the years which the users is interested in.
Outputs: Processed_GFC.tif
"""
GFC_tiffs_dir = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Data/Labelling"
Slovakia_shape = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Data/Labelling/Slovakia_shp/sr_0.shp"

# OUTPUT
OUTPUT_TIF = "C:/Users/misko/Documents/Michal/Master/A_Thesis/Actual_Scripts/Deforestation_Thesis/outputs/Processed_GFC_001b.tif"

# Years of interest (values stored in GFC lossyear band)
years = [22, 23, 24]

def clip_tile_to_shape(tile_path, shapes):
    """Clip a single raster tile to the Slovakia boundary."""
    with rasterio.open(tile_path) as src:
        clipped, transform = mask(src, shapes, crop=True)
        profile = src.profile
        profile.update({
            "height": clipped.shape[1],
            "width": clipped.shape[2],
            "transform": transform
        })
    return clipped, profile


def clip_all_tiles(tiff_folder, shape_path):
    """Clip all tiles and return list of clipped rasters + profiles."""
    tif_files = glob.glob(os.path.join(tiff_folder, "*.tif"))
    if not tif_files:
        raise FileNotFoundError("No GFC tiles found!")

    gdf = gpd.read_file(shape_path)
    gdf = gdf.to_crs("EPSG:4326")
    shapes = gdf.geometry.values

    clipped_rasters = []
    clipped_profiles = []

    for tif in tif_files:
        print(f"Clipping {os.path.basename(tif)} ...")
        clipped, profile = clip_tile_to_shape(tif, shapes)
        clipped_rasters.append(clipped)
        clipped_profiles.append(profile)

    return clipped_rasters, clipped_profiles


def merge_clipped_tiles(clipped_rasters, clipped_profiles):
    """Merge all clipped tiles into one raster."""
    # Need temporary in-memory datasets
    src_files = []

    for data, profile in zip(clipped_rasters, clipped_profiles):
        memfile = rasterio.io.MemoryFile()
        dataset = memfile.open(**profile)
        dataset.write(data)
        src_files.append(dataset)

    merged, transform = merge(src_files)

    # Base profile = first tile’s profile
    base_profile = clipped_profiles[0].copy()
    base_profile.update({
        "height": merged.shape[1],
        "width": merged.shape[2],
        "transform": transform
    })

    # Close memory datasets
    for src in src_files:
        src.close()

    return merged, base_profile


def filter_years(raster_data, years):
    """Keep only pixels whose lossyear matches the selected values."""
    band = raster_data[0]  # lossyear stored in band 1

    mask_years = np.isin(band, years)
    filtered = np.where(mask_years, band, 0)

    return filtered[np.newaxis, :, :]


def save_raster(raster_data, profile, output_path):
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(raster_data)
    print(f"\nSaved: {output_path}")


def main():

    clipped_rasters, clipped_profiles = clip_all_tiles(GFC_tiffs_dir, Slovakia_shape)
    merged, profile = merge_clipped_tiles(clipped_rasters, clipped_profiles)
    filtered = filter_years(merged, years)

    save_raster(filtered, profile, OUTPUT_TIF)


if __name__ == "__main__":
    main()

