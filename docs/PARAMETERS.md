# Parameter Reference — Ecological Overshoot Calculator

Every parameter used in `scripts/calculate_overshoot.py`, with its value, origin, and how it enters each formula. Parameters are either **fetched** from a database at runtime or **hard-coded** from a published source.

---

## Quick legend

| Symbol | Meaning |
|--------|---------|
| **DB** | Fetched from FAOSTAT bulk download (varies by country and year) |
| **REF-CSV** | Loaded from a small reference CSV committed to git |
| **HC** | Hard-coded constant in the Python script, from a specific publication |

---

## 1. Cropland Footprint

### Formula

```
EF_cropland = Σ_crops ( Production_t / Y_W ) × EQF_cropland

BC_cropland = CroplandArea_ha × YF × EQF_cropland

where  Y_W  = WorldProduction_t / WorldAreaHarvested_ha   (per crop group, per year)
       YF   = NationalYield / WorldYield                   (weighted across crops)
```

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **Crop production** (tonnes) | `Production_t` | varies | **DB** | FAOSTAT domain QCL, Element "Production", Unit "t". Bulk file `Production_Crops_Livestock_E_All_Data_(Normalized).zip`. Extracted to `crop_production.csv`. Crop groups: Cereals primary (1717), Fruit Primary (1738), Oilcrops Oil Equivalent (1732), Pulses Total (1726), Roots & Tubers Total (1720), Vegetables Primary (1735). | `data/01_cropland/crop_production.csv` |
| **Area harvested** (ha) | `AreaHarvested_ha` | varies | **DB** | Same FAOSTAT QCL file, Element "Area harvested", Unit "ha". Same 6 crop groups. | `data/01_cropland/crop_production.csv` |
| **World yield** | `Y_W` | computed | **DB** (derived) | Computed at runtime: sum of all countries' production / sum of all countries' area harvested, per crop group per year. Countries identified by `Area Code < 5000` (excludes FAO aggregate codes). | Script line 139–159 |
| **Cropland area** (1000 ha) | `CroplandArea` | varies | **DB** | FAOSTAT domain RL (Land Use), Items: "Arable land" (6621) + "Permanent crops" (6650), Element "Area", Unit "1000 ha". Bulk file `Inputs_LandUse_E_All_Data_(Normalized).zip`. Extracted to `cropland_area.csv`. | `data/01_cropland/cropland_area.csv` |
| **Yield Factor** | `YF` | computed | **DB** (derived) | National yield / world yield, weighted across crop groups. Clamped to range [0.01, 10.0] to prevent outliers. Falls back to YF=1.0 when data is missing. | Script line ~220–245 |
| **Equivalence Factor** | `EQF_cropland` | **2.1** gha/ha | **HC** | Wackernagel, M. et al. (2002). "Tracking the Ecological Overshoot of the Human Economy." *PNAS* 99(14): 9266–9271. Table 1. | `data/09_factors/equivalence_factors_reference_1999.csv` (also in script line 34) |

---

## 2. Grazing Land Footprint

### Formula

```
EF_grazing = Σ_species ( Heads × AnnualPastureDemand_t ) / GrasslandNPP × EQF_grazing

BC_grazing = PastureArea_ha × YF_grazing × EQF_grazing
```

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **Livestock heads** | `Heads` | varies | **DB** | FAOSTAT domain QA, Element "Stocks", Unit "An" (animals). Bulk file `Production_Crops_Livestock_E_All_Data_(Normalized).zip`. Extracted to `livestock_stocks.csv`. Species: Cattle (866), Buffalo (946), Sheep (976), Goats (1016), Camels (1126), Swine/pigs (1034). | `data/02_grazing/livestock_stocks.csv` |
| **Annual pasture demand — Cattle** | `PastureDemand` | **2.35** t DM/head/yr | **HC** | Average of dairy (2.382) and beef (2.325). Source: FAO GLEAM 3.0 Global Livestock Environmental Assessment Model, global average feed coefficients. GLEAM documentation: https://www.fao.org/gleam/en/ | `data/02_grazing/gleam_feed_coefficients.csv`, script line 72 |
| **Annual pasture demand — Buffalo** | | **2.409** t DM/head/yr | **REF-CSV** | FAO GLEAM 3.0 (global averages). Total DMI 12.0 kg/day × pasture fraction 0.55 × 365 / 1000. | `data/02_grazing/gleam_feed_coefficients.csv` |
| **Annual pasture demand — Sheep** | | **0.46** t DM/head/yr | **REF-CSV** | FAO GLEAM 3.0. Total DMI 1.8 kg/day × pasture fraction 0.70 × 365 / 1000. | `data/02_grazing/gleam_feed_coefficients.csv` |
| **Annual pasture demand — Goats** | | **0.394** t DM/head/yr | **REF-CSV** | FAO GLEAM 3.0. Total DMI 1.5 kg/day × pasture fraction 0.72 × 365 / 1000. | `data/02_grazing/gleam_feed_coefficients.csv` |
| **Annual pasture demand — Camels** | | **2.0** t DM/head/yr | **HC** | Approximate, assumed similar to cattle. No direct GLEAM coefficient available for camels. | Script line 76 |
| **Annual pasture demand — Pigs** | | **0.0** t DM/head/yr | **REF-CSV** | FAO GLEAM 3.0. Pigs are fed entirely on crop-based feed and residues; zero pasture grazing. | `data/02_grazing/gleam_feed_coefficients.csv`, script line 77 |
| **Grassland NPP** | `GrasslandNPP` | **2.45** t DM/ha/yr | **HC** | Monfreda, C. et al. (2008). "Farming the planet: Geographic distribution of crop areas, yields, physiological types, and net primary production in the year 2000." *Global Biogeochemical Cycles* 22(1). Above-ground edible NPP for grassland, from SAGE dataset (University of Wisconsin). | `data/02_grazing/grassland_npp_reference.csv`, script line 42 |
| **Pasture area** (1000 ha) | `PastureArea` | varies | **DB** | FAOSTAT domain RL, Item "Permanent meadows and pastures" (6655), Element "Area", Unit "1000 ha". | `data/02_grazing/pasture_area.csv` |
| **Yield Factor (grazing)** | `YF_grazing` | **1.0** | **HC** | Simplification. The official NFA computes country-specific grazing YFs from GAEZ suitability indices. We use 1.0 (world average) as approximation. | Script line (implicit in vectorized BC calculation) |
| **Equivalence Factor** | `EQF_grazing` | **0.5** gha/ha | **HC** | Wackernagel et al. (2002), Table 1. | `data/09_factors/equivalence_factors_reference_1999.csv`, script line 37 |

---

## 3. Forest Product Footprint

### Formula

```
EF_forest = RoundwoodProduction_m3 / NAI × EQF_forest

BC_forest = ForestArea_ha × YF_forest × EQF_forest
```

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **Roundwood production** (m³) | `RoundwoodProd` | varies | **DB** | FAOSTAT domain FO (Forestry), Item "Roundwood" (1861), Element "Production" (5516), Unit "m3". Bulk file `Forestry_E_All_Data_(Normalized).zip`. Includes both industrial roundwood and fuelwood. | `data/03_forest/timber_production.csv` |
| **Net Annual Increment** | `NAI` | **1.81** m³/ha/yr | **HC** | UNECE/FAO Temperate and Boreal Forest Resource Assessment 2000 (TBFRA-2000), combined with FAO Global Fibre Supply Model 1998 (GFSM) for tropical data. World average across temperate, boreal, and tropical forests. | `data/10_reference_parameters/forest_nai_reference.csv`, script line 43 |
| **Forest area** (1000 ha) | `ForestArea` | varies | **DB** | FAOSTAT domain RL, Item "Forest land" (6646), Element "Area", Unit "1000 ha". Derived from FAO Forest Resources Assessment (FRA). Data from 1990 onward; interpolated between FRA reporting years (1990, 2000, 2005, 2010, 2015, 2020). | `data/03_forest/forest_area.csv` |
| **Yield Factor (forest)** | `YF_forest` | **1.0** | **HC** | Simplification. Official NFA uses NAI ratio between national and world forests. We use 1.0 as approximation. | Script (implicit) |
| **Equivalence Factor** | `EQF_forest` | **1.3** gha/ha | **HC** | Wackernagel et al. (2002), Table 1. | `data/09_factors/equivalence_factors_reference_1999.csv`, script line 36 |

---

## 4. Fishing Grounds Footprint

### Formula

```
PPR = Catch_t × DiscardRate × (1 / TE)^(TL - 1) / WetToCarbon

MarineYield = WorldSustainablePPR / ContinentalShelfArea

EF_fishing = PPR / MarineYield × EQF_fishing

BC_fishing = ContinentalShelfArea × (CountryCatch / WorldCatch) × EQF_fishing
```

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **Fish production** (1000 t) | `Catch_kt` | varies | **DB** | FAOSTAT domain FBS (Food Balance Sheets), Element "Production" (5511), Unit "1000 t". Includes marine and freshwater capture plus aquaculture. Sub-categories: Freshwater Fish (2761), Demersal Fish (2762), Pelagic Fish (2763), Marine Fish Other (2764), Crustaceans (2765), Cephalopods (2766), Molluscs Other (2767), Aquatic Animals Others (2769), Aquatic Products Other (2961), Meat Aquatic Mammals (2768). The aggregate "Fish, Seafood" (2960) is **excluded** to avoid double-counting. Bulk file `FoodBalanceSheets_E_All_Data_(Normalized).zip`. | `data/04_fishing/fish_supply_fbs.csv` |
| **Transfer efficiency** | `TE` | **0.1013** (10.13%) | **HC** | Pauly, D. & Christensen, V. (1995). "Primary production required to sustain global fisheries." *Nature* 374: 255–257. Mean trophic transfer efficiency across marine ecosystems. | `data/04_fishing/ppr_calculation_parameters.csv`, script line 48 |
| **Discard rate** | `DiscardRate` | **1.27** | **HC** | Pauly & Christensen (1995). Ratio meaning 1.0 t landed + 0.27 t discarded bycatch per tonne of reported catch. | `data/04_fishing/ppr_calculation_parameters.csv`, script line 49 |
| **Wet weight to carbon** | `WetToCarbon` | **9.0** | **HC** | Sea Around Us project / Pauly. 9:1 ratio of wet fish weight to carbon content. Used to convert catch tonnage to carbon equivalents for PPR. | `data/04_fishing/ppr_calculation_parameters.csv`, script line 50 |
| **Trophic level — Freshwater Fish** | `TL` | **2.5** | **HC** | Average across freshwater species. Sources: Pauly & Christensen (1995), FishBase trophic ecology data (www.fishbase.org). Nile tilapia ~2.0, common carp ~2.9, catla ~2.5 → group average 2.5. | Script line 57, `data/04_fishing/fish_trophic_reference.csv` |
| **Trophic level — Demersal Fish** | | **3.8** | **HC** | Atlantic cod 4.0, Alaska pollock 3.5, largehead hairtail 4.0 → group average ~3.8. Pauly & Christensen 1995 / FishBase. | Script line 58 |
| **Trophic level — Pelagic Fish** | | **3.0** | **HC** | Anchoveta 2.7, herring 3.2, sardine 2.7, mackerel 3.2, sprat 3.0 → group average ~3.0. Pauly & Christensen 1995 / FishBase. | Script line 59 |
| **Trophic level — Marine Fish, Other** | | **3.2** | **HC** | Average of miscellaneous marine species. Pauly & Christensen 1995. | Script line 60 |
| **Trophic level — Crustaceans** | | **2.5** | **HC** | Shrimp species typically TL 2.0–3.0, average ~2.5. FishBase / Sea Around Us. | Script line 61 |
| **Trophic level — Cephalopods** | | **3.5** | **HC** | Squid and octopus are active predators, TL 3.2–4.0, average ~3.5. FishBase. | Script line 62 |
| **Trophic level — Molluscs, Other** | | **2.1** | **HC** | Bivalves (mussels, clams, oysters) are filter feeders, TL ~2.0–2.2. FishBase. | Script line 63 |
| **Trophic level — Aquatic Animals, Others** | | **3.0** | **HC** | Mixed group, assigned mid-range value. | Script line 64 |
| **Trophic level — Aquatic Products, Other** | | **3.0** | **HC** | Mixed group, assigned mid-range value. | Script line 65 |
| **Trophic level — Meat, Aquatic Mammals** | | **3.2** | **HC** | Marine mammals are mid-to-upper predators. | Script line 66 |
| **Sustainable global catch** | `MSY` | **93.0** Mt/yr | **HC** | Gulland, J.A. (1971). *The Fish Resources of the Ocean*. Fishing News Books, West Byfleet. Also referenced in FAO SOFIA reports. This is the maximum sustainable yield for global marine capture fisheries. | `data/04_fishing/ppr_calculation_parameters.csv`, `data/10_reference_parameters/sustainable_catch_by_group.csv`, script line 51 |
| **Continental shelf area** | `ShelfArea` | **2.0 × 10⁹** ha | **HC** | Various oceanographic references. Approximately 24.3 million km² = 2.43 billion ha; rounded to 2 billion ha following standard NFA practice. | `data/04_fishing/ppr_calculation_parameters.csv`, script line 52 |
| **Equivalence Factor** | `EQF_fishing` | **0.4** gha/ha | **HC** | Wackernagel et al. (2002), Table 1. | `data/09_factors/equivalence_factors_reference_1999.csv`, script line 38 |

---

## 5. Built-up Land Footprint

### Formula

```
EF_built_up = BC_built_up = BuiltUpArea_ha × EQF_built_up
```

Built-up land is assumed to replace cropland of equivalent productivity, so EF = BC.

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **Built-up area** (1000 ha) | `BuiltUpArea` | varies | **DB** (3-tier) | **Tier 1**: FAOSTAT item 6649 "Farm buildings and Farmyards" — available for ~36 countries. From `Inputs_LandUse_E_All_Data_(Normalized).zip`, Unit "1000 ha". **Tier 2**: Land-use residual = `LandArea (6601) − AgLand (6610) − Forest (6646) − OtherLand (6670) − InlandWaters (6680)`, used where positive. All items from same land-use ZIP. **Tier 3**: 3% of cropland area (Arable land 6621 + Permanent crops 6650) as proxy — for countries where Tier 1 and 2 fail. | `data/raw/Inputs_LandUse_E_All_Data_(Normalized).zip`, script lines ~290–330 |
| **Equivalence Factor** | `EQF_built_up` | **2.2** gha/ha | **HC** | Wackernagel et al. (2002). Built-up land is assumed to occupy former cropland, so EQF is set slightly above cropland (2.1) to reflect the high-productivity land typically urbanised. The 2.2 value is from the same Table 1. | `data/09_factors/equivalence_factors_reference_1999.csv`, script line 35 |

---

## 6. Carbon Footprint

### Formula

```
CO2_net_t = CO2_energy_kt × 1000 × (1 − OceanFraction)

SeqRate_CO2 = AFCS × (44 / 12)          [converts t C/ha/yr → t CO2/ha/yr]

EF_carbon = CO2_net_t / SeqRate_CO2 × EQF_carbon
```

No explicit biocapacity for carbon — the forest BC component absorbs this role.

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **CO₂ emissions from energy** (kt) | `CO2_kt` | varies | **DB** | FAOSTAT domain GT (Emissions Totals), Item "Energy" (6821), Element "Emissions (CO2)" (7273), Source "FAO TIER 1" (3050), Unit "kt". This covers fossil fuel combustion CO₂ from the energy sector. Bulk file `Emissions_Totals_E_All_Data_(Normalized).zip`. | `data/06_carbon/co2_energy_faostat.csv` |
| **Ocean CO₂ absorption fraction** | `OceanFraction` | **0.35** (35%) | **HC** | Khatiwala, S. et al. (2009). "Reconstruction of the history of anthropogenic CO₂ concentrations in the ocean." *Nature* 462: 346–349. The 28–35% range is from their 1961–2008 reconstruction. The 35% default is from Wackernagel et al. (2002) / IPCC Third Assessment Report (2001). We use the upper bound (35%) as a constant following standard NFA practice. | `data/10_reference_parameters/carbon_sequestration_parameters.csv`, script line 45 |
| **Average Forest Carbon Sequestration** | `AFCS` | **0.73** t C/ha/yr | **HC** | Mancini, M.S. et al. (2016). "Ecological Footprint: Refining the carbon Footprint calculation." *Ecological Indicators* 61: 390–403. This is the NFA 2016 value: weighted average carbon uptake across 26 forest biomes, accounting for fire, soil carbon, and harvested wood product emissions. Uncertainty: ± 0.37 t C/ha/yr. | `data/10_reference_parameters/carbon_sequestration_parameters.csv`, script line 44 |
| **CO₂/C molecular weight ratio** | `44/12` | **3.667** | **HC** | Stoichiometric ratio of CO₂ to C molecular weights. Used to convert AFCS from t C/ha/yr to t CO₂/ha/yr: 0.73 × 3.667 = 2.677 t CO₂/ha/yr. Standard chemistry. | Script line (in formula, implicit) |
| **Equivalence Factor** | `EQF_carbon` | **1.3** gha/ha | **HC** | Uses the forest EQF because carbon sequestration occurs on forest land. Wackernagel et al. (2002), Table 1. | `data/09_factors/equivalence_factors_reference_1999.csv`, script line 39 |

---

## 7. Population

### Parameters

| Parameter | Symbol | Value | Source type | Source detail | File / Line |
|-----------|--------|-------|-------------|---------------|-------------|
| **National population** (1000 persons) | `Population` | varies | **DB** | FAOSTAT domain OA, Item "Population - Est. & Proj." (3010), Element "Total Population - Both sexes" (511), Unit "1000 No". Covers 1950–2100 (estimates + projections). Bulk file `Population_E_All_Data_(Normalized).zip`. | `data/07_population/population.csv` |

---

## 8. Derived / Aggregated Outputs

These are not input parameters but computed from the above:

| Output | Formula | Unit |
|--------|---------|------|
| `ef_total_gha` | `ef_cropland + ef_grazing + ef_forest + ef_fishing + ef_built_up + ef_carbon` | gha |
| `bc_total_gha` | `bc_cropland + bc_grazing + bc_forest + bc_fishing + bc_built_up` | gha |
| `ecological_deficit_gha` | `bc_total - ef_total` (negative = deficit) | gha |
| `ef_per_capita_gha` | `ef_total / (population × 1000)` | gha/person |
| `bc_per_capita_gha` | `bc_total / (population × 1000)` | gha/person |
| `number_of_earths` | `world_ef / world_bc` | ratio |
| `overshoot_day` | `floor(365 × world_bc / world_ef)` | day of year |

---

## 9. Equivalence Factor Summary

All EQFs are **static 1999 values** from a single publication:

> Wackernagel, M., Schulz, N.B., Deumling, D. et al. (2002). "Tracking the Ecological Overshoot of the Human Economy." *Proceedings of the National Academy of Sciences* 99(14): 9266–9271.

| Land type | EQF (gha/ha) | Script constant | Note |
|-----------|:------------:|-----------------|------|
| Cropland | 2.1 | `EQF_CROPLAND` | Highest productivity per ha |
| Built-up land | 2.2 | `EQF_BUILT_UP` | Assumed to replace prime cropland |
| Forest | 1.3 | `EQF_FOREST` | Also used for carbon sequestration |
| Grazing land | 0.5 | `EQF_GRAZING` | Low per-ha productivity |
| Fishing grounds | 0.4 | `EQF_FISHING` | Marine productivity |
| Carbon | 1.3 | `EQF_CARBON` | = Forest EQF (sequestration on forest land) |

The official NFA uses **time-varying EQFs** computed annually from GAEZ v4 suitability indices. Our static values are an accepted simplification for approximate calculations.

---

## 10. Data File Provenance

Complete mapping from parameter to file on disk:

| File | Downloaded from | Contents | Size |
|------|----------------|----------|------|
| `data/01_cropland/crop_production.csv` | FAOSTAT `Production_Crops_Livestock_E_All_Data_(Normalized).zip` | Crop production (t) and area harvested (ha) by crop group | 15 MB |
| `data/01_cropland/cropland_area.csv` | FAOSTAT `Inputs_LandUse_E_All_Data_(Normalized).zip` | Arable land + Permanent crops area (1000 ha) | 3.6 MB |
| `data/02_grazing/livestock_stocks.csv` | FAOSTAT `Production_Crops_Livestock_E_All_Data_(Normalized).zip` | Livestock head counts by species | 4.8 MB |
| `data/02_grazing/pasture_area.csv` | FAOSTAT `Inputs_LandUse_E_All_Data_(Normalized).zip` | Permanent meadows & pastures (1000 ha) | 1.4 MB |
| `data/02_grazing/gleam_feed_coefficients.csv` | Hard-coded from FAO GLEAM 3.0 documentation | Annual pasture DM demand per animal type | 704 B |
| `data/02_grazing/grassland_npp_reference.csv` | Hard-coded from Monfreda et al. (2008) | World average grassland NPP | 213 B |
| `data/03_forest/timber_production.csv` | FAOSTAT `Forestry_E_All_Data_(Normalized).zip` | Roundwood production (m³) | 11 MB |
| `data/03_forest/forest_area.csv` | FAOSTAT `Inputs_LandUse_E_All_Data_(Normalized).zip` | Forest land area (1000 ha) | 1.5 MB |
| `data/04_fishing/fish_supply_fbs.csv` | FAOSTAT `FoodBalanceSheets_E_All_Data_(Normalized).zip` | Fish production by FBS category (1000 t) | 45 MB |
| `data/04_fishing/ppr_calculation_parameters.csv` | Hard-coded from Pauly & Christensen (1995), Gulland (1971) | TE, discard rate, wet:carbon, MSY, shelf area | 539 B |
| `data/04_fishing/fish_trophic_reference.csv` | Hard-coded from Pauly & Christensen (1995) / FishBase | Species-level trophic levels (20 species) | 1.6 KB |
| `data/05_built_up/built_up_area.csv` | FAOSTAT `Inputs_LandUse_E_All_Data_(Normalized).zip` | Other land + Inland waters (used for residual calc) | 1.6 MB |
| `data/06_carbon/co2_energy_faostat.csv` | FAOSTAT `Emissions_Totals_E_All_Data_(Normalized).zip` | CO₂ from energy sector (kt) | 1.4 MB |
| `data/07_population/population.csv` | FAOSTAT `Population_E_All_Data_(Normalized).zip` | National population (1000 persons) | 13 MB |
| `data/09_factors/equivalence_factors_reference_1999.csv` | Hard-coded from Wackernagel et al. (2002) | 6 EQF values | 388 B |
| `data/10_reference_parameters/carbon_sequestration_parameters.csv` | Hard-coded from Mancini et al. (2016), Khatiwala et al. (2009) | AFCS, ocean CO₂ fraction | 577 B |
| `data/10_reference_parameters/forest_nai_reference.csv` | Hard-coded from UNECE/FAO TBFRA 2000 | World average forest NAI | 193 B |
| `data/10_reference_parameters/ocean_co2_uptake_timeseries.csv` | Hard-coded from Khatiwala et al. (2009) | Ocean CO₂ uptake 1960–2008 (PgC/yr) | 373 B |
| `data/10_reference_parameters/sustainable_catch_by_group.csv` | Hard-coded from Gulland (1971) / FAO | Sustainable catch by species group (14 groups) | 2 KB |
| `data/raw/Inputs_LandUse_E_All_Data_(Normalized).zip` | FAOSTAT bulk download server | Full land-use dataset (all items incl. 6649) | 3 MB |

---

## 11. Full Bibliography of Hard-coded Parameters

1. **Wackernagel, M.**, Schulz, N.B., Deumling, D., Callejas Linares, A., Jenkins, M., Kapos, V., Monfreda, C., Loh, J., Myers, N., Norgaard, R. & Randers, J. (2002). "Tracking the Ecological Overshoot of the Human Economy." *Proceedings of the National Academy of Sciences* 99(14): 9266–9271. doi:10.1073/pnas.142033699
   - **Used for**: All 6 Equivalence Factors (Table 1), ocean CO₂ fraction default (35%).

2. **Monfreda, C.**, Ramankutty, N. & Foley, J.A. (2008). "Farming the planet: 2. Geographic distribution of crop areas, yields, physiological types, and net primary production in the year 2000." *Global Biogeochemical Cycles* 22(1): GB1022. doi:10.1029/2007GB002947
   - **Used for**: Grassland NPP = 2.45 t DM/ha/yr. From SAGE (Center for Sustainability and the Global Environment), University of Wisconsin-Madison.

3. **Mancini, M.S.**, Galli, A., Niccolucci, V., Lin, D., Bastianoni, S., Wackernagel, M. & Marchettini, N. (2016). "Ecological Footprint: Refining the carbon Footprint calculation." *Ecological Indicators* 61: 390–403. doi:10.1016/j.ecolind.2015.09.040
   - **Used for**: AFCS = 0.73 ± 0.37 t C/ha/yr. Weighted average across 26 forest biomes.

4. **Khatiwala, S.**, Primeau, F. & Hall, T. (2009). "Reconstruction of the history of anthropogenic CO₂ concentrations in the ocean." *Nature* 462: 346–349. doi:10.1038/nature08526
   - **Used for**: Ocean CO₂ absorption fraction (28–35% range), ocean uptake time series (1960–2008).

5. **Pauly, D.** & Christensen, V. (1995). "Primary production required to sustain global fisheries." *Nature* 374: 255–257. doi:10.1038/374255a0
   - **Used for**: Transfer efficiency (10.13%), discard rate (1.27), trophic level methodology. Also underpins the species-level TL values from FishBase.

6. **Gulland, J.A.** (1971). *The Fish Resources of the Ocean*. Fishing News Books, West Byfleet, UK.
   - **Used for**: Maximum sustainable yield = 93 million tonnes/yr (global marine capture).

7. **UNECE/FAO** (2000). *Temperate and Boreal Forest Resource Assessment 2000* (TBFRA-2000). United Nations Economic Commission for Europe / Food and Agriculture Organization.
   - **Used for**: World average forest NAI = 1.81 m³/ha/yr. Combined with FAO GFSM (1998) for tropical forests.

8. **FAO GLEAM 3.0** — Global Livestock Environmental Assessment Model. Food and Agriculture Organization of the United Nations. https://www.fao.org/gleam/en/
   - **Used for**: Annual pasture dry matter demand per head for cattle (dairy/beef), buffalo, sheep, goats, pigs, and chickens.

9. **FishBase** — Froese, R. & Pauly, D. (eds.) (2024). FishBase. World Wide Web electronic publication. www.fishbase.org
   - **Used for**: Species-level trophic levels used to derive FBS category averages.

10. **Sea Around Us** — Pauly, D. & Zeller, D. (eds.) (2015). Sea Around Us Concepts, Design and Data. www.seaaroundus.org
    - **Used for**: Wet weight to carbon ratio (9:1), continental shelf area (~2 billion ha).
