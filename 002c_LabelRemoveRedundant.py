import geopandas as gpd
import pandas as pd
import os

"""
This script loads all of the labelled forest disturbance vector features, removes the redundant features 
with the priority given to the manually labelled data.
Output is the merged dataset of the vector files per year.
"""


def data_loader(manual_path, auto_path):
    """Load and validate manual and auto-labelled datasets."""
    print(f"\nLoading manual labels: {os.path.basename(manual_path)}")
    manual_gdf = gpd.read_file(manual_path)

    print(f"Loading auto labels: {os.path.basename(auto_path)}")
    auto_gdf = gpd.read_file(auto_path)

    # Fix invalid geometries using buffer(0) - standard GIS technique
    print("Validating and fixing geometries...")
    manual_invalid = ~manual_gdf.geometry.is_valid
    auto_invalid = ~auto_gdf.geometry.is_valid

    if manual_invalid.any():
        print(f"  Fixing {manual_invalid.sum()} invalid manual geometries")
        manual_gdf.loc[manual_invalid, 'geometry'] = manual_gdf.loc[manual_invalid, 'geometry'].buffer(0)

    if auto_invalid.any():
        print(f"  Fixing {auto_invalid.sum()} invalid auto geometries")
        auto_gdf.loc[auto_invalid, 'geometry'] = auto_gdf.loc[auto_invalid, 'geometry'].buffer(0)

    # Ensure same CRS
    if manual_gdf.crs != auto_gdf.crs:
        print(f"Reprojecting auto labels to match manual CRS")
        auto_gdf = auto_gdf.to_crs(manual_gdf.crs)

    print(f"  Manual: {len(manual_gdf)} features")
    print(f"  Auto: {len(auto_gdf)} features")

    return manual_gdf, auto_gdf


def overlay(manual_gdf, auto_gdf):
    """Remove redundant auto polygons that overlap with manual labels."""
    print("\nRemoving redundant auto-labelled features...")

    # Create spatial index for efficient searching
    manual_sindex = manual_gdf.sindex

    keep_indices = []
    removed_count = 0
    error_count = 0

    for idx, auto_feat in auto_gdf.iterrows():
        try:
            # Skip empty/invalid geometries
            if auto_feat.geometry is None or auto_feat.geometry.is_empty:
                continue

            # Ensure valid geometry
            if not auto_feat.geometry.is_valid:
                auto_feat.geometry = auto_feat.geometry.buffer(0)

            # Find potential overlaps using spatial index
            possible_matches_idx = list(manual_sindex.intersection(auto_feat.geometry.bounds))
            possible_matches = manual_gdf.iloc[possible_matches_idx]

            has_overlap = False
            for _, manual_feat in possible_matches.iterrows():
                try:
                    # Skip invalid manual geometries
                    if manual_feat.geometry is None or manual_feat.geometry.is_empty:
                        continue

                    manual_geom = manual_feat.geometry
                    if not manual_geom.is_valid:
                        manual_geom = manual_geom.buffer(0)

                    # Check for intersection
                    if auto_feat.geometry.intersects(manual_geom):
                        intersection = auto_feat.geometry.intersection(manual_geom)

                        if intersection.is_empty or intersection.area == 0:
                            continue

                        # Calculate overlap ratio
                        overlap_ratio = intersection.area / auto_feat.geometry.area

                        # Remove if >10% overlap
                        if overlap_ratio > 0.1:
                            has_overlap = True
                            removed_count += 1
                            break

                except Exception as e:
                    error_count += 1
                    continue

            if not has_overlap:
                keep_indices.append(idx)

        except Exception as e:
            error_count += 1
            # Keep feature if error occurred
            keep_indices.append(idx)

    # Filter auto features
    auto_filtered = auto_gdf.loc[keep_indices].copy()

    # Merge manual and filtered auto datasets
    merged_gdf = gpd.GeoDataFrame(
        pd.concat([manual_gdf, auto_filtered], ignore_index=True),
        crs=manual_gdf.crs
    )

    print(f"  Removed: {removed_count} overlapping features")
    print(f"  Kept: {len(auto_filtered)} unique auto features")
    if error_count > 0:
        print(f"  Geometry errors handled: {error_count}")
    print(f"  Total merged: {len(merged_gdf)} features")

    return merged_gdf


def save(gpkg, out_path):
    """Save the merged GeoDataFrame to a GeoPackage file."""
    # Ensure .gpkg extension
    if not out_path.endswith('.gpkg'):
        out_path = out_path.replace('.tiff', '.gpkg').replace('.tif', '.gpkg')
        if not out_path.endswith('.gpkg'):
            out_path += '.gpkg'

    print(f"\nSaving to: {out_path}")
    gpkg.to_file(out_path, driver="GPKG")
    print(f"✓ Saved successfully: {len(gpkg)} features")


# ============================
# PATHS
# ============================
# Manually labelled
manual_2023_path = r"C:\Users\misko\Documents\Forest Disturbance events 2023.shp"
manual_2024_path = r"C:\Users\misko\Documents\Forest_Disturbance_events.shp"

# Auto labelled patches
auto_2023_path = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\AUTO_Forest_Disturbance_events_2023x.gpkg"
auto_2024_path = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\AUTO_Forest_Disturbance_events_2024x.gpkg"

# Output paths
output_2023 = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\Complete_deforestation_drivers_2023.gpkg"
output_2024 = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\Deforestation_Thesis\Complete_deforestation_drivers_2024.gpkg"

# ============================
# MAIN EXECUTION
# ============================
if __name__ == "__main__":
    print("=" * 60)
    print("FOREST DISTURBANCE LABEL MERGE")
    print("=" * 60)

    # Process 2023
    print("\n" + "=" * 60)
    print("PROCESSING 2023 DATA")
    print("=" * 60)

    if os.path.exists(manual_2023_path) and os.path.exists(auto_2023_path):
        manual_2023, auto_2023 = data_loader(manual_2023_path, auto_2023_path)
        final_2023 = overlay(manual_2023, auto_2023)
        save(final_2023, output_2023)
    else:
        print("⚠ Skipping 2023 - input files not found")
        if not os.path.exists(manual_2023_path):
            print(f"  Missing: {manual_2023_path}")
        if not os.path.exists(auto_2023_path):
            print(f"  Missing: {auto_2023_path}")

    # Process 2024
    print("\n" + "=" * 60)
    print("PROCESSING 2024 DATA")
    print("=" * 60)

    if os.path.exists(manual_2024_path) and os.path.exists(auto_2024_path):
        manual_2024, auto_2024 = data_loader(manual_2024_path, auto_2024_path)
        final_2024 = overlay(manual_2024, auto_2024)
        #the column naming had to be adjusted for year 2024 since it includes 2 columns of the same name.
        final_2024 = final_2024.rename(columns={"year": "year_lower"})
        save(final_2024, output_2024)
    else:
        print("Skipping 2024 - input files not found")
        if not os.path.exists(manual_2024_path):
            print(f"  Missing: {manual_2024_path}")
        if not os.path.exists(auto_2024_path):
            print(f"  Missing: {auto_2024_path}")
    print(final_2024.columns)
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print("\nOutput files:")
    if os.path.exists(output_2023):
        print(f"  ✓ {output_2023}")
    if os.path.exists(output_2024):
        print(f"  ✓ {output_2024}")
    print("=" * 60)