# Ecological Overshoot Calculator

Computes the **Ecological Footprint** and **Biocapacity** for ~234 countries
over a 10-year window (2014-2023), following the
[National Footprint Accounts](https://www.footprintnetwork.org/) methodology.

Outputs a single country-level CSV and a global summary CSV with metrics
including Number of Earths and Earth Overshoot Day.

## Quick start

```bash
git clone <repo-url> && cd earthovershoot01

# Install deps + download ~400 MB of FAOSTAT data
./setup.sh

# Run the calculator
python3 scripts/calculate_overshoot.py
```

Output:
- `data/overshoot_results.csv` &mdash; per-country, per-year results
- `data/overshoot_global_summary.csv` &mdash; world totals by year

### Faster setup (skip large trade file)

```bash
./setup.sh --skip-trade      # saves ~265 MB; trade data not used by calculator
./setup.sh --quick            # also skips food balance sheets
```

## Project structure

```
earthovershoot01/
├── setup.sh                       # Bootstrap: install deps + fetch data
├── requirements.txt               # Python dependencies
├── README.md
│
├── scripts/
│   ├── fetch_footprint_data.py    # Downloads all FAOSTAT bulk data
│   ├── calculate_overshoot.py     # Main calculation script
│   ├── convert_to_md.sh           # PDF/EPUB → Markdown converter
│   └── data_sources.csv           # Registry of all data sources
│
├── data/
│   ├── 01_cropland/               # Crop production + cropland area
│   ├── 02_grazing/                # Livestock stocks + pasture area + GLEAM coefficients
│   ├── 03_forest/                 # Timber production + forest area
│   ├── 04_fishing/                # Fish FBS + trophic/PPR parameters
│   ├── 05_built_up/               # Built-up land area
│   ├── 06_carbon/                 # CO2 emissions (energy sector)
│   ├── 07_population/             # Population by country
│   ├── 08_trade/                  # Import/export (not yet used)
│   ├── 09_factors/                # Equivalence factors (EQF)
│   ├── 10_reference_parameters/   # Sequestration rates, NAI, PPR params
│   ├── raw/                       # Cached FAOSTAT ZIP downloads
│   ├── overshoot_results.csv      # ← generated output
│   └── overshoot_global_summary.csv
│
└── references/                    # Research PDFs/EPUBs (not in git)
    └── md_output/                 # Converted markdown (not in git)
```

**Git tracks:** scripts, reference parameters, READMEs, `.gitignore`,
`setup.sh`, `requirements.txt`.

**Git ignores:** all bulk CSV data, raw ZIPs, PDFs, generated outputs.
Run `./setup.sh` after cloning to fetch everything.

## Methodology

The calculator implements six footprint components:

| Component | Ecological Footprint (demand) | Biocapacity (supply) | EQF |
|-----------|-------------------------------|----------------------|-----|
| **Cropland** | Production / world yield per crop | Cropland area x yield factor | 2.1 |
| **Grazing** | Livestock heads x pasture DM demand / grassland NPP | Pasture area | 0.5 |
| **Forest** | Roundwood production / Net Annual Increment | Forest area | 1.3 |
| **Fishing** | Primary Production Required (PPR) / marine yield | Shelf area x catch share | 0.4 |
| **Built-up** | Built-up land area (= biocapacity) | Same as footprint | 2.2 |
| **Carbon** | CO2 x (1-ocean fraction) / sequestration rate | (included in forest BC) | 1.3 |

**Key constants:**
- Forest NAI: 1.81 m3/ha/yr
- Carbon sequestration (AFCS): 0.73 t C/ha/yr
- Ocean CO2 absorption: 35%
- Grassland NPP: 2.45 t DM/ha/yr
- Trophic transfer efficiency: 10.13%
- Continental shelf: 2 billion ha

### Output columns

**Country-level** (`overshoot_results.csv`):

| Column | Description |
|--------|-------------|
| `area_code`, `area` | FAOSTAT country code and name |
| `year` | 2014-2023 |
| `ef_*_gha` | Ecological Footprint by component (global hectares) |
| `ef_total_gha` | Sum of 6 EF components |
| `bc_*_gha` | Biocapacity by component |
| `bc_total_gha` | Sum of 5 BC components |
| `ecological_deficit_gha` | BC - EF (negative = deficit) |
| `population` | In thousands |
| `ef_per_capita_gha` | Total EF / population |
| `bc_per_capita_gha` | Total BC / population |

**Global summary** (`overshoot_global_summary.csv`):

| Column | Description |
|--------|-------------|
| `year` | 2014-2023 |
| `world_ef_gha` | World total Ecological Footprint |
| `world_bc_gha` | World total Biocapacity |
| `overshoot_gha` | EF - BC |
| `number_of_earths` | EF / BC |
| `overshoot_day` | Day of year (365 x BC/EF) |

## Data sources

All data is downloaded automatically by `scripts/fetch_footprint_data.py`:

| Source | Domain | Size |
|--------|--------|------|
| FAOSTAT Production (QCL) | Crops, livestock | ~34 MB |
| FAOSTAT Land Use (RL) | Area by use type | ~3 MB |
| FAOSTAT Forestry (FO) | Roundwood, forest area | ~18 MB |
| FAOSTAT Food Balance (FBS) | Fish supply | ~55 MB |
| FAOSTAT Emissions (GT) | CO2 from energy | ~21 MB |
| FAOSTAT Population (OA) | National population | ~2 MB |
| FAOSTAT Trade (TCL) | Import/export | ~265 MB |
| World Bank API | Population cross-check | <1 MB |
| Literature | EQFs, AFCS, NAI, NPP, PPR | <1 KB |

See `scripts/data_sources.csv` for the full registry of 30+ source datasets.

## Limitations

This is a simplified implementation. Differences from the official
Global Footprint Network accounts include:

- **Production-based only** &mdash; no trade adjustment (consumption = production + imports - exports). This means exporting countries are overcharged and importing countries undercharged.
- **Static equivalence factors** from 1999 (Wackernagel et al. 2002). The official NFA uses time-varying EQFs derived from GAEZ suitability indices.
- **Simplified yield factors** &mdash; YF=1.0 for grazing, forest, and fishing (cropland YF is computed from data). The official NFA computes country-specific YFs annually.
- **Built-up area estimated** from land-use residuals or 3% of cropland where direct data is unavailable.
- **CO2 data** uses FAOSTAT energy emissions rather than the IEA dataset used by GFN.

Expected results: Number of Earths ~2.0 (vs official ~1.7), Overshoot Day ~late June (vs official ~late July).

## References

Key papers (place PDFs in `references/` — not tracked by git):

- Wackernagel et al. (2002). "Tracking the Ecological Overshoot of the Human Economy." *PNAS* 99(14): 9266-9271.
- Borucke et al. (2013). "Accounting for demand and supply of the biosphere's regenerative capacity." *Ecological Indicators* 24: 518-533.
- Monfreda et al. (2008). "Farming the planet." *Global Biogeochemical Cycles*.
- Mancini et al. (2016). "Ecological Footprint: Refining the carbon Footprint calculation." *Ecological Indicators*.
- Pauly & Christensen (1995). "Primary production required to sustain global fisheries." *Nature*.

## License

Data sourced from FAOSTAT is subject to
[FAO terms of use](https://www.fao.org/contact-us/terms/en/).
