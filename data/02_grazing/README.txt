GRAZING  –  Formula parameters: P_grazing, Feed_demand

pasture_area.csv               Permanent meadows & pastures (1000 ha)
                               Source: FAOSTAT RL; Item 6655

livestock_stocks.csv           Livestock populations (head) and slaughter
                               Source: FAOSTAT QCL

gleam_feed_coefficients.csv    Dry matter intake & feed source fractions
                               per livestock type (kg DM/head/day)
                               Source: FAO GLEAM 3.0 global averages
                               Used to compute: TFR, F_Mkt, F_Crop, F_Res
                               Grazing demand = TFR - F_Mkt - F_Crop - F_Res

grassland_npp_reference.csv    World-average grassland productivity
                               Value: 2.45 t DM/ha/yr
                               Source: Monfreda et al. 2008 (SAGE)

FORMULA:
  P_GR = TFR - F_Mkt - F_Crop - F_Res  (pasture-based feed demand)
  EF_grazing = (P_GR / Y_W_grass) * EQF_grazing
  Y_W_grass = 2.45 t DM/ha/yr

For detailed regional coefficients, download FAO GLEAM model:
  https://www.fao.org/gleam/en/
