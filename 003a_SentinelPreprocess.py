import ee
import geemap
import math
import geopandas as gpd

"""
description: 
last modified: 6.2.2026
* used for the additional AOIs drawn to offer more generalisation power 
9.3.2026 -changes:
- AOI_id changed += 10 
- input path for the AOI extent
function that loads the date to ee format
production of the sentinel 1 and sentinel 2 composites 
This is done from the EE environment images and saves composites to drive
Modified to:
- Use monthly composites instead of quarterly
- Keep only S2 bands B12, B8, B4, B3
- Extend freeze buffer to 3 days after freezing
- Organize exports by AOI subfolder


"""

# aoi_gdf = gpd.read_file("test4_2024_defo_bboxes.gpkg")
#aoi_gdf = gpd.read_file("00b_manual2024_defo_AOIs.gpkg")
aoi_gdf = gpd.read_file("00c_manual2024_added.gpkg")

if aoi_gdf.crs.to_epsg() != 4326:
    aoi_gdf = aoi_gdf.to_crs(4326)

ee.Initialize(project="testproject-473020")


def gdf_row_to_ee_geometry(row):
    geom = row.geometry
    xmin, ymin, xmax, ymax = geom.bounds
    return ee.Geometry.Rectangle([xmin, ymin, xmax, ymax])


ee_aois = []

for idx, row in aoi_gdf.iterrows():
    ee_geom = gdf_row_to_ee_geometry(row)
    ee_aois.append({
        "id": idx,
        "geometry": ee_geom
    })


def convert_dec_to_eedate(number):
    '''
    Converts an decimal date number to an ee.Date
    '''
    doy = int(number % 1 * 365) + 1
    year = int(number)

    # Create the datestring and fill small doy numbers with preceding 0s
    jul_date_string = str(year) + (str(doy)).zfill(3)

    # Make the ee.Date
    eedate = ee.Date.parse('YYYYDDD', jul_date_string)

    return eedate


# S1 composite (where we consider both ascending and descending)
def produce_s1_composite(
        aoi,
        start_date,
        end_date,
        orbit="DESCENDING",
        mask_freezing=True,
        freeze_threshold=-1.0,
        freeze_buffer_days=3
):
    # Convert decimal dates to ee.Date
    start_date = convert_dec_to_eedate(start_date)
    end_date = convert_dec_to_eedate(end_date)

    # -----------------------------
    # ERA5 freezing-day utilities
    # -----------------------------

    def get_freezing_days(aoi, start_date, end_date, threshold=0.0):
        """
        The function creates flags for the acquisition days when
        there was freezing temperatures over AOI.
        Freezing temperatures create a reduced backscatter compared to
        the above zero temperatures which might create untrue biased
        results and lead to false loss of backscatter information in the data
        """
        era5 = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .select("temperature_2m")
        )

        def flag_freeze(img):
            # Convert from Kelvin to Celsius
            temp_c = img.subtract(273.15)

            # Calculate mean temperature over AOI
            mean_temp = (
                temp_c
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=1000,
                    bestEffort=True
                )
                .values()
                .get(0)
            )

            # Flag as freeze day if mean temperature is below threshold
            freeze = ee.Number(mean_temp).lt(threshold)

            return img.set({
                "freeze_day": freeze,
                "system:time_start": img.get("system:time_start")
            })

        return era5.map(flag_freeze)

    def tag_s1_with_freeze_flag(s1_collection, freezing_days, buffer_days=3):
        """
        Tag S1 images with freeze flag, including buffer days after freezing
        """

        def tag_image(img):
            img_date = ee.Date(img.get("system:time_start"))

            # Check if this date OR the previous buffer_days had freezing temperatures
            freeze_flag = ee.Number(0)

            for day_offset in range(buffer_days + 1):
                check_date = img_date.advance(-day_offset, "day")
                freeze_match = freezing_days.filterDate(
                    check_date,
                    check_date.advance(1, "day")
                ).first()

                # If any day in the buffer period had freezing, flag this image
                day_freeze = ee.Algorithms.If(
                    freeze_match,
                    freeze_match.get("freeze_day"),
                    0
                )

                freeze_flag = ee.Algorithms.If(
                    ee.Number(day_freeze).eq(1),
                    1,
                    freeze_flag
                )

            return img.set("freeze_day", freeze_flag)

        return s1_collection.map(tag_image)

    # -----------------------------
    # Build Sentinel-1 collection
    # -----------------------------

    s1 = (
        ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT')
        .filterBounds(aoi)
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
        .filter(ee.Filter.eq('orbitProperties_pass', orbit))
        .filterDate(start_date, end_date)
    )

    # -----------------------------
    # Apply freezing mask with buffer
    # -----------------------------

    if mask_freezing:
        # Extend the period to check for freezing to include buffer days before
        extended_start = start_date.advance(-freeze_buffer_days, "day")

        freezing_days = get_freezing_days(
            aoi,
            extended_start,
            end_date,
            freeze_threshold
        )

        s1 = tag_s1_with_freeze_flag(s1, freezing_days, freeze_buffer_days)

        # Remove frozen acquisitions and those within buffer period after freezing
        s1 = s1.filter(ee.Filter.eq("freeze_day", 0))

        print(
            "Kept S1 dates after freeze filtering (with 3-day buffer):",
            s1.aggregate_array("system:time_start").getInfo()
        )

    # -----------------------------
    # Composite
    # -----------------------------

    def process_collection(col):
        col = col.map(s1_mask_edges)
        col = slope_correction(col)
        col = col.map(lin_to_db)
        return col.select(['VV', 'VH']).mean()

    s1_composite = ee.Algorithms.If(
        s1.size().gt(0),
        process_collection(s1),
        ee.Image.constant([-100, -100]).rename(['VV', 'VH'])
    )

    s1_composite = ee.Image(s1_composite).unmask(-100)

    s1_composite = s1_composite.where(
        s1_composite.select('VV').eq(-100), 0
    )

    # Scale and cast to int16
    s1_composite = s1_composite.multiply(1000).toInt16()

    return s1_composite.clip(aoi)


def produce_s2_composite(aoi, start_date, end_date):
    # MODIFIED: Only keep B12, B8, B4, B3
    S2_BANDS = ['B3', 'B4', 'B8', 'B12']
    cloud_probability = 0.60
    cloud_band = 'cs'

    start_date = convert_dec_to_eedate(start_date)
    end_date = convert_dec_to_eedate(end_date)

    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 95)) \
        .filterDate(end_date.advance(-6, 'month'), end_date) \
        .filterBounds(aoi)

    cloudscore = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')

    s2 = s2.linkCollection(cloudscore, [cloud_band]) \
        .map(lambda img: img.updateMask(img.select(cloud_band).gte(cloud_probability)))

    # Sort by most recent first
    s2_sorted = s2.sort('system:time_start', False)

    # Backfill composite
    s2_composite = s2_sorted.select(S2_BANDS).mosaic()

    # Recent period composite
    s2_lastperiod = s2_sorted.filterDate(start_date, end_date).select(S2_BANDS).median()

    s2_composite = s2_composite.blend(s2_lastperiod)

    return s2_composite


# Masking S1 edges (Work from Andreas, Daniel and Bart) #https://code.earthengine.google.com/ccdb1f10b5f9afddbe5453a234c99c57
def s1_mask_edges(image):
    angle = image.select('angle')
    return image \
        .updateMask( \
        createSceneStartEndMask(image, 500) \
            .And(angle.gt(30.63993).And(angle.lt(45.23993))) \
        )


def createSceneStartEndMask(image, bufferMeters):
    geometry = image.geometry()
    coordinates = ee.Array(ee.List(geometry.coordinates().get(0)))
    size = coordinates.length().get([0])
    Max = coordinates.reduce(ee.Reducer.max(), [0])
    Min = coordinates.reduce(ee.Reducer.min(), [0])
    xMax = ee.Geometry.Point(coordinates.mask( \
        Max.slice(1, 0, 1).repeat(0, size).eq(coordinates.slice(1, 0, 1)) \
        ).slice(0, 0, 1).project([1]).toList())
    xMin = ee.Geometry.Point(coordinates.mask( \
        Min.slice(1, 0, 1).repeat(0, size).eq(coordinates.slice(1, 0, 1)) \
        ).slice(0, 0, 1).project([1]).toList())
    yMax = ee.Geometry.Point(coordinates.mask( \
        Max.slice(1, 1).repeat(0, size).eq(coordinates.slice(1, 1)) \
        ).slice(0, 0, 1).project([1]).toList())
    yMin = ee.Geometry.Point(coordinates.mask( \
        Min.slice(1, 1).repeat(0, size).eq(coordinates.slice(1, 1)) \
        ).slice(0, 0, 1).project([1]).toList())
    totalSlices = image.getNumber('totalSlices')
    features = ee.FeatureCollection([ \
        ee.Feature(ee.Feature(ee.Geometry.LineString([xMax, yMax]), {'sliceNumber': 1, 'orbit': 'DESCENDING'})), \
        ee.Feature(
            ee.Feature(ee.Geometry.LineString([xMin, yMin]), {'sliceNumber': totalSlices, 'orbit': 'DESCENDING'})), \
        ee.Feature(ee.Feature(ee.Geometry.LineString([xMax, yMin]), {'sliceNumber': 1, 'orbit': 'ASCENDING'})), \
        ee.Feature(
            ee.Feature(ee.Geometry.LineString([xMin, yMax]), {'sliceNumber': totalSlices, 'orbit': 'ASCENDING'})), \
        ]) \
        .filter(ee.Filter.And( \
        ee.Filter.eq('sliceNumber', image.getNumber('sliceNumber')), \
        ee.Filter.eq('orbit', image.getString('orbitProperties_pass')) \
        ))
    buffered = features.geometry().buffer(20000)
    coords = ee.List(geometry.coordinates().get(0))
    segments = ee.FeatureCollection(coords.zip(coords.slice(1).cat(coords.slice(0, 1))) \
                                    .map(lambda segment: ee.Feature(ee.Geometry.LineString(ee.List(segment))))
                                    )
    # Select segments on the footprint contained within buffered
    filteredSegments = segments.filter(ee.Filter.isContained('.geo', buffered))

    return filteredSegments.distance(bufferMeters).Not().unmask(1)


def slope_correction(collection,
                     TERRAIN_FLATTENING_MODEL='VOLUME',
                     DEM=ee.Image('USGS/SRTMGL1_003'),
                     TERRAIN_FLATTENING_ADDITIONAL_LAYOVER_SHADOW_BUFFER=0):
    """
    Parameters
    ----------
    collection : ee image collection
        DESCRIPTION.
    TERRAIN_FLATTENING_MODEL : string
        The radiometric terrain normalization model, either volume or direct
    DEM : ee asset
        The DEM to be used
    TERRAIN_FLATTENING_ADDITIONAL_LAYOVER_SHADOW_BUFFER : integer
        The additional buffer to account for the passive layover and shadow
    Returns
    -------
    ee image collection
        An image collection where radiometric terrain normalization is
        implemented on each image
    """

    ninetyRad = ee.Image.constant(90).multiply(math.pi / 180)

    def _volumetric_model_SCF(theta_iRad, alpha_rRad):
        """
        Parameters
        ----------
        theta_iRad : ee.Image
            The scene incidence angle
        alpha_rRad : ee.Image
            Slope steepness in range
        Returns
        -------
        ee.Image
            Applies the volume model in the radiometric terrain normalization
        """

        # Volume model
        nominator = (ninetyRad.subtract(theta_iRad).add(alpha_rRad)).tan()
        denominator = (ninetyRad.subtract(theta_iRad)).tan()
        return nominator.divide(denominator)

    def _direct_model_SCF(theta_iRad, alpha_rRad, alpha_azRad):
        """
        Parameters
        ----------
        theta_iRad : ee.Image
            The scene incidence angle
        alpha_rRad : ee.Image
            Slope steepness in range
        Returns
        -------
        ee.Image
            Applies the direct model in the radiometric terrain normalization
        """
        # Surface model
        nominator = (ninetyRad.subtract(theta_iRad)).cos()
        denominator = alpha_azRad.cos().multiply((ninetyRad.subtract(theta_iRad).add(alpha_rRad)).cos())
        return nominator.divide(denominator)

    def _erode(image, distance):
        """

        Parameters
        ----------
        image : ee.Image
            Image to apply the erode function to
        distance : integer
            The distance to apply the buffer
        Returns
        -------
        ee.Image
            An image that is masked to conpensate for passive layover
            and shadow depending on the given distance
        """
        # buffer function (thanks Noel)

        d = (image.Not().unmask(1).fastDistanceTransform(30).sqrt()
             .multiply(ee.Image.pixelArea().sqrt()))

        return image.updateMask(d.gt(distance))

    def _masking(alpha_rRad, theta_iRad, buffer):
        """
        Parameters
        ----------
        alpha_rRad : ee.Image
            Slope steepness in range
        theta_iRad : ee.Image
            The scene incidence angle
        buffer : TYPE
            DESCRIPTION.
        Returns
        -------
        ee.Image
            An image that is masked to conpensate for passive layover
            and shadow depending on the given distance
        """
        # calculate masks
        # layover, where slope > radar viewing angle
        layover = alpha_rRad.lt(theta_iRad).rename('layover')
        # shadow
        shadow = alpha_rRad.gt(ee.Image.constant(-1)
                               .multiply(ninetyRad.subtract(theta_iRad))).rename('shadow')
        # combine layover and shadow
        mask = layover.And(shadow)
        # add buffer to final mask
        if (buffer > 0):
            mask = _erode(mask, buffer)
        return mask.rename('no_data_mask')

    def _correct(image):
        """

        Parameters
        ----------
        image : ee.Image
            Image to apply the radiometric terrain normalization to
        Returns
        -------
        ee.Image
            Radiometrically terrain corrected image
        """

        bandNames = image.bandNames()

        geom = image.geometry()
        proj = image.select(1).projection()

        elevation = DEM.resample('bilinear').reproject(proj, None, 10).clip(geom)

        # calculate the look direction
        heading = ee.Terrain.aspect(image.select('angle')).reduceRegion(ee.Reducer.mean(), image.geometry(), 1000)

        # in case of null values for heading replace with 0
        heading = ee.Dictionary(heading).combine({'aspect': 0}, False).get('aspect')

        heading = ee.Algorithms.If(
            ee.Number(heading).gt(180),
            ee.Number(heading).subtract(360),
            ee.Number(heading)
        )

        # the numbering follows the article chapters
        # 2.1.1 Radar geometry
        theta_iRad = image.select('angle').multiply(math.pi / 180)
        phi_iRad = ee.Image.constant(heading).multiply(math.pi / 180)

        # 2.1.2 Terrain geometry
        alpha_sRad = ee.Terrain.slope(elevation).select('slope').multiply(math.pi / 180)

        aspect = ee.Terrain.aspect(elevation).select('aspect').clip(geom)

        aspect_minus = aspect.updateMask(aspect.gt(180)).subtract(360)

        phi_sRad = aspect.updateMask(aspect.lte(180)) \
            .unmask() \
            .add(aspect_minus.unmask()) \
            .multiply(-1) \
            .multiply(math.pi / 180)

        # elevation = DEM.reproject(proj,None, 10).clip(geom)

        # 2.1.3 Model geometry
        # reduce to 3 angle
        phi_rRad = phi_iRad.subtract(phi_sRad)

        # slope steepness in range (eq. 2)
        alpha_rRad = (alpha_sRad.tan().multiply(phi_rRad.cos())).atan()

        # slope steepness in azimuth (eq 3)
        alpha_azRad = (alpha_sRad.tan().multiply(phi_rRad.sin())).atan()

        # 2.2
        # Gamma_nought
        gamma0 = image.divide(theta_iRad.cos())

        if (TERRAIN_FLATTENING_MODEL == 'VOLUME'):
            # Volumetric Model
            scf = _volumetric_model_SCF(theta_iRad, alpha_rRad)

        if (TERRAIN_FLATTENING_MODEL == 'DIRECT'):
            scf = _direct_model_SCF(theta_iRad, alpha_rRad, alpha_azRad)

        # apply model for Gamm0
        gamma0_flat = gamma0.multiply(scf)

        # get Layover/Shadow mask
        mask = _masking(alpha_rRad, theta_iRad, TERRAIN_FLATTENING_ADDITIONAL_LAYOVER_SHADOW_BUFFER)
        output = gamma0_flat.mask(mask).rename(bandNames).copyProperties(image)
        output = ee.Image(output).addBands(image.select('angle'), None, True)

        return output.set('system:time_start', image.get('system:time_start'))

    return collection.map(_correct)


# Function to process S1 linear to dB.
def lin_to_db(image):
    """
    Convert backscatter from linear to dB.
    Parameters
    ----------
    image : ee.Image
        Image to convert
    Returns
    -------
    ee.Image
        output image
    """
    bandNames = image.bandNames().remove('angle')
    db = ee.Image.constant(10).multiply(image.select(bandNames).log10()).rename(bandNames)
    return image.addBands(db, None, True)


def export_to_drive(image, aoi, description, folder="Final_GEE_Exports", scale=10):
    task = ee.batch.Export.image.toDrive(
        image=image.clip(aoi),
        description=description,
        folder=folder,
        fileNamePrefix=description,
        region=aoi,
        scale=scale,
        maxPixels=1e13
    )
    task.start()
    print("Export started:", description, "_", folder)


##################### TEMPORAL CONFIGURATION ####################

# MODIFIED: Monthly composites instead of quarterly
MONTHS = {
    1: (0.0, 1 / 12),
    2: (1 / 12, 2 / 12),
    3: (2 / 12, 3 / 12),
    4: (3 / 12, 4 / 12),
    5: (4 / 12, 5 / 12),
    6: (5 / 12, 6 / 12),
    7: (6 / 12, 7 / 12),
    8: (7 / 12, 8 / 12),
    9: (8 / 12, 9 / 12),
    10: (9 / 12, 10 / 12),
    11: (10 / 12, 11 / 12),
    12: (11 / 12, 1.0),
}


def get_monthly_window(year, month):
    """
    Get the start and end dates for a given month
    """
    m_start, m_end = MONTHS[month]
    start_date = year + m_start
    end_date = year + m_end
    return start_date, end_date


## ADJUST below:
YEARS = [2022, 2023, 2024, 2025]
MONTH_NUMBERS = list(range(1, 13))  # 1 to 12

# Scaling values for Sentinel-1 and Sentinel-2 data. This needs to be consistent with model training
# S1 values are in dB * 1000 after produce_s1_composite (int16 format)
s1vv_min = -25 * 1000
s1vv_max = 0 * 1000
s1vh_min = -30 * 1000
s1vh_max = -5 * 1000
# S2 values
s2vis_min = 0
s2vis_max = 3000
s2nir_min = 0
s2nir_max = 6000


# Function to scale S1 to values ranging 0-1
def scale_image_s1(image):
    """Scale S1 VV and VH bands from dB*1000 to 0-1 range"""
    vv = image.select('VV').unitScale(s1vv_min, s1vv_max).clamp(0, 1)
    vh = image.select('VH').unitScale(s1vh_min, s1vh_max).clamp(0, 1)

    return ee.Image.cat([vv, vh]).rename(['VV', 'VH'])


# Function to scale S2 to values ranging 0-1
# MODIFIED: Only scale B3, B4, B8, B12
def scale_image_s2(image):
    """Scale S2 bands to 0-1 range"""
    # Extract and scale bands
    b3 = image.select('B3').unitScale(s2vis_min, s2vis_max).clamp(0, 1)
    b4 = image.select('B4').unitScale(s2vis_min, s2vis_max).clamp(0, 1)
    b8 = image.select('B8').unitScale(s2nir_min, s2nir_max).clamp(0, 1)
    b12 = image.select('B12').unitScale(s2vis_min, s2vis_max).clamp(0, 1)

    scaled = ee.Image.cat([b3, b4, b8, b12]).rename([
        'B3', 'B4', 'B8', 'B12'
    ])

    return scaled.unmask(0)  # To set cloudmasks to 0 instead of 'masked'


######################## MAIN EXPORT LOOP ########################

for aoi_obj in ee_aois:
    aoi = aoi_obj["geometry"]
    aoi_id = aoi_obj["id"]
    #for extra AOIs run
    aoi_id += 10
    for year in YEARS:
        for month in MONTH_NUMBERS:
            start_date, end_date = get_monthly_window(year, month)

            print(
                f"AOI {aoi_id} | {year} Month {month:02d} "
                f"({start_date:.4f} → {end_date:.4f})"
            )

            # Produce raw composites
            s1_raw = produce_s1_composite(aoi, start_date, end_date)
            s2_raw = produce_s2_composite(aoi, start_date, end_date)

            # Scale to 0-1 range
            s1_scaled = scale_image_s1(s1_raw)
            s2_scaled = scale_image_s2(s2_raw)

            # Combine S1 and S2
            composite_scaled = (
                s1_scaled.rename(["S1_VV", "S1_VH"])
                .addBands(
                    s2_scaled.rename(["S2_B3", "S2_B4", "S2_B8", "S2_B12"])
                )
            )

            # Multiply by 1000 and convert to int16
            composite_export = composite_scaled.multiply(1000).toInt16()

            # Export to Drive
            # MODIFIED: Folder structure is now Final_GEE_Exports/AOI_{aoi_id}
            export_name = f"AOI_{aoi_id}_{year}_M{month:02d}"
            export_folder = f"Final_GEE_Exports/AOI_{aoi_id}"
            export_to_drive(composite_export, aoi, export_name, folder=export_folder)

print("\n=== All export tasks started successfully ===")