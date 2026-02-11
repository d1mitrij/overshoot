FACTORS  –  Formula parameters: Equivalence_Factor (EF),
                                Yield_Factor (YF)

equivalence_factors_reference_1999.csv
    Reference EF values from Wackernagel et al. 2002 (Table 1)
    These are for 1999; EFs change yearly with land-use shifts.

FORMULA:
  Global_hectares = Physical_ha × Yield_Factor × Equivalence_Factor

  Yield_Factor (YF) = country_yield / world_average_yield
    → computed from FAOSTAT production data (01_cropland, etc.)

  Equivalence_Factor (EF) = suitability_index / global_avg_SI
    → derived from GAEZ agricultural suitability data

MANUAL DOWNLOAD:
  GAEZ (Global Agro-Ecological Zones, FAO/IIASA):
    https://gaez.fao.org/
    Theme 4: Suitability and Attainable Yield
    Theme 5: Actual Yields and Production
    Also available as ArcGIS Image Services

  GLASOD (Soil degradation → biocapacity loss):
    https://data.isric.org/geonetwork/srv/api/records/9e84c15e-cb46-45e2-9126-1ca38bd5cd22
    Download the Shapefile format from ISRIC repository
    Degradation rated: light / moderate / strong / extreme
