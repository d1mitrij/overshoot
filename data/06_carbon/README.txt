CARBON  –  Formula parameters: Carbon_Footprint, CO2_emissions,
                               Sequestration_rate

co2_energy_faostat.csv         CO₂ from the Energy sector (kt)
                               Source: FAOSTAT Emissions Totals
                               Item='Energy', Element='Emissions (CO2)'
                               >>> PRIMARY INPUT for carbon Footprint

co2_agrifood_total_faostat.csv Total agrifood-system CO₂/CO₂eq (kt)
                               Source: FAOSTAT Emissions Totals

lulucf_emissions_faostat.csv   Land-use change & forest emissions
                               Source: FAOSTAT Emissions Totals

co2_worldbank_*.csv            Cross-check from World Bank WDI
                               (may be empty if indicator archived)

FORMULA NOTE:
  Carbon Footprint = forest area needed to sequester 65% of CO₂
  (oceans absorb ~35%).  Sequestration rate from IPCC: weighted
  average across 26 forest biomes.

MANUAL DOWNLOAD for additional detail:
  IEA (requires license):
    https://www.iea.org/data-and-statistics/data-explorers
    Database: 'Greenhouse Gas Emissions from Energy'

  EDGAR (EU JRC, free):
    https://edgar.jrc.ec.europa.eu/
    Dataset: EDGARv8.0 CO₂ 1970–2023
