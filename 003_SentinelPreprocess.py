
import ee
import geemap
import math


"""
description: 
function that loads the date to ee format
production of the sentinel 1 and sentinel 2 composites 
This is done from the EE environment images
"""

def convert_dec_to_eedate(number):

    '''
    Converts an decimal date number to an ee.Date
    '''
    # Obtain a year and doy integer separately
    doy = int(number % 1 * 365) + 1
    year = int(number)

    # Create the datestring and fill small doy numbers with preceding 0s
    jul_date_string = str(year) + (str(doy)).zfill(3)

    # Make the ee.Date
    eedate = ee.Date.parse('YYYYDDD' , jul_date_string)

    return eedate

# Function to produce an S1 composite (where we consider both ascending and descending)
def produce_s1_composite(start_date, end_date):
 
  # Convert the decimal dates to ee.Date
  start_date = convert_dec_to_eedate(start_date)
  end_date = convert_dec_to_eedate(end_date)
 
  # Define the descending orbit collection
  s1_descending = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT')\
      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))\
      .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))\
      .filterDate(start_date, end_date)
 
  # Define the ascending orbit collection
  s1_ascending = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT')\
      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))\
      .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))\
      .filterDate(start_date, end_date)
 
  # Define a function to pre-process the collection if it's not empty, then make a mean composite
  def process_collection(s1_collection):
      s1_collection = s1_collection.map(s1_mask_edges)
      s1_collection = slope_correction(s1_collection)
      s1_collection = s1_collection.map(lin_to_db)
      s1_composite = s1_collection.select(['VV', 'VH']).mean()
      return s1_composite
 
  # Use ee.Algorithms.If to handle empty collections for descending and ascending
  s1_descending_composite = ee.Algorithms.If(
      s1_descending.size().gt(0),
      process_collection(s1_descending),
      ee.Image.constant([-100, -100]).rename(['VV', 'VH'])#.updateMask(0)
  )
 
  s1_ascending_composite = ee.Algorithms.If(
      s1_ascending.size().gt(0),
      process_collection(s1_ascending),
      ee.Image.constant([-100, -100]).rename(['VV', 'VH'])#.updateMask(0)
  )
 
  # Convert the output of ee.Algorithms.If to ee.Image
  s1_descending_composite = ee.Image(s1_descending_composite).unmask(-100)
  s1_ascending_composite = ee.Image(s1_ascending_composite).unmask(-100)
 
  # Blend the composites
  s1_composite = s1_descending_composite.where(s1_descending_composite.select('VV').eq(-100), s1_ascending_composite)
 
  #-# ATTENTION Scale no-data values to 1s instead of 0s (note that 0s are high values and will become 1s after 0-1 scaling)
  s1_composite = s1_composite.where(s1_composite.select('VV').eq(-100), 0)
 
  # Put the VV and VH bands in an integer format
  s1_composite = s1_composite.multiply(1000).toInt16()
 
  return ee.Image(s1_composite)
 
 
 
 
 
 
 
 
# Function to produce an S2 composite SR, we backfill the cloud gaps up to 6 months in the past
def produce_s2_composite(start_date, end_date):
 
  # Define variables for cloud masking
  cloud_probability = 0.60
  cloud_band = 'cs'
 
  # Convert the decimal dates to ee.Date
  start_date = convert_dec_to_eedate(start_date)
  end_date = convert_dec_to_eedate(end_date)
 
 
 
  # Define the s2 SR collection to be used
  s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
                          .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE',95))\
                          .filterDate(end_date.advance(-6, 'month'), end_date)
 
  # Take the cloud probabilites from the cloudscore+ method, link the collections, and apply cloud masking
  cloudscore = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
 
  s2 = s2.linkCollection(cloudscore, [cloud_band])\
         .map(lambda img :  img.updateMask(img.select(cloud_band).gte(cloud_probability)))
 
  # Sort images by date in descending order to prioritize the most recent pixel
  s2_sorted = s2.select(['B12', 'B8', 'B4', 'B3'])\
                .sort('system:time_start', True)  # Sort in descending order
 
  # Use .mosaic() to create a backfill composite (most recent on top)
  s2_composite = s2_sorted.mosaic()
 
  # Make a recent short-term (defined by the COMPOSITE_PERIOD) median composite that we put (even further) on top
  s2_lastmonth = s2_sorted.filterDate(start_date, end_date).median()
  s2_composite = s2_composite.blend(s2_lastmonth)
 
  return s2_composite
 
 
 
 
 
# Masking S1 edges (Work from Andreas, Daniel and Bart) #https://code.earthengine.google.com/ccdb1f10b5f9afddbe5453a234c99c57
def s1_mask_edges(image):
  angle = image.select('angle')
  return image\
    .updateMask(\
      createSceneStartEndMask(image, 500)\
        .And(angle.gt(30.63993).And(angle.lt(45.23993)))\
    )
 
def createSceneStartEndMask(image, bufferMeters):
  geometry = image.geometry()
  coordinates = ee.Array(ee.List(geometry.coordinates().get(0)))
  size = coordinates.length().get([0])
  Max = coordinates.reduce(ee.Reducer.max(), [0])
  Min = coordinates.reduce(ee.Reducer.min(), [0])
  xMax = ee.Geometry.Point(coordinates.mask(\
    Max.slice(1, 0, 1).repeat(0, size).eq(coordinates.slice(1, 0, 1))\
    ).slice(0, 0, 1).project([1]).toList())
  xMin = ee.Geometry.Point(coordinates.mask(\
    Min.slice(1, 0, 1).repeat(0, size).eq(coordinates.slice(1, 0, 1))\
    ).slice(0, 0, 1).project([1]).toList())
  yMax = ee.Geometry.Point(coordinates.mask(\
    Max.slice(1, 1).repeat(0, size).eq(coordinates.slice(1, 1))\
    ).slice(0, 0, 1).project([1]).toList())
  yMin = ee.Geometry.Point(coordinates.mask(\
    Min.slice(1, 1).repeat(0, size).eq(coordinates.slice(1, 1))\
    ).slice(0, 0, 1).project([1]).toList())
  totalSlices = image.getNumber('totalSlices')
  features = ee.FeatureCollection([\
    ee.Feature(ee.Feature(ee.Geometry.LineString([xMax, yMax]), {'sliceNumber': 1, 'orbit': 'DESCENDING'})),\
    ee.Feature(ee.Feature(ee.Geometry.LineString([xMin, yMin]), {'sliceNumber': totalSlices, 'orbit': 'DESCENDING'})),\
    ee.Feature(ee.Feature(ee.Geometry.LineString([xMax, yMin]), {'sliceNumber': 1, 'orbit': 'ASCENDING'})),\
    ee.Feature(ee.Feature(ee.Geometry.LineString([xMin, yMax]), {'sliceNumber': totalSlices, 'orbit': 'ASCENDING'})),\
    ])\
    .filter(ee.Filter.And(\
      ee.Filter.eq('sliceNumber', image.getNumber('sliceNumber')),\
      ee.Filter.eq('orbit', image.getString('orbitProperties_pass'))\
    ))
  buffered = features.geometry().buffer(20000)
  coords = ee.List(geometry.coordinates().get(0))
  segments = ee.FeatureCollection(coords.zip(coords.slice(1).cat(coords.slice(0, 1)))\
    .map(lambda segment : ee.Feature(ee.Geometry.LineString(ee.List(segment))))
  )
  # Select segments on the footprint contained within buffered
  filteredSegments = segments.filter(ee.Filter.isContained('.geo', buffered))
 
  return filteredSegments.distance(bufferMeters).Not().unmask(1)
 
 
 
def slope_correction(collection,
                     TERRAIN_FLATTENING_MODEL = 'VOLUME',
                     DEM = ee.Image('USGS/SRTMGL1_003'),
                     TERRAIN_FLATTENING_ADDITIONAL_LAYOVER_SHADOW_BUFFER = 0):
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
 
    ninetyRad = ee.Image.constant(90).multiply(math.pi/180)
 
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
 
        elevation = DEM.resample('bilinear').reproject(proj,None, 10).clip(geom)
 
        # calculate the look direction
        heading = ee.Terrain.aspect(image.select('angle')).reduceRegion(ee.Reducer.mean(), image.geometry(), 1000)
 
 
        #in case of null values for heading replace with 0
        heading = ee.Dictionary(heading).combine({'aspect': 0}, False).get('aspect')
 
        heading = ee.Algorithms.If(
            ee.Number(heading).gt(180),
            ee.Number(heading).subtract(360),
            ee.Number(heading)
        )
 
        # the numbering follows the article chapters
        # 2.1.1 Radar geometry
        theta_iRad = image.select('angle').multiply(math.pi/180)
        phi_iRad = ee.Image.constant(heading).multiply(math.pi/180)
 
        # 2.1.2 Terrain geometry
        alpha_sRad = ee.Terrain.slope(elevation).select('slope').multiply(math.pi / 180)
 
        aspect = ee.Terrain.aspect(elevation).select('aspect').clip(geom)
 
        aspect_minus = aspect.updateMask(aspect.gt(180)).subtract(360)
 
        phi_sRad = aspect.updateMask(aspect.lte(180))\
            .unmask()\
            .add(aspect_minus.unmask())\
            .multiply(-1)\
            .multiply(math.pi / 180)
 
        #elevation = DEM.reproject(proj,None, 10).clip(geom)
 
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


##################### EXAMPLE USE ####################
# COMPOSITE_PERIOD = 1/12   # The period length to produce the most recent Sentinel composites for (years)
# EXPORT_MOMENTS = [2020.75, 2021.00, 2021.25, 2021.50, 2021.75, 2022.00, 2022.25, 2022.50, 2022.75, 2023.00, 2023.25, 2023.50, 2023.75, 2024.00] 

# # Loop through the export moments, i.e. the dates
# for export_moment in EXPORT_MOMENTS:
#   date_now = export_moment

#   # Get start and end dates for sentinel image composites
#   start_date = date_now - COMPOSITE_PERIOD
#   end_date = date_now

#   # Create the images we need
#   s1_composite = produce_s1_composite(start_date, end_date) #-# the orbit 'DESCENDING' was removed here
#   s2_composite = produce_s2_composite(start_date, end_date)