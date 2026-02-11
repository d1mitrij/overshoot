FISHING  –  Formula parameters: P_fishing, Fish_catch, PPR

fish_supply_fbs.csv       Fish & seafood from food balance sheets
                          Source: FAOSTAT Food Balance Sheets
                          Includes: production, import, export,
                          domestic supply, food supply per capita

fisheries_emissions.csv   GHG emissions from fisheries/aquaculture
                          Source: FAOSTAT Emissions Totals

NOTE: Detailed capture fisheries data (needed for the formula)
is NOT in FAOSTAT bulk downloads.  You must download separately:

  FAO FishSTAT (capture fisheries by species, country, year):
    https://www.fao.org/fishery/en/statistics
    Dataset: 'Global Capture Production'
    Reference MSY: 93 million tonnes/year (FAO 1997)

  Sea Around Us (trophic levels & Primary Production Requirement):
    https://www.seaaroundus.org/data/
    Advanced Search > filter by EEZ for tonnage and PPR
    Required to convert catch into fishing-ground area demand
