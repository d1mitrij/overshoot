REFERENCE PARAMETERS  –  Literature-based constants for the formula

carbon_sequestration_parameters.csv
    AFCS = 0.73 ± 0.37 t C/ha/yr (Mancini et al., NFA 2016)
    Ocean CO₂ absorption: 28-35% (Khatiwala et al. 2009)
    Formula: EF_C = CO₂ × (1 - S_Ocean) / Y_C × EQF_forest

forest_nai_reference.csv
    Net Annual Increment = 1.81 m³/ha/yr (UNECE/FAO TBFRA 2000)
    Denominator for forest product Footprint

ocean_co2_uptake_timeseries.csv
    Approximate decadal ocean CO₂ uptake (Pg C/yr)
    Source: Khatiwala et al. 2009
    Divide by CDIAC total emissions for time-varying fraction

sustainable_catch_by_group.csv
    Reference MSY allocation across 14 species groups
    Total: ~93 million tonnes/yr (Gulland 1971)

FORMULA NOTES:
  Carbon FP = [CO₂ × (1 - ocean_frac)] / AFCS × EQF_forest
  Forest FP = timber_m3 / NAI × EQF_forest
  Grazing FP = pasture_feed_demand / grassland_NPP × EQF_grazing
  Fishing FP = PPR_harvest / (PPS / shelf_area) × EQF_fishing
    where PPR = catch × discard_rate × (1/TE)^(TL-1) / carbon_ratio
