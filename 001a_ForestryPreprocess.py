import geopandas as gpd
import pandas as pd
import rasterio
import chardet

#read data, find out which years for different disturbances there are
# Administrative forest boundaries shp
forest_boundaries_path = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Data/JPRL_2024(shp)/JPRL_2024.dbf"
# Evidence of the logging activity for the year
year = 2024
logging_table_path = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/data/slovakia/forestry/LHE_taz2024.xlsx"
with open(logging_table_path, 'rb') as f:
    result = chardet.detect(f.read(500000))
    print("Detected encoding:", result)

# --- 1. Read files ---
usecols_gdf = ['KPL', 'DC', 'CP', 'PS', 'PC', 'Plocha', 'geometry']
if year == 2024:
    usecols_df = [
        'Evidenčný rok LHE', 'Kód plánu', 'Rok začiatku platnosti plánu',
        'Dielec', 'Čiastková plocha', 'Porastová skupina', 'Kód plánu',
        'Druh ťažby', 'Hospodársky spôsob a forma', 'Príčina náhodnej ťažby',
        'Prebierková plocha (ha)', 'Príčina vzniku',
        'Plocha na obnovu celkom (ha)', 'Výmera holiny (ha)', 'Drevina', 'Ťažba (m3)'
    ]
else:
    usecols_df = [
        'Evidenčný rok LHE', 'Kód plánu', 'Rok začiatku platnosti plánu',
        'Dielec', 'Čiastková plocha', 'Porastová skupina', 'Kód plánu',
        'Druh ťažby', 'Hospodársky spôsob a forma', 'Príčina náhodnej ťažby',
        'Prebierková plocha (ha)', 'Príčina vzniku holiny',
        'Výmera holiny (ha)', 'Drevina', 'ťažba (m3)'
    ]


# Read spatial and tabular data
forest_boundaries_gdf = gpd.read_file(forest_boundaries_path)[usecols_gdf]
logging_df = pd.read_excel(logging_table_path, usecols=usecols_df)

#To do:
# 1 retrieve only deforestation events with some value above 0.5ha for 'holina
# 2 Keep only desired data columns
# 3 Join this table information to the spatially explicit forest_boundaries_path
    # Join based on KPL in shapefile - 'Kod PLanu in excel\
    # based on DC in shp and Dielec in excel
    # based on and CP or Ciastkova plocha in excel
# 4 output should be a shapefile where one patch up to the division of CP should get the records of the excel

# --- 2
filtered_logging = logging_df[logging_df["Výmera holiny (ha)"]>0.5]
print(filtered_logging.shape[0])
# --- 3 Renaming, Aggregating excel and dissolving shapefile
forest_boundaries_gdf.columns = forest_boundaries_gdf.columns.str.strip()
filtered_logging.columns = filtered_logging.columns.str.strip()

filtered_logging = filtered_logging.rename(columns={
    "Kód plánu":"KPL",
    "Dielec":"DC",
    "Čiastková plocha":"CP"
})
## --- Aggregate (group by KPL, DC, CP) ---
if year == 2024:
    print("Taking columns for the year 2024")
    aggregated_logging = (
        filtered_logging
        .groupby(["KPL", "DC", "CP"], dropna=False)
        .agg({
            "Výmera holiny (ha)": "sum",
            "Ťažba (m3)": "sum",
            "Plocha na obnovu celkom (ha)": "sum",
            "Prebierková plocha (ha)": "sum",
            "Evidenčný rok LHE": "first",
            "Druh ťažby": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Príčina vzniku": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Drevina": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Hospodársky spôsob a forma": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Príčina náhodnej ťažby": lambda x: ', '.join(sorted(set(x.dropna()))),
        })
        .reset_index()
    )
elif year == 2023:
    print("Taking columns for the year 2023")
    aggregated_logging = (
        filtered_logging
        .groupby(["KPL", "DC", "CP"], dropna=False)
        .agg({
            "Výmera holiny (ha)": "sum",
            "ťažba (m3)": "sum",
            "Prebierková plocha (ha)": "sum",
            "Evidenčný rok LHE": "first",
            "Druh ťažby": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Príčina vzniku holiny": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Drevina": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Hospodársky spôsob a forma": lambda x: ', '.join(sorted(set(x.dropna()))),
            "Príčina náhodnej ťažby": lambda x: ', '.join(sorted(set(x.dropna()))),
        })
        .reset_index()
    )


print(f"Aggregated logging records: {aggregated_logging.shape[0]}")
# Replace NaN CP to group by KPL, DC when CP is missing
forest_boundaries_gdf["CP"] = forest_boundaries_gdf["CP"].fillna("NO_CP").astype(str)

#Dissolve (aggregate geometries) on KPL, DC, CP
dissolved_gdf = (
    forest_boundaries_gdf
    .dissolve(by=["KPL", "DC", "CP"], as_index=False, aggfunc="first")
)
print(f"Dissolved shapefile now has unique keys: {dissolved_gdf.shape[0]} features")
# --- 4
merged_gdf = forest_boundaries_gdf.merge(
    aggregated_logging,
    on=["KPL","DC","CP"],
    how="right",
    validate="m:1"
)
print(f"Joined shp. now has {merged_gdf.shape[0]} records.")
merged_gdf = gpd.GeoDataFrame(merged_gdf, geometry='geometry', crs=forest_boundaries_gdf.crs)

# --- 5. Optional: filter only geometries that received matching Excel data ---
merged_gdf_matched = merged_gdf[merged_gdf["Výmera holiny (ha)"].notna()].copy()
print(f"Features with matching logging records: {merged_gdf_matched.shape[0]}")

# --- 6. Save results ---
output_path = f"Forestry/LHE_{year}_Slovakia_deforestation_events.gpkg"
merged_gdf_matched.to_file(output_path, driver="GPKG")
print(f"Saved merged gpkg: {output_path}")