import ee
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from datetime import datetime
import numpy as np

"""
Script to create backscatter signal time series with temperature data
for inspection of freezing effects on Sentinel-1 acquisitions
"""

# Initialize Earth Engine
ee.Initialize(project="testproject-473020")

# Load AOI
#aoi_gdf = gpd.read_file("00b_TemperatureForest.gpkg") small undisturbed forest AOI
aoi_gdf = gpd.read_file("test4_2024_defo_bboxes.gpkg")

if aoi_gdf.crs.to_epsg() != 4326:
    aoi_gdf = aoi_gdf.to_crs(4326)


def gdf_row_to_ee_geometry(row):
    geom = row.geometry
    xmin, ymin, xmax, ymax = geom.bounds
    return ee.Geometry.Rectangle([xmin, ymin, xmax, ymax])


def convert_dec_to_eedate(number):
    '''
    Converts a decimal date number to an ee.Date
    '''
    doy = int(number % 1 * 365) + 1
    year = int(number)
    jul_date_string = str(year) + (str(doy)).zfill(3)
    eedate = ee.Date.parse('YYYYDDD', jul_date_string)
    return eedate


def get_s1_timeseries(aoi, start_date, end_date, orbit="DESCENDING"):
    """
    Extract Sentinel-1 backscatter time series for an AOI
    """
    start_date = convert_dec_to_eedate(start_date)
    end_date = convert_dec_to_eedate(end_date)

    s1 = (
        ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT')
        .filterBounds(aoi)
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
        .filter(ee.Filter.eq('orbitProperties_pass', orbit))
        .filterDate(start_date, end_date)
        .sort('system:time_start')
    )

    def extract_values(img):
        # Calculate mean backscatter over AOI
        stats = img.select(['VV', 'VH']).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10,
            bestEffort=True
        )

        # Convert to dB
        vv_linear = ee.Number(stats.get('VV'))
        vh_linear = ee.Number(stats.get('VH'))

        vv_db = ee.Number(10).multiply(vv_linear.log10())
        vh_db = ee.Number(10).multiply(vh_linear.log10())

        return ee.Feature(None, {
            'date': img.date().format('YYYY-MM-dd'),
            'timestamp': img.date().millis(),
            'VV_dB': vv_db,
            'VH_dB': vh_db,
            'orbit': img.get('orbitProperties_pass')
        })

    features = s1.map(extract_values)
    return features


def get_temperature_timeseries(aoi, start_date, end_date):
    """
    Extract ERA5 temperature time series for an AOI
    """
    start_date = convert_dec_to_eedate(start_date)
    end_date = convert_dec_to_eedate(end_date)

    era5 = (
        ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .select("temperature_2m")
        .sort('system:time_start')
    )

    def extract_temp(img):
        # Convert from Kelvin to Celsius
        temp_c = img.subtract(273.15)

        # Calculate mean temperature over AOI
        mean_temp = temp_c.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=1000,
            bestEffort=True
        ).get('temperature_2m')

        return ee.Feature(None, {
            'date': img.date().format('YYYY-MM-dd'),
            'timestamp': img.date().millis(),
            'temp_mean_C': mean_temp
        })

    features = era5.map(extract_temp)
    return features


def features_to_dataframe(features):
    """
    Convert EE FeatureCollection to pandas DataFrame
    """
    data = features.getInfo()
    records = [feat['properties'] for feat in data['features']]
    df = pd.DataFrame(records)

    if len(df) > 0:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

    return df


# Temporal configuration
QUARTERS = {
    "Q1": (0.00, 0.25),
    "Q2": (0.25, 0.50),
    "Q3": (0.50, 0.75),
    "Q4": (0.75, 1.00),
}

TEMPORAL_SETTINGS = {
    "quarter_only": {
        "offset_start": 0.00,
        "offset_end": 0.00
    },
    "quarter_plus_3m": {
        "offset_start": -3 / 12,
        "offset_end": 0.00
    }
}


def get_temporal_window(year, quarter, setting):
    q_start, q_end = QUARTERS[quarter]
    cfg = TEMPORAL_SETTINGS[setting]

    start_date = year + q_start + cfg["offset_start"]
    end_date = year + q_end + cfg["offset_end"]

    return start_date, end_date


def plot_timeseries(s1_df, temp_df, aoi_id, year, quarter, setting, output_dir="timeseries_plots"):
    """
    Create a dual-axis plot showing backscatter and temperature time series
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(14, 6))

    # Plot backscatter on primary y-axis
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Backscatter (dB)', color='tab:blue', fontsize=12)

    if len(s1_df) > 0:
        ax1.plot(s1_df['date'], s1_df['VV_dB'], 'o-',
                 color='darkblue', label='VV', markersize=6, linewidth=1.5)
        ax1.plot(s1_df['date'], s1_df['VH_dB'], 's-',
                 color='royalblue', label='VH', markersize=6, linewidth=1.5)

    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left')

    # Plot temperature on secondary y-axis
    ax2 = ax1.twinx()
    ax2.set_ylabel('Temperature (°C)', color='tab:red', fontsize=12)

    if len(temp_df) > 0:
        ax2.plot(temp_df['date'], temp_df['temp_mean_C'],
                 color='red', linewidth=2, alpha=0.7, label='Mean Temp')
        ax2.axhline(y=0, color='darkred', linestyle='--',
                    linewidth=2, label='Freezing Point', alpha=0.8)

        # Highlight freezing days
        freezing_days = temp_df[temp_df['temp_mean_C'] < 0]
        if len(freezing_days) > 0:
            ax2.scatter(freezing_days['date'], freezing_days['temp_mean_C'],
                        color='darkred', s=100, marker='x',
                        linewidth=3, label='Freezing Days', zorder=5)

    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.legend(loc='upper right')

    # Title and formatting
    plt.title(f'S1 Backscatter & Temperature Time Series\n'
              f'AOI {aoi_id} | {year} {quarter} | {setting}',
              fontsize=14, fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save plot
    filename = f'timeseries_AOI{aoi_id}_{year}_{quarter}_{setting}.png'
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Saved plot: {filepath}")


def create_summary_stats(s1_df, temp_df, aoi_id, year, quarter, setting):
    """
    Create summary statistics for the time series
    """
    summary = {
        'aoi_id': aoi_id,
        'year': year,
        'quarter': quarter,
        'setting': setting,
        's1_acquisitions': len(s1_df),
        'freezing_days': len(temp_df[temp_df['temp_mean_C'] < 0]) if len(temp_df) > 0 else 0,
        'temp_min_C': temp_df['temp_mean_C'].min() if len(temp_df) > 0 else np.nan,
        'temp_mean_C': temp_df['temp_mean_C'].mean() if len(temp_df) > 0 else np.nan,
        'temp_max_C': temp_df['temp_mean_C'].max() if len(temp_df) > 0 else np.nan,
        'vv_mean_dB': s1_df['VV_dB'].mean() if len(s1_df) > 0 else np.nan,
        'vh_mean_dB': s1_df['VH_dB'].mean() if len(s1_df) > 0 else np.nan,
    }

    # Count S1 acquisitions during freezing
    if len(s1_df) > 0 and len(temp_df) > 0:
        # Merge on date to find S1 acquisitions on freezing days
        merged = pd.merge(s1_df, temp_df, on='date', how='left')
        s1_on_freezing = len(merged[merged['temp_mean_C'] < 0])
        summary['s1_on_freezing_days'] = s1_on_freezing
    else:
        summary['s1_on_freezing_days'] = 0

    return summary


######################## MAIN ANALYSIS ########################

# Configuration
YEARS = [2023, 2024, 2025]
QUARTER_NAMES = ["Q1", "Q2", "Q3", "Q4"]
SETTING_NAMES = ["quarter_only", "quarter_plus_3m"]

# Select AOIs to analyze (set to None to analyze all)
AOI_INDICES = [1]  # Change to None for all AOIs, or list specific indices

# Get AOI list
if AOI_INDICES is None:
    aoi_indices = range(len(aoi_gdf))
else:
    aoi_indices = AOI_INDICES

summary_stats = []

for aoi_idx in aoi_indices:
    row = aoi_gdf.iloc[aoi_idx]
    aoi = gdf_row_to_ee_geometry(row)
    aoi_id = aoi_idx

    print(f"\n{'=' * 60}")
    print(f"Processing AOI {aoi_id}")
    print(f"{'=' * 60}")

    for year in YEARS:
        for quarter in QUARTER_NAMES:
            for setting in SETTING_NAMES:
                start_date, end_date = get_temporal_window(year, quarter, setting)

                print(f"\n{year} {quarter} | {setting} ({start_date:.3f} → {end_date:.3f})")

                # Get S1 time series
                s1_features = get_s1_timeseries(aoi, start_date, end_date)
                s1_df = features_to_dataframe(s1_features)

                # Get temperature time series
                temp_features = get_temperature_timeseries(aoi, start_date, end_date)
                temp_df = features_to_dataframe(temp_features)

                print(f"  S1 acquisitions: {len(s1_df)}")
                print(f"  Temperature records: {len(temp_df)}")

                if len(temp_df) > 0:
                    freezing_days = len(temp_df[temp_df['temp_mean_C'] < 0])
                    print(f"  Freezing days (< 0°C): {freezing_days}")
                    print(f"  Temp range: {temp_df['temp_mean_C'].min():.1f}°C to {temp_df['temp_mean_C'].max():.1f}°C")

                # Create plot
                plot_timeseries(s1_df, temp_df, aoi_id, year, quarter, setting)

                # Save summary stats
                stats = create_summary_stats(s1_df, temp_df, aoi_id, year, quarter, setting)
                summary_stats.append(stats)

                # Save detailed data to CSV
                if len(s1_df) > 0 or len(temp_df) > 0:
                    output_csv_dir = "timeseries_data"
                    import os

                    os.makedirs(output_csv_dir, exist_ok=True)

                    # Merge S1 and temperature data
                    if len(s1_df) > 0 and len(temp_df) > 0:
                        merged_df = pd.merge(s1_df, temp_df, on='date', how='outer')
                    elif len(s1_df) > 0:
                        merged_df = s1_df
                    else:
                        merged_df = temp_df

                    csv_filename = f'timeseries_AOI{aoi_id}_{year}_{quarter}_{setting}.csv'
                    csv_filepath = os.path.join(output_csv_dir, csv_filename)
                    merged_df.to_csv(csv_filepath, index=False)
                    print(f"  Saved data: {csv_filepath}")

# Save summary statistics
summary_df = pd.DataFrame(summary_stats)
#summary_df.to_csv('timeseries_summary_stats.csv', index=False)
print(f"\n{'=' * 60}")
print(f"Summary statistics saved to: timeseries_summary_stats.csv")
print(f"{'=' * 60}")

# Print overall summary
print("\nOverall Summary:")
print(f"Total time periods analyzed: {len(summary_df)}")
print(f"Total S1 acquisitions: {summary_df['s1_acquisitions'].sum()}")
print(f"Total freezing days: {summary_df['freezing_days'].sum()}")
print(f"S1 acquisitions on freezing days: {summary_df['s1_on_freezing_days'].sum()}")

print("\n=== Analysis complete ===")