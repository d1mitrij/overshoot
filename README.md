# Ecological Overshoot Calculator

Computes the **Ecological Footprint** and **Biocapacity** for 234 countries
over a 10-year window (2014--2023), following the
[National Footprint Accounts](https://www.footprintnetwork.org/) methodology
(Wackernagel et al. 2002; Borucke et al. 2013).

Produces two CSV outputs with metrics including per-country ecological
deficit, Number of Earths, and Earth Overshoot Day.

## Latest results (2023)

| Metric | Value |
|--------|-------|
| World Ecological Footprint | 24.56 billion gha |
| World Biocapacity | 11.84 billion gha |
| Overshoot | 12.71 billion gha |
| Number of Earths | **2.07** |
| Overshoot Day | **June 25** (day 176) |

### World component breakdown (2023)

| Component | Footprint (bn gha) | Biocapacity (bn gha) |
|-----------|--------------------:|---------------------:|
| Cropland | 3.22 | 3.40 |
| Grazing | 1.18 | 1.81 |
| Forest products | 3.01 | 5.70 |
| Fishing grounds | 2.32 | 0.80 |
| Built-up land | 0.14 | 0.14 |
| Carbon | 14.68 | *(absorbed by forest BC)* |
| **Total** | **24.56** | **11.84** |

Carbon emissions account for 60% of the total footprint.

### Overshoot Day trend

| Year | Number of Earths | Overshoot Day |
|------|-----------------|---------------|
| 2014 | 1.91 | July 9 |
| 2016 | 1.93 | July 7 |
| 2018 | 1.99 | July 2 |
| 2020 | 1.96 | July 4 |
| 2022 | 2.05 | June 26 |
| 2023 | 2.07 | June 25 |

### Spot checks (2023, per capita gha)

| Country | EF/cap | BC/cap | Deficit/cap |
|---------|-------:|-------:|------------:|
| USA | 6.51 | 2.70 | -3.81 |
| China | 3.38 | 0.83 | -2.55 |
| India | 1.01 | 0.44 | -0.57 |
| Brazil | 3.02 | 8.38 | +5.36 |

---

## Quick start

```bash
git clone https://github.com/d1mitrij/overshoot.git && cd overshoot
git checkout dima

# Install Python deps + download ~400 MB of FAOSTAT data
./setup.sh

# Run the calculator
python3 scripts/calculate_overshoot.py
```

Output files:
- `data/overshoot_results.csv` -- 2,340 rows (234 countries x 10 years)
- `data/overshoot_global_summary.csv` -- 10 rows (annual world totals)

### Faster setup

```bash
./setup.sh --skip-trade      # saves ~265 MB; trade data not used by calculator
./setup.sh --quick            # also skips food balance sheets
```

### Requirements

- Python 3.8+
- `pandas`, `numpy`, `requests` (installed by `setup.sh`)

---

## Project structure

```
overshoot/
├── setup.sh                         Bootstrap: install deps + fetch data
├── requirements.txt                 Python dependencies
├── README.md
│
├── scripts/
│   ├── fetch_footprint_data.py      Downloads all FAOSTAT bulk data (~400 MB)
│   ├── calculate_overshoot.py       Main calculation engine (vectorized)
│   ├── convert_to_md.sh             PDF/EPUB to Markdown converter
│   └── data_sources.csv             Registry of 30+ data source URLs
│
├── data/                            Created by setup.sh / fetch script
│   ├── 01_cropland/                 Crop production + cropland area
│   ├── 02_grazing/                  Livestock stocks, pasture, GLEAM coefficients
│   ├── 03_forest/                   Timber production + forest area
│   ├── 04_fishing/                  Fish food balance sheets, trophic/PPR params
│   ├── 05_built_up/                 Built-up land area (from land-use residual)
│   ├── 06_carbon/                   CO2 emissions (energy sector)
│   ├── 07_population/               National population (FAOSTAT + World Bank)
│   ├── 08_trade/                    Import/export (reserved for future use)
│   ├── 09_factors/                  Equivalence factors (EQF, static 1999)
│   ├── 10_reference_parameters/     AFCS, NAI, PPR, ocean CO2, grassland NPP
│   └── raw/                         Cached FAOSTAT ZIP downloads
│
└── references/                      Research papers (not in git)
    └── md_output/                   Converted markdown versions
```

### What git tracks vs. fetches

| Tracked in git | Fetched by `setup.sh` |
|----------------|----------------------|
| All scripts (`scripts/`) | Raw FAOSTAT ZIPs (`data/raw/`) |
| Reference parameters (<10 KB each) | Bulk CSVs (crop, livestock, forest, fish, CO2, pop, trade) |
| Data directory READMEs | Generated output CSVs |
| `setup.sh`, `requirements.txt` | |
| `.gitignore`, `README.md` | |

PDFs, EPUBs, and databases are **never stored in git**. Research
documents go in `references/` locally.

---

## Methodology

### The Ecological Footprint framework

The Ecological Footprint measures how much biologically productive land
and water area a population requires to produce the resources it consumes
and to absorb the waste it generates, measured in **global hectares** (gha).

**Biocapacity** measures the capacity of ecosystems to regenerate.
When a population's Footprint exceeds available Biocapacity, it is in
**ecological deficit** (overshoot).

### Six footprint components

| # | Component | Ecological Footprint (demand) | Biocapacity (supply) | EQF |
|---|-----------|-------------------------------|----------------------|-----|
| 1 | **Cropland** | `sum(Production_t / WorldYield_t_ha) x EQF` | `CroplandArea_ha x YieldFactor x EQF` | 2.1 |
| 2 | **Grazing** | `sum(LivestockHeads x PastureDemand_t) / GrasslandNPP x EQF` | `PastureArea_ha x EQF` | 0.5 |
| 3 | **Forest** | `RoundwoodProduction_m3 / NAI x EQF` | `ForestArea_ha x EQF` | 1.3 |
| 4 | **Fishing** | `PPR / MarineYield x EQF` (trophic-level method) | `ShelfArea x CatchShare x EQF` | 0.4 |
| 5 | **Built-up** | `BuiltUpArea_ha x EQF` (= biocapacity) | Same as footprint | 2.2 |
| 6 | **Carbon** | `CO2_t x (1 - OceanFrac) / SeqRate x EQF` | *(included in forest BC)* | 1.3 |

### Key constants and their sources

| Parameter | Value | Unit | Source |
|-----------|------:|------|--------|
| Forest NAI | 1.81 | m3/ha/yr | UNECE/FAO TBFRA 2000 |
| Carbon sequestration (AFCS) | 0.73 | t C/ha/yr | Mancini et al. 2016 |
| Ocean CO2 absorption | 35% | fraction | Khatiwala et al. 2009 |
| Grassland NPP | 2.45 | t DM/ha/yr | Monfreda et al. 2008 |
| Trophic transfer efficiency | 10.13% | fraction | Pauly & Christensen 1995 |
| Discard rate | 1.27 | ratio | Pauly & Christensen 1995 |
| Continental shelf area | 2.0 x 10^9 | ha | Various oceanographic |
| Sustainable global catch | 93 | Mt/yr | Gulland 1971 / FAO |

### Fishing grounds: PPR method

The fishing footprint uses the **Primary Production Required** (PPR)
approach to convert fish catch into the marine area needed to sustain it:

```
PPR = Catch_t x DiscardRate x (1/TE)^(TL-1) / WetToCarbon
EF  = PPR / MarineYieldPerHa x EQF_fishing
```

Each FBS fish category is assigned an average trophic level:

| FBS Category | Trophic Level |
|-------------|:------------:|
| Freshwater Fish | 2.5 |
| Demersal Fish | 3.8 |
| Pelagic Fish | 3.0 |
| Marine Fish, Other | 3.2 |
| Crustaceans | 2.5 |
| Cephalopods | 3.5 |
| Molluscs, Other | 2.1 |

### Built-up land estimation

Direct built-up area data is sparse in FAOSTAT. The calculator uses a
three-tier fallback:

1. **FAOSTAT item 6649** (Farm buildings & Farmyards) -- available for ~36 countries
2. **Land-use residual** -- `LandArea - AgLand - Forest - OtherLand - InlandWaters` -- used where positive
3. **3% of cropland area** -- proxy for remaining countries

### Carbon footprint

```
CO2_net = CO2_energy_kt x 1000 x (1 - 0.35)        # 35% absorbed by oceans
SeqRate = AFCS x (44/12)                            # convert t C to t CO2
EF_carbon = CO2_net / SeqRate x EQF_forest           # forest area equivalent
```

---

## Output schema

### Country-level: `overshoot_results.csv`

| Column | Type | Description |
|--------|------|-------------|
| `area_code` | int | FAOSTAT country code |
| `area` | str | Country name |
| `year` | int | 2014--2023 |
| `ef_cropland_gha` | float | Cropland footprint (global hectares) |
| `ef_grazing_gha` | float | Grazing land footprint |
| `ef_forest_gha` | float | Forest product footprint |
| `ef_fishing_gha` | float | Fishing grounds footprint |
| `ef_built_up_gha` | float | Built-up land footprint |
| `ef_carbon_gha` | float | Carbon footprint |
| `ef_total_gha` | float | Sum of 6 EF components |
| `bc_cropland_gha` | float | Cropland biocapacity |
| `bc_grazing_gha` | float | Grazing land biocapacity |
| `bc_forest_gha` | float | Forest biocapacity |
| `bc_fishing_gha` | float | Fishing grounds biocapacity |
| `bc_built_up_gha` | float | Built-up land biocapacity |
| `bc_total_gha` | float | Sum of 5 BC components |
| `ecological_deficit_gha` | float | BC - EF (negative = deficit) |
| `population` | float | Population in thousands |
| `ef_per_capita_gha` | float | EF total / population |
| `bc_per_capita_gha` | float | BC total / population |

### Global summary: `overshoot_global_summary.csv`

| Column | Type | Description |
|--------|------|-------------|
| `year` | int | 2014--2023 |
| `world_ef_gha` | float | World total Ecological Footprint |
| `world_bc_gha` | float | World total Biocapacity |
| `overshoot_gha` | float | EF - BC |
| `number_of_earths` | float | EF / BC |
| `overshoot_day` | int | Day of year when year's BC is used up (365 x BC/EF) |

---

## Data sources

All bulk data is downloaded automatically by `scripts/fetch_footprint_data.py`
from public FAOSTAT endpoints. No API keys required.

| Source | FAOSTAT Domain | What it provides | Download size |
|--------|---------------|------------------|--------------|
| Production (QCL) | Crops & livestock | Crop production, area harvested, livestock stocks | ~34 MB |
| Land Use (RL) | Inputs | Cropland, pasture, forest, other land area | ~3 MB |
| Forestry (FO) | Forestry | Roundwood production, forest area | ~18 MB |
| Food Balance (FBS) | Food Balance Sheets | Fish production by category | ~55 MB |
| Emissions (GT) | Emissions Totals | CO2 from energy sector | ~21 MB |
| Population (OA) | Population | National population estimates | ~2 MB |
| Trade (TCL) | Trade | Import/export volumes | ~265 MB |

Additional sources (embedded as reference parameter CSVs):
- FAO GLEAM 3.0 -- livestock feed coefficients
- Pauly & Christensen 1995 -- PPR / trophic parameters
- Wackernagel et al. 2002 -- equivalence factors
- Mancini et al. 2016 -- carbon sequestration rate
- Khatiwala et al. 2009 -- ocean CO2 uptake
- Monfreda et al. 2008 -- grassland NPP
- UNECE/FAO TBFRA 2000 -- forest Net Annual Increment
- Gulland 1971 -- sustainable marine catch reference

See `scripts/data_sources.csv` for the complete registry of 30+ datasets.

---

## Limitations and known differences from GFN

This is a simplified, open-source implementation. Key differences from the
official [Global Footprint Network](https://www.footprintnetwork.org/)
National Footprint Accounts:

| Factor | This calculator | Official NFA |
|--------|----------------|-------------|
| **Accounting basis** | Production-based | Consumption-based (production + imports - exports) |
| **Equivalence factors** | Static 1999 values | Time-varying, from GAEZ suitability indices |
| **Yield factors** | YF=1.0 for grazing/forest/fishing; computed for cropland | Country-specific, annually updated |
| **Built-up area** | Estimated (residual / proxy) | GHSL satellite data |
| **CO2 source** | FAOSTAT energy emissions | IEA energy CO2 |
| **Trade adjustment** | None | Full MRIO / commodity-flow trade matrix |

### Impact on results

- **Number of Earths ~2.07** vs GFN's ~1.7 -- the production-based approach
  double-counts resources that are exported (counted in producing country
  but also consumed in importing country). The carbon footprint is also
  slightly higher due to the FAOSTAT energy dataset.
- **Overshoot Day ~June 25** vs GFN's ~July 28 -- follows from the above.
- **Per-capita rankings differ** -- e.g. small island nations with large
  fisheries (Iceland, Nauru) show very high footprints because their
  production is export-oriented but counted locally.

---

## References

Key literature (place PDFs in `references/` -- not tracked in git):

1. Wackernagel, M. et al. (2002). "Tracking the Ecological Overshoot of the Human Economy." *Proceedings of the National Academy of Sciences* 99(14): 9266--9271.
2. Borucke, M. et al. (2013). "Accounting for demand and supply of the biosphere's regenerative capacity: The National Footprint Accounts' underlying methodology and framework." *Ecological Indicators* 24: 518--533.
3. Monfreda, C. et al. (2008). "Farming the planet: Geographic distribution of crop areas, yields, physiological types, and net primary production in the year 2000." *Global Biogeochemical Cycles* 22(1).
4. Mancini, M.S. et al. (2016). "Ecological Footprint: Refining the carbon Footprint calculation." *Ecological Indicators* 61: 390--403.
5. Pauly, D. & Christensen, V. (1995). "Primary production required to sustain global fisheries." *Nature* 374: 255--257.
6. Khatiwala, S. et al. (2009). "Reconstruction of the history of anthropogenic CO2 concentrations in the ocean." *Nature* 462: 346--349.
7. Gulland, J.A. (1971). *The Fish Resources of the Ocean*. Fishing News Books.

---

## License

Data sourced from FAOSTAT is subject to the
[FAO Open Data Licensing](https://www.fao.org/contact-us/terms/en/)
(CC BY-NC-SA 3.0 IGO).
