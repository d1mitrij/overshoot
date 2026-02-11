#!/usr/bin/env python3
"""
fetch_footprint_data.py

Downloads input data for the Ecological Footprint / Overshoot formula.

Formula
-------
  Ecological Footprint = Σ (P_i × YF_i × EF_i)   for 6 land-use types
  Biocapacity          = Σ (A_i × YF_i × EF_i)   for available productive area
  Overshoot            = Footprint − Biocapacity

  where P = physical hectares, YF = yield factor, EF = equivalence factor,
  A = available bioproductive area, and i ∈ {cropland, grazing, forest,
  fishing, built-up, carbon}.

Sources
-------
  Automated:
    - FAOSTAT bulk downloads  (land use, production, forestry, population,
                                emissions, trade, food balance sheets)
    - World Bank API           (population cross-check)
    - FishBase API             (trophic levels for commercial fish species)
    - Sea Around Us API        (global catch & stock status)
    - FAO GLEAM coefficients   (livestock feed requirements, global averages)
    - Literature constants     (AFCS, ocean CO₂, forest NAI, grassland NPP,
                                PPR parameters, sustainable catch reference)

  Manual download required (for full NFA-grade accuracy):
    - GAEZ v4   (suitability indexes for time-varying EQFs)
    - GFN       (pre-computed yield/equivalence factors by year)
    - GLASOD    (soil degradation → biocapacity loss)
    - GHSL      (satellite built-up area)
    - IEA       (detailed energy-sector CO₂, requires license)
    - GTAP      (multi-region input-output tables, requires license)
    - FAO GLEAM (detailed regional feed coefficients)
    - FAO SOFIA (fisheries stock status reports)

Usage
-----
  python3 fetch_footprint_data.py
  python3 fetch_footprint_data.py --skip-trade          # skip 265 MB trade file
  python3 fetch_footprint_data.py --skip-food-balance    # skip 52 MB FBS file
  python3 fetch_footprint_data.py --redownload           # ignore cached ZIPs
"""

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' required.  pip install requests")

try:
    import pandas as pd
except ImportError:
    sys.exit("ERROR: 'pandas' required.  pip install pandas")

# ═══════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════
BASE_DIR      = Path(__file__).resolve().parent.parent  # project root
DATA_DIR      = BASE_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"

PARAM_DIRS = {
    "cropland":   DATA_DIR / "01_cropland",
    "grazing":    DATA_DIR / "02_grazing",
    "forest":     DATA_DIR / "03_forest",
    "fishing":    DATA_DIR / "04_fishing",
    "built_up":   DATA_DIR / "05_built_up",
    "carbon":     DATA_DIR / "06_carbon",
    "population": DATA_DIR / "07_population",
    "trade":      DATA_DIR / "08_trade",
    "factors":    DATA_DIR / "09_factors",
    "reference":  DATA_DIR / "10_reference_parameters",
}

# ═══════════════════════════════════════════════════════════════════════
# FAOSTAT bulk-download catalogue
# ═══════════════════════════════════════════════════════════════════════
FAOSTAT_BULK = "https://fenixservices.fao.org/faostat/static/bulkdownloads"

FAOSTAT_FILES = {
    "land_use": {
        "filename": "Inputs_LandUse_E_All_Data_(Normalized).zip",
        "size_hint": "~3 MB",
        "description": "Land area by use type (cropland, pasture, forest, built-up)",
    },
    "production": {
        "filename": "Production_Crops_Livestock_E_All_Data_(Normalized).zip",
        "size_hint": "~32 MB",
        "description": "Crop production, yields, livestock stocks",
    },
    "forestry": {
        "filename": "Forestry_E_All_Data_(Normalized).zip",
        "size_hint": "~17 MB",
        "description": "Timber, roundwood, fuelwood production",
    },
    "population": {
        "filename": "Population_E_All_Data_(Normalized).zip",
        "size_hint": "~1.5 MB",
        "description": "Annual population by country",
    },
    "emissions": {
        "filename": "Emissions_Totals_E_All_Data_(Normalized).zip",
        "size_hint": "~20 MB",
        "description": "Agricultural GHG emissions by country",
    },
    "trade": {
        "filename": "Trade_CropsLivestock_E_All_Data_(Normalized).zip",
        "size_hint": "~265 MB",
        "description": "Import/export of crops and livestock products",
    },
    "food_balance": {
        "filename": "FoodBalanceSheets_E_All_Data_(Normalized).zip",
        "size_hint": "~52 MB",
        "description": "Food supply, domestic utilisation, fish supply",
    },
}

# World Bank indicator API (free, no key required)
WB_API = "https://api.worldbank.org/v2"

# FishBase REST API (public, no key required)
FISHBASE_API = "https://fishbase.ropensci.org"

# Sea Around Us API (public)
SAU_API = "https://api.seaaroundus.org/api/v1"

# FAO GLEAM data (model documentation PDFs + parameter tables)
GLEAM_BASE = "https://www.fao.org/gleam/resources/en/"

# ═══════════════════════════════════════════════════════════════════════
# Reference constants from literature
# ═══════════════════════════════════════════════════════════════════════

# Average Forest-Carbon Sequestration (Mancini et al., used in NFA 2016+)
AFCS_TC_PER_HA_YR = 0.73          # tonnes C / ha / year
AFCS_UNCERTAINTY  = 0.37           # ± tonnes C / ha / year

# Ocean CO₂ absorption (Khatiwala et al. 2009; range over 1961-2008)
OCEAN_CO2_FRACTION_MIN = 0.28      # 28%
OCEAN_CO2_FRACTION_MAX = 0.35      # 35%
OCEAN_CO2_FRACTION_DEFAULT = 0.35  # commonly used constant

# World-average forest Net Annual Increment (UNECE/FAO TBFRA 2000)
FOREST_NAI_M3_PER_HA_YR = 1.81    # m³ harvestable wood / ha / year

# Grassland NPP (Monfreda et al. 2008, SAGE)
GRASSLAND_NPP_T_DM_PER_HA_YR = 2.45  # tonnes dry matter / ha / year

# Fishing parameters (Pauly & Christensen 1995)
FISH_TRANSFER_EFFICIENCY = 0.1013  # 10.13% between trophic levels
FISH_DISCARD_RATE = 1.27           # 1.27 = 0.27 tonnes bycatch per tonne
FISH_WET_WEIGHT_TO_CARBON = 9.0    # 9:1 wet weight to carbon ratio
FISH_SUSTAINABLE_CATCH_MT = 93.0   # Gulland 1971: 93 million tonnes/year
CONTINENTAL_SHELF_AREA_HA = 2.0e9  # ~2 billion ha marine shelf

# Key livestock species for GLEAM feed coefficients
# Dry matter intake (kg DM/head/day) – approximate global averages from GLEAM 3.0
GLEAM_FEED_COEFFICIENTS = {
    "Cattle (dairy)":    {"total_dmi_kg_day": 14.5, "pasture_fraction": 0.45,
                          "crop_fraction": 0.30, "residue_fraction": 0.25},
    "Cattle (beef)":     {"total_dmi_kg_day": 9.8,  "pasture_fraction": 0.65,
                          "crop_fraction": 0.15, "residue_fraction": 0.20},
    "Buffalo":           {"total_dmi_kg_day": 12.0, "pasture_fraction": 0.55,
                          "crop_fraction": 0.20, "residue_fraction": 0.25},
    "Sheep":             {"total_dmi_kg_day": 1.8,  "pasture_fraction": 0.70,
                          "crop_fraction": 0.10, "residue_fraction": 0.20},
    "Goats":             {"total_dmi_kg_day": 1.5,  "pasture_fraction": 0.72,
                          "crop_fraction": 0.08, "residue_fraction": 0.20},
    "Pigs":              {"total_dmi_kg_day": 2.5,  "pasture_fraction": 0.00,
                          "crop_fraction": 0.75, "residue_fraction": 0.25},
    "Chickens (layers)": {"total_dmi_kg_day": 0.12, "pasture_fraction": 0.00,
                          "crop_fraction": 0.90, "residue_fraction": 0.10},
    "Chickens (broilers)": {"total_dmi_kg_day": 0.10, "pasture_fraction": 0.00,
                            "crop_fraction": 0.90, "residue_fraction": 0.10},
}

# Major fish species/groups with trophic levels (FishBase / Pauly & Christensen)
FISH_TROPHIC_LEVELS = {
    "Anchoveta":                   {"trophic_level": 2.7, "species_group": "Small pelagics"},
    "Atlantic herring":            {"trophic_level": 3.2, "species_group": "Small pelagics"},
    "Skipjack tuna":               {"trophic_level": 3.8, "species_group": "Tunas"},
    "Atlantic cod":                {"trophic_level": 4.0, "species_group": "Demersal"},
    "Alaska pollock":              {"trophic_level": 3.5, "species_group": "Demersal"},
    "Blue whiting":                {"trophic_level": 3.6, "species_group": "Small pelagics"},
    "Yellowfin tuna":              {"trophic_level": 4.3, "species_group": "Tunas"},
    "European pilchard (sardine)": {"trophic_level": 2.7, "species_group": "Small pelagics"},
    "Japanese anchovy":            {"trophic_level": 3.1, "species_group": "Small pelagics"},
    "Largehead hairtail":          {"trophic_level": 4.0, "species_group": "Demersal"},
    "Atlantic mackerel":           {"trophic_level": 3.2, "species_group": "Small pelagics"},
    "Chub mackerel":               {"trophic_level": 3.2, "species_group": "Small pelagics"},
    "Pacific saury":               {"trophic_level": 3.1, "species_group": "Small pelagics"},
    "Bigeye tuna":                 {"trophic_level": 4.5, "species_group": "Tunas"},
    "Chilean jack mackerel":       {"trophic_level": 3.5, "species_group": "Small pelagics"},
    "European sprat":              {"trophic_level": 3.0, "species_group": "Small pelagics"},
    "Nile tilapia":                {"trophic_level": 2.0, "species_group": "Freshwater"},
    "Catla":                       {"trophic_level": 2.5, "species_group": "Freshwater"},
    "Common carp":                 {"trophic_level": 2.9, "species_group": "Freshwater"},
    "Shrimp (various)":            {"trophic_level": 2.5, "species_group": "Crustaceans"},
}

# ═══════════════════════════════════════════════════════════════════════
# FAOSTAT codes – items and elements used by the formula
# ═══════════════════════════════════════════════════════════════════════

# -- Land-Use domain (RL) --
# Element 5110 = Area (1000 ha)
LAND_USE_ITEMS = {
    6621: "Arable land",
    6650: "Land under perm. crops",
    6610: "Cropland",                       # = 6621 + 6650
    6655: "Permanent meadows and pastures",
    6661: "Forest land",
    6600: "Country area",
    6670: "Land area",
    # Built-up: item code varies by edition; we also search by name
}

# -- Production domain (QCL) --
# Crop aggregates
CROP_ITEMS = {
    1717: "Cereals, Total",
    1720: "Roots and Tubers, Total",
    1726: "Pulses, Total",
    1732: "Treenuts, Total",
    1735: "Oil Crops, Primary",
    1738: "Vegetables, Primary",
    1753: "Fruit, Primary",
    2555: "Sugar crops, primary",
    2562: "Fibre crops, primary",
}
CROP_ELEMENTS = {
    5312: "Area harvested",       # ha
    5510: "Production",           # tonnes
    5419: "Yield",                # hg/ha  (hectograms per hectare)
}

# Livestock stocks
LIVESTOCK_ITEMS = {
    866:  "Cattle and Buffaloes",
    976:  "Sheep",
    1016: "Goats",
    946:  "Horses",
    1126: "Camels",
    1057: "Chickens",
    1068: "Ducks",
    1034: "Pigs",
}
LIVESTOCK_ELEMENTS = {
    5111: "Stocks",               # Head (1000 head for some)
    5313: "Producing Animals/Slaughtered",
}

# -- Forestry domain (FO) --
FORESTRY_ITEMS = {
    1861: "Roundwood",
    1862: "Industrial roundwood, coniferous",
    1863: "Industrial roundwood, non-coniferous",
    1864: "Sawnwood",
    1866: "Wood fuel",
}
FORESTRY_ELEMENTS = {
    5516: "Production",           # m³
    5622: "Import Quantity",
    5922: "Export Quantity",
}

# -- Trade domain (TCL) --
TRADE_ELEMENTS = {
    5610: "Import Quantity",      # tonnes
    5910: "Export Quantity",      # tonnes
    5622: "Import Value",         # 1000 US$
    5922: "Export Value",         # 1000 US$
}

# ═══════════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("footprint")

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "EcologicalFootprintFetcher/1.0"})

REQUEST_DELAY = 1.0        # politeness delay between calls (seconds)
TIMEOUT       = 300        # per-request timeout (seconds)
MAX_RETRIES   = 3


def _download(url: str, dest: Path, description: str = "") -> bool:
    """Download a file with retries and progress indication."""
    if dest.exists():
        log.info("  cached: %s (%s)", dest.name,
                 _human_size(dest.stat().st_size))
        return True

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("  downloading %s (attempt %d/%d) ...",
                     description or dest.name, attempt, MAX_RETRIES)
            r = SESSION.get(url, timeout=TIMEOUT, stream=True)
            r.raise_for_status()

            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r    {pct:3d}% of {_human_size(total)}",
                              end="", flush=True)
            if total:
                print()
            log.info("  saved: %s (%s)", dest.name,
                     _human_size(dest.stat().st_size))
            return True

        except Exception as exc:
            log.warning("  attempt %d failed: %s", attempt, exc)
            if dest.exists():
                dest.unlink()
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY * attempt)

    log.error("  FAILED after %d attempts: %s", MAX_RETRIES, url)
    return False


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def _read_faostat_zip(zip_path: Path, encoding: str = "latin-1") -> pd.DataFrame:
    """Read the normalised CSV inside a FAOSTAT bulk-download ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV found in {zip_path.name}")
        # pick the normalised one if multiple files exist
        target = csv_names[0]
        for n in csv_names:
            if "Normalized" in n or "normalized" in n:
                target = n
                break
        log.info("  reading %s from %s", target, zip_path.name)
        with zf.open(target) as f:
            df = pd.read_csv(
                io.TextIOWrapper(f, encoding=encoding),
                low_memory=False,
            )
    return df


def _save(df: pd.DataFrame, path: Path, description: str = ""):
    """Save a DataFrame to CSV and log it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("  -> %s  (%d rows) %s", path.relative_to(BASE_DIR),
             len(df), description)


def _write_readme(directory: Path, lines: list[str]):
    """Write a README.txt in the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "README.txt").write_text("\n".join(lines) + "\n")


# ═══════════════════════════════════════════════════════════════════════
# 1. FAOSTAT bulk downloads
# ═══════════════════════════════════════════════════════════════════════

def download_faostat(keys: list[str], redownload: bool = False) -> dict[str, Path]:
    """Download requested FAOSTAT bulk ZIPs.  Returns {key: zip_path}."""
    log.info("=== Downloading FAOSTAT bulk files ===")
    result = {}
    for key in keys:
        meta = FAOSTAT_FILES[key]
        url = f"{FAOSTAT_BULK}/{meta['filename']}"
        dest = RAW_DIR / meta["filename"]
        if redownload and dest.exists():
            dest.unlink()
        ok = _download(url, dest, f"{key} ({meta['size_hint']})")
        if ok:
            result[key] = dest
    return result


# ═══════════════════════════════════════════════════════════════════════
# 2. Process each formula parameter
# ═══════════════════════════════════════════════════════════════════════

# ── P_cropland : cropland area, crop production, yields ───────────────
def process_cropland(zips: dict[str, Path]):
    log.info("=== Processing: CROPLAND (P_cropland, Yield_cropland) ===")
    out = PARAM_DIRS["cropland"]

    # --- Land area ---
    if "land_use" in zips:
        df = _read_faostat_zip(zips["land_use"])
        cropland_items = [6621, 6650, 6610]  # arable, perm crops, cropland
        mask = (
            df["Item Code"].isin(cropland_items)
            & (df["Element Code"] == 5110)
        )
        crop_area = df.loc[mask].copy()
        if crop_area.empty:
            # try matching by name
            mask = (
                df["Item"].str.contains("rable|ropland|ermanent crop",
                                        case=False, na=False)
                & (df["Element"].str.contains("Area", case=False, na=False))
            )
            crop_area = df.loc[mask].copy()
        _save(crop_area, out / "cropland_area.csv",
              "| Unit: 1000 ha | Source: FAOSTAT RL")

    # --- Crop production & yields ---
    if "production" in zips:
        df = _read_faostat_zip(zips["production"])
        mask = (
            df["Item Code"].isin(list(CROP_ITEMS.keys()))
            & df["Element Code"].isin(list(CROP_ELEMENTS.keys()))
        )
        crop_prod = df.loc[mask].copy()
        _save(crop_prod, out / "crop_production.csv",
              "| Source: FAOSTAT QCL")

    _write_readme(out, [
        "CROPLAND  –  Formula parameters: P_cropland, Yield_cropland",
        "",
        "cropland_area.csv      Arable land + permanent crops area (1000 ha)",
        "                       Source: FAOSTAT Inputs/Land Use (domain RL)",
        "                       Element 5110 (Area); Items 6621, 6650, 6610",
        "",
        "crop_production.csv    Major crop aggregates – area harvested,",
        "                       production, yield",
        "                       Source: FAOSTAT Production (domain QCL)",
        "                       Elements 5312, 5510, 5419",
    ])


# ── P_grazing : pasture area, livestock stocks ────────────────────────
def process_grazing(zips: dict[str, Path]):
    log.info("=== Processing: GRAZING (P_grazing, Feed_demand) ===")
    out = PARAM_DIRS["grazing"]

    if "land_use" in zips:
        df = _read_faostat_zip(zips["land_use"])
        mask = (
            (df["Item Code"] == 6655)
            & (df["Element Code"] == 5110)
        )
        pasture = df.loc[mask].copy()
        if pasture.empty:
            mask = df["Item"].str.contains(
                "asture|eadow|razing", case=False, na=False
            )
            pasture = df.loc[mask].copy()
        _save(pasture, out / "pasture_area.csv",
              "| Unit: 1000 ha | Source: FAOSTAT RL")

    if "production" in zips:
        df = _read_faostat_zip(zips["production"])
        mask = (
            df["Item Code"].isin(list(LIVESTOCK_ITEMS.keys()))
            & df["Element Code"].isin(list(LIVESTOCK_ELEMENTS.keys()))
        )
        livestock = df.loc[mask].copy()
        if livestock.empty:
            # fallback: search by name
            mask = (
                df["Item"].str.contains(
                    "Cattle|Sheep|Goat|Horse|Camel|Chicken|Pig|Duck",
                    case=False, na=False,
                )
                & df["Element"].str.contains(
                    "Stock|Slaughter|Producing", case=False, na=False
                )
            )
            livestock = df.loc[mask].copy()
        _save(livestock, out / "livestock_stocks.csv",
              "| Source: FAOSTAT QCL")

    _write_readme(out, [
        "GRAZING  –  Formula parameters: P_grazing, Feed_demand",
        "",
        "pasture_area.csv       Permanent meadows & pastures (1000 ha)",
        "                       Source: FAOSTAT RL; Item 6655",
        "",
        "livestock_stocks.csv   Livestock populations (head) and slaughter",
        "                       Source: FAOSTAT QCL",
        "                       Items: Cattle(866), Sheep(976), Goats(1016),",
        "                              Horses(946), Camels(1126), etc.",
    ])


# ── P_forest : forest area, timber production ─────────────────────────
def process_forest(zips: dict[str, Path]):
    log.info("=== Processing: FOREST (P_forest, Forest_growth_rate) ===")
    out = PARAM_DIRS["forest"]

    if "land_use" in zips:
        df = _read_faostat_zip(zips["land_use"])
        mask = (
            (df["Item Code"] == 6661)
            & (df["Element Code"] == 5110)
        )
        forest_area = df.loc[mask].copy()
        if forest_area.empty:
            mask = (
                df["Item"].str.contains("orest land", case=False, na=False)
                & df["Element"].str.contains("Area", case=False, na=False)
            )
            forest_area = df.loc[mask].copy()
        _save(forest_area, out / "forest_area.csv",
              "| Unit: 1000 ha | Source: FAOSTAT RL")

    if "forestry" in zips:
        df = _read_faostat_zip(zips["forestry"])
        mask = (
            df["Item Code"].isin(list(FORESTRY_ITEMS.keys()))
            & df["Element Code"].isin(list(FORESTRY_ELEMENTS.keys()))
        )
        timber = df.loc[mask].copy()
        if timber.empty:
            mask = (
                df["Item"].str.contains(
                    "Roundwood|Sawnwood|Wood fuel|Fuelwood",
                    case=False, na=False,
                )
                & df["Element"].str.contains(
                    "Production|Import|Export", case=False, na=False
                )
            )
            timber = df.loc[mask].copy()
        _save(timber, out / "timber_production.csv",
              "| Source: FAOSTAT FO")

    _write_readme(out, [
        "FOREST  –  Formula parameters: P_forest, Forest_growth_rate",
        "",
        "forest_area.csv        Forest land area (1000 ha)",
        "                       Source: FAOSTAT RL; Item 6661",
        "",
        "timber_production.csv  Roundwood, sawnwood, fuelwood (m³)",
        "                       Source: FAOSTAT FO",
        "",
        "MANUAL DOWNLOAD NEEDED for forest growth / sequestration rates:",
        "  IPCC Guidelines (tropical rates):",
        "    https://www.ipcc-nggip.iges.or.jp/",
        "  UNECE Temperate & Boreal Forest Resource Assessment:",
        "    https://unece.org/forests/fra",
        "  FAO FRA (Forest Resources Assessment):",
        "    https://fra-data.fao.org/",
    ])


# ── P_fishing : fish catch, fishing grounds ───────────────────────────
def process_fishing(zips: dict[str, Path]):
    log.info("=== Processing: FISHING (P_fishing, Fish_catch, PPR) ===")
    out = PARAM_DIRS["fishing"]

    found_fish = False

    # Fish supply from Food Balance Sheets (best available in FAOSTAT bulk)
    if "food_balance" in zips:
        df = _read_faostat_zip(zips["food_balance"])
        mask = df["Item"].str.contains(
            "Fish|Seafood|Aquatic|Crustacean|Mollusc|Cephalopod|Pelagic"
            "|Demersal|Marine|Freshwater.*fish",
            case=False, na=False,
        )
        fish = df.loc[mask].copy()
        if not fish.empty:
            _save(fish, out / "fish_supply_fbs.csv",
                  "| Source: FAOSTAT Food Balance Sheets")
            found_fish = True
            # Log what items we found
            items = fish["Item"].unique()
            log.info("  Fish items found: %s", ", ".join(items[:10]))

    # Also try: use emissions data for fisheries-related items
    if "emissions" in zips:
        df = _read_faostat_zip(zips["emissions"])
        mask = df["Item"].str.contains(
            "Fish|Aquaculture", case=False, na=False
        )
        fish_em = df.loc[mask].copy()
        if not fish_em.empty:
            _save(fish_em, out / "fisheries_emissions.csv",
                  "| Source: FAOSTAT Emissions")

    if not found_fish:
        log.warning("  No fish data found in downloaded files.")
        log.warning("  Fish capture data requires FAO FishSTAT (separate download).")

    _write_readme(out, [
        "FISHING  –  Formula parameters: P_fishing, Fish_catch, PPR",
        "",
        "fish_supply_fbs.csv       Fish & seafood from food balance sheets",
        "                          Source: FAOSTAT Food Balance Sheets",
        "                          Includes: production, import, export,",
        "                          domestic supply, food supply per capita",
        "",
        "fisheries_emissions.csv   GHG emissions from fisheries/aquaculture",
        "                          Source: FAOSTAT Emissions Totals",
        "",
        "NOTE: Detailed capture fisheries data (needed for the formula)",
        "is NOT in FAOSTAT bulk downloads.  You must download separately:",
        "",
        "  FAO FishSTAT (capture fisheries by species, country, year):",
        "    https://www.fao.org/fishery/en/statistics",
        "    Dataset: 'Global Capture Production'",
        "    Reference MSY: 93 million tonnes/year (FAO 1997)",
        "",
        "  Sea Around Us (trophic levels & Primary Production Requirement):",
        "    https://www.seaaroundus.org/data/",
        "    Advanced Search > filter by EEZ for tonnage and PPR",
        "    Required to convert catch into fishing-ground area demand",
    ])


# ── P_built_up : built-up / infrastructure area ──────────────────────
def process_built_up(zips: dict[str, Path]):
    log.info("=== Processing: BUILT-UP (P_built_up) ===")
    out = PARAM_DIRS["built_up"]

    if "land_use" in zips:
        df = _read_faostat_zip(zips["land_use"])
        # Try known item codes for built-up/artificial area
        mask = df["Item"].str.contains(
            "uilt-up|rtificial|nfrastructure|and under perm. meadows",
            case=False, na=False,
        )
        # also try: "Other land" as proxy
        if mask.sum() == 0:
            mask = df["Item"].str.contains(
                "Other land|Inland water",
                case=False, na=False,
            )
        built = df.loc[mask].copy()
        # If still empty, save full item list for inspection
        if built.empty:
            items = df[["Item Code", "Item"]].drop_duplicates()
            _save(items, out / "available_land_items.csv",
                  "| All item codes in RL domain for manual inspection")
        else:
            _save(built, out / "built_up_area.csv",
                  "| Source: FAOSTAT RL")

    _write_readme(out, [
        "BUILT-UP  –  Formula parameter: P_built_up",
        "",
        "built_up_area.csv      Built-up / infrastructure area (1000 ha)",
        "                       Source: FAOSTAT RL (if item available)",
        "",
        "NOTE: FAOSTAT land-use data may not include built-up area",
        "directly.  For higher-resolution satellite-derived data:",
        "",
        "MANUAL DOWNLOAD:",
        "  JRC GHSL (Global Human Settlement Layer):",
        "    https://human-settlement.emergency.copernicus.eu/"
        "GHSLWeGenerateData.php",
        "    Product: GHS-BUILT-S (built-up surface grids)",
        "    Also on Google Earth Engine: tag 'ghsl'",
        "",
        "  CORINE Land Cover (Europe only):",
        "    https://land.copernicus.eu/en/products/corine-land-cover",
    ])


# ── Carbon : CO₂ emissions, sequestration ────────────────────────────
def process_carbon(zips: dict[str, Path]):
    log.info("=== Processing: CARBON (CO2_emissions, Sequestration) ===")
    out = PARAM_DIRS["carbon"]

    # --- FAOSTAT emissions (primary source – includes Energy sector) ---
    if "emissions" in zips:
        df = _read_faostat_zip(zips["emissions"])

        # 1) Energy-sector CO₂ (fossil fuel – the key input for carbon FP)
        energy_co2 = df[
            (df["Item"] == "Energy")
            & (df["Element"] == "Emissions (CO2)")
        ].copy()
        if not energy_co2.empty:
            _save(energy_co2, out / "co2_energy_faostat.csv",
                  "| Unit: kt CO₂ | Source: FAOSTAT Emissions (Energy)")

        # 2) Total agrifood-system CO₂ (for full-system view)
        total_co2 = df[
            (df["Item"] == "Agrifood systems")
            & (df["Element"].str.contains("CO2", case=False, na=False))
        ].copy()
        if not total_co2.empty:
            _save(total_co2, out / "co2_agrifood_total_faostat.csv",
                  "| Unit: kt | Source: FAOSTAT Emissions (Agrifood)")

        # 3) Land-use change & forestry emissions (biocapacity impact)
        lulucf = df[
            df["Item"].str.contains(
                "Forest|Land-use change|Net Forest|Forestland",
                case=False, na=False,
            )
        ].copy()
        if not lulucf.empty:
            _save(lulucf, out / "lulucf_emissions_faostat.csv",
                  "| Source: FAOSTAT Emissions (LULUCF)")

    # --- World Bank CO₂ as cross-check (may fail if indicator archived) ---
    log.info("  Fetching CO₂ data from World Bank API (cross-check) ...")
    for indicator, label in [
        ("EN.ATM.CO2E.KT", "CO₂ emissions total (kt)"),
        ("EN.ATM.CO2E.PC", "CO₂ emissions per capita (t)"),
    ]:
        records = _fetch_worldbank_indicator(indicator, label)
        if records:
            _save(pd.DataFrame(records),
                  out / f"co2_worldbank_{indicator.split('.')[-1].lower()}.csv",
                  f"| Source: World Bank ({indicator})")

    _write_readme(out, [
        "CARBON  –  Formula parameters: Carbon_Footprint, CO2_emissions,",
        "                               Sequestration_rate",
        "",
        "co2_energy_faostat.csv         CO₂ from the Energy sector (kt)",
        "                               Source: FAOSTAT Emissions Totals",
        "                               Item='Energy', Element='Emissions (CO2)'",
        "                               >>> PRIMARY INPUT for carbon Footprint",
        "",
        "co2_agrifood_total_faostat.csv Total agrifood-system CO₂/CO₂eq (kt)",
        "                               Source: FAOSTAT Emissions Totals",
        "",
        "lulucf_emissions_faostat.csv   Land-use change & forest emissions",
        "                               Source: FAOSTAT Emissions Totals",
        "",
        "co2_worldbank_*.csv            Cross-check from World Bank WDI",
        "                               (may be empty if indicator archived)",
        "",
        "FORMULA NOTE:",
        "  Carbon Footprint = forest area needed to sequester 65% of CO₂",
        "  (oceans absorb ~35%).  Sequestration rate from IPCC: weighted",
        "  average across 26 forest biomes.",
        "",
        "MANUAL DOWNLOAD for additional detail:",
        "  IEA (requires license):",
        "    https://www.iea.org/data-and-statistics/data-explorers",
        "    Database: 'Greenhouse Gas Emissions from Energy'",
        "",
        "  EDGAR (EU JRC, free):",
        "    https://edgar.jrc.ec.europa.eu/",
        "    Dataset: EDGARv8.0 CO₂ 1970–2023",
    ])


def _fetch_worldbank_indicator(
    indicator: str,
    label: str,
    per_page: int = 15000,
    date: str = "1961:2023",
) -> list[dict]:
    """Fetch a World Bank WDI indicator for all countries."""
    url = f"{WB_API}/country/all/indicator/{indicator}"
    params = {
        "format": "json",
        "per_page": per_page,
        "date": date,
    }
    records = []
    page = 1
    while True:
        params["page"] = page
        try:
            r = SESSION.get(url, params=params, timeout=60)
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:
            log.warning("  World Bank API error (%s): %s", indicator, exc)
            break

        if not isinstance(payload, list) or len(payload) < 2:
            break
        meta, data = payload[0], payload[1]
        if not data:
            break

        for row in data:
            if row.get("value") is None:
                continue
            records.append({
                "country_code": row["countryiso3code"],
                "country": row["country"]["value"],
                "year": int(row["date"]),
                "indicator": indicator,
                "indicator_name": label,
                "value": row["value"],
                "unit": row.get("unit", ""),
            })

        total_pages = meta.get("pages", 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    log.info("  World Bank %s: %d records", indicator, len(records))
    return records


# ── Population ────────────────────────────────────────────────────────
def process_population(zips: dict[str, Path]):
    log.info("=== Processing: POPULATION ===")
    out = PARAM_DIRS["population"]

    if "population" in zips:
        df = _read_faostat_zip(zips["population"])
        # Element 511 = Total Population - Both sexes (or similar)
        mask = df["Element"].str.contains(
            "Total Population|Both sexes", case=False, na=False
        )
        if mask.sum() == 0:
            # take everything – population file is usually small
            pop = df.copy()
        else:
            pop = df.loc[mask].copy()
        _save(pop, out / "population.csv",
              "| Unit: 1000 persons | Source: FAOSTAT OA")

    # Also fetch from World Bank as cross-check
    records = _fetch_worldbank_indicator(
        "SP.POP.TOTL", "Population, total"
    )
    if records:
        df = pd.DataFrame(records)
        _save(df, out / "population_worldbank.csv",
              "| Source: World Bank (SP.POP.TOTL)")

    _write_readme(out, [
        "POPULATION  –  Formula parameter: Population (denominator)",
        "",
        "population.csv              National populations (1000 persons)",
        "                            Source: FAOSTAT OA",
        "",
        "population_worldbank.csv    Cross-check from World Bank WDI",
        "                            Indicator: SP.POP.TOTL",
    ])


# ── Trade (consumption-based accounting) ──────────────────────────────
def process_trade(zips: dict[str, Path]):
    log.info("=== Processing: TRADE (Footprint_consumption) ===")
    out = PARAM_DIRS["trade"]

    if "trade" in zips:
        df = _read_faostat_zip(zips["trade"])
        # Keep import/export quantities for major categories
        mask = df["Element Code"].isin([5610, 5910])
        trade = df.loc[mask].copy()
        _save(trade, out / "trade_crops_livestock.csv",
              "| Source: FAOSTAT TCL")
    else:
        log.info("  Trade file skipped (use --skip-trade to confirm)")

    _write_readme(out, [
        "TRADE  –  Formula: Footprint_consumption = Production + Import"
        " - Export",
        "",
        "trade_crops_livestock.csv   Import/export quantities (tonnes)",
        "                            Source: FAOSTAT TCL",
        "                            Elements: 5610 (Import), 5910 (Export)",
        "",
        "ADDITIONAL SOURCES:",
        "  UN Comtrade (non-agricultural trade):",
        "    https://comtradeplus.un.org/",
        "    API: https://comtradedeveloper.un.org/",
        "    Free: 100k records/call, 500 calls/day",
        "",
        "  GTAP (Multi-Region Input-Output tables):",
        "    https://www.gtap.agecon.purdue.edu/",
        "    Licensed database; GTAP 10 used by Global Footprint Network",
    ])


# ── Equivalence & Yield factors ───────────────────────────────────────
def process_factors():
    log.info("=== Processing: FACTORS (EF, YF) ===")
    out = PARAM_DIRS["factors"]

    # Save the standard equivalence factors from Wackernagel et al. 2002
    # as a reference starting point
    ef_data = [
        {"land_type": "Cropland",           "equivalence_factor_gha_per_ha": 2.1,
         "notes": "Wackernagel et al. 2002 (Table 1)"},
        {"land_type": "Built-up land",      "equivalence_factor_gha_per_ha": 2.2,
         "notes": "Assumed same productivity as cropland it replaces"},
        {"land_type": "Forest",             "equivalence_factor_gha_per_ha": 1.3,
         "notes": "Wackernagel et al. 2002 (Table 1)"},
        {"land_type": "Grazing land",       "equivalence_factor_gha_per_ha": 0.5,
         "notes": "Wackernagel et al. 2002 (Table 1)"},
        {"land_type": "Fishing grounds",    "equivalence_factor_gha_per_ha": 0.4,
         "notes": "Wackernagel et al. 2002 (Table 1)"},
        {"land_type": "Carbon (fossil fuel)", "equivalence_factor_gha_per_ha": 1.3,
         "notes": "Uses forest equivalence factor (sequestration area)"},
    ]
    df = pd.DataFrame(ef_data)
    _save(df, out / "equivalence_factors_reference_1999.csv",
          "| Reference values from 1999 accounts")

    _write_readme(out, [
        "FACTORS  –  Formula parameters: Equivalence_Factor (EF),",
        "                                Yield_Factor (YF)",
        "",
        "equivalence_factors_reference_1999.csv",
        "    Reference EF values from Wackernagel et al. 2002 (Table 1)",
        "    These are for 1999; EFs change yearly with land-use shifts.",
        "",
        "FORMULA:",
        "  Global_hectares = Physical_ha × Yield_Factor × Equivalence_Factor",
        "",
        "  Yield_Factor (YF) = country_yield / world_average_yield",
        "    → computed from FAOSTAT production data (01_cropland, etc.)",
        "",
        "  Equivalence_Factor (EF) = suitability_index / global_avg_SI",
        "    → derived from GAEZ agricultural suitability data",
        "",
        "MANUAL DOWNLOAD:",
        "  GAEZ (Global Agro-Ecological Zones, FAO/IIASA):",
        "    https://gaez.fao.org/",
        "    Theme 4: Suitability and Attainable Yield",
        "    Theme 5: Actual Yields and Production",
        "    Also available as ArcGIS Image Services",
        "",
        "  GLASOD (Soil degradation → biocapacity loss):",
        "    https://data.isric.org/geonetwork/srv/api/records/"
        "9e84c15e-cb46-45e2-9126-1ca38bd5cd22",
        "    Download the Shapefile format from ISRIC repository",
        "    Degradation rated: light / moderate / strong / extreme",
    ])


# ═══════════════════════════════════════════════════════════════════════
# 3. Fetch additional gap-filling data sources
# ═══════════════════════════════════════════════════════════════════════

# ── FishBase trophic levels via API ─────────────────────────────────
def fetch_fishbase_trophic():
    """Fetch trophic levels for major commercial species from FishBase API."""
    log.info("=== Fetching: FishBase trophic level data ===")
    out = PARAM_DIRS["fishing"]
    records = []

    # First: save our curated reference table
    for species, info in FISH_TROPHIC_LEVELS.items():
        records.append({
            "species": species,
            "trophic_level": info["trophic_level"],
            "species_group": info["species_group"],
            "source": "Literature (Pauly & Christensen 1995 / FishBase)",
        })

    # Try FishBase API for additional species
    api_records = []
    try:
        # Search for key commercial species via the ecology endpoint
        # FishBase API: /ecology?limit=100 returns ecology records
        species_queries = [
            "Engraulis ringens",     # Anchoveta
            "Clupea harengus",       # Atlantic herring
            "Katsuwonus pelamis",    # Skipjack tuna
            "Gadus morhua",          # Atlantic cod
            "Theragra chalcogramma", # Alaska pollock
            "Thunnus albacares",     # Yellowfin tuna
            "Sardina pilchardus",    # European pilchard
            "Scomber scombrus",      # Atlantic mackerel
            "Thunnus obesus",        # Bigeye tuna
            "Oreochromis niloticus", # Nile tilapia
        ]
        for sci_name in species_queries:
            try:
                genus, species = sci_name.split(" ", 1)
                url = f"{FISHBASE_API}/species?Genus={genus}&Species={species}"
                r = SESSION.get(url, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and "data" in data and data["data"]:
                        sp = data["data"][0]
                        spec_code = sp.get("SpecCode")
                        if spec_code:
                            # Fetch ecology for this species
                            eco_url = f"{FISHBASE_API}/ecology?SpecCode={spec_code}"
                            er = SESSION.get(eco_url, timeout=30)
                            if er.status_code == 200:
                                eco_data = er.json()
                                if isinstance(eco_data, dict) and "data" in eco_data and eco_data["data"]:
                                    eco = eco_data["data"][0]
                                    tl = eco.get("DietTroph") or eco.get("FoodTroph")
                                    if tl:
                                        api_records.append({
                                            "species": f"{genus} {species}",
                                            "common_name": sp.get("FBname", ""),
                                            "trophic_level": float(tl),
                                            "trophic_se": float(eco.get("DietSeTroph") or eco.get("FoodSeTroph") or 0),
                                            "spec_code": spec_code,
                                            "source": "FishBase API",
                                        })
                time.sleep(REQUEST_DELAY)
            except Exception as exc:
                log.debug("  FishBase query failed for %s: %s", sci_name, exc)
                continue

    except Exception as exc:
        log.warning("  FishBase API unavailable: %s", exc)

    if api_records:
        df_api = pd.DataFrame(api_records)
        _save(df_api, out / "fishbase_trophic_api.csv",
              "| Source: FishBase API (live query)")
        log.info("  Retrieved %d species from FishBase API", len(api_records))
    else:
        log.info("  FishBase API returned no data; using literature reference table")

    # Always save the curated reference table
    df_ref = pd.DataFrame(records)
    _save(df_ref, out / "fish_trophic_reference.csv",
          "| Source: Literature (Pauly & Christensen 1995)")

    # Save PPR calculation parameters
    ppr_params = pd.DataFrame([
        {"parameter": "transfer_efficiency", "value": FISH_TRANSFER_EFFICIENCY,
         "unit": "fraction", "source": "Pauly & Christensen 1995",
         "notes": "Efficiency between trophic levels (10.13%)"},
        {"parameter": "discard_rate", "value": FISH_DISCARD_RATE,
         "unit": "ratio", "source": "Pauly & Christensen 1995",
         "notes": "1.27 = 0.27 t bycatch per tonne harvested"},
        {"parameter": "wet_weight_to_carbon", "value": FISH_WET_WEIGHT_TO_CARBON,
         "unit": "ratio", "source": "Sea Around Us / Pauly",
         "notes": "9:1 wet weight to carbon conversion"},
        {"parameter": "sustainable_catch_global", "value": FISH_SUSTAINABLE_CATCH_MT,
         "unit": "million tonnes/yr", "source": "Gulland 1971 / FAO",
         "notes": "Maximum sustainable yield for global marine capture"},
        {"parameter": "continental_shelf_area", "value": CONTINENTAL_SHELF_AREA_HA,
         "unit": "hectares", "source": "Various oceanographic",
         "notes": "~2 billion ha of continental shelf"},
    ])
    _save(ppr_params, out / "ppr_calculation_parameters.csv",
          "| Source: Literature compilation")


# ── Sea Around Us – catch by EEZ ────────────────────────────────────
def fetch_sau_catch():
    """Fetch global catch data from Sea Around Us API."""
    log.info("=== Fetching: Sea Around Us catch data ===")
    out = PARAM_DIRS["fishing"]
    records = []

    try:
        # Global catch by year (all EEZs combined)
        url = f"{SAU_API}/global/1/stock-status"
        r = SESSION.get(url, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                for row in data["data"]:
                    records.append(row)
                if records:
                    df = pd.DataFrame(records)
                    _save(df, out / "sau_global_stock_status.csv",
                          "| Source: Sea Around Us API (global stock status)")
                    log.info("  Sea Around Us: %d records", len(records))
                    return
    except Exception as exc:
        log.warning("  Sea Around Us stock-status endpoint: %s", exc)

    # Fallback: try catch reconstruction endpoint
    try:
        url = f"{SAU_API}/global/1/catch-chart/eez"
        r = SESSION.get(url, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                df = pd.DataFrame(data["data"])
                _save(df, out / "sau_global_catch.csv",
                      "| Source: Sea Around Us API (global catch)")
                log.info("  Sea Around Us: %d catch records", len(df))
                return
    except Exception as exc:
        log.warning("  Sea Around Us catch endpoint: %s", exc)

    log.info("  Sea Around Us API not reachable; PPR params saved from literature")


# ── GLEAM feed coefficients ─────────────────────────────────────────
def process_gleam_coefficients():
    """Save GLEAM livestock feed requirement coefficients."""
    log.info("=== Processing: GLEAM feed coefficients ===")
    out = PARAM_DIRS["grazing"]

    records = []
    for animal, coeffs in GLEAM_FEED_COEFFICIENTS.items():
        records.append({
            "animal_type": animal,
            "total_dmi_kg_per_day": coeffs["total_dmi_kg_day"],
            "pasture_fraction": coeffs["pasture_fraction"],
            "crop_fraction": coeffs["crop_fraction"],
            "residue_fraction": coeffs["residue_fraction"],
            "pasture_dmi_kg_per_day": round(
                coeffs["total_dmi_kg_day"] * coeffs["pasture_fraction"], 2),
            "annual_pasture_demand_t_dm": round(
                coeffs["total_dmi_kg_day"] * coeffs["pasture_fraction"] * 365 / 1000, 3),
            "source": "FAO GLEAM 3.0 (global averages)",
        })

    df = pd.DataFrame(records)
    _save(df, out / "gleam_feed_coefficients.csv",
          "| Source: FAO GLEAM 3.0 global averages")

    # Also save world-average grassland NPP
    npp_data = pd.DataFrame([{
        "parameter": "world_avg_grassland_npp",
        "value": GRASSLAND_NPP_T_DM_PER_HA_YR,
        "unit": "tonnes dry matter / ha / year",
        "source": "Monfreda et al. 2008 (SAGE, Univ. Wisconsin)",
        "notes": "Above-ground edible NPP for grassland. Used as Y_W in grazing footprint.",
    }])
    _save(npp_data, out / "grassland_npp_reference.csv",
          "| Source: SAGE / Monfreda et al. 2008")

    _write_readme(out, [
        "GRAZING  –  Formula parameters: P_grazing, Feed_demand",
        "",
        "pasture_area.csv               Permanent meadows & pastures (1000 ha)",
        "                               Source: FAOSTAT RL; Item 6655",
        "",
        "livestock_stocks.csv           Livestock populations (head) and slaughter",
        "                               Source: FAOSTAT QCL",
        "",
        "gleam_feed_coefficients.csv    Dry matter intake & feed source fractions",
        "                               per livestock type (kg DM/head/day)",
        "                               Source: FAO GLEAM 3.0 global averages",
        "                               Used to compute: TFR, F_Mkt, F_Crop, F_Res",
        "                               Grazing demand = TFR - F_Mkt - F_Crop - F_Res",
        "",
        "grassland_npp_reference.csv    World-average grassland productivity",
        "                               Value: 2.45 t DM/ha/yr",
        "                               Source: Monfreda et al. 2008 (SAGE)",
        "",
        "FORMULA:",
        "  P_GR = TFR - F_Mkt - F_Crop - F_Res  (pasture-based feed demand)",
        "  EF_grazing = (P_GR / Y_W_grass) * EQF_grazing",
        "  Y_W_grass = 2.45 t DM/ha/yr",
        "",
        "For detailed regional coefficients, download FAO GLEAM model:",
        "  https://www.fao.org/gleam/en/",
    ])


# ── Reference parameters (carbon, forest, ocean) ───────────────────
def process_reference_parameters():
    """Save all literature-based reference parameters needed for the formula."""
    log.info("=== Processing: REFERENCE PARAMETERS ===")
    out = PARAM_DIRS["reference"]

    # Carbon sequestration parameters
    carbon_params = pd.DataFrame([
        {"parameter": "AFCS", "value": AFCS_TC_PER_HA_YR,
         "uncertainty": f"± {AFCS_UNCERTAINTY}",
         "unit": "tonnes C / ha / year",
         "source": "Mancini et al. (NFA 2016)",
         "notes": "Average Forest-Carbon Sequestration rate for world-average forests"},
        {"parameter": "ocean_co2_fraction_min", "value": OCEAN_CO2_FRACTION_MIN,
         "uncertainty": "", "unit": "fraction",
         "source": "Khatiwala et al. 2009 (Nature)",
         "notes": "Minimum ocean absorption of anthropogenic CO2 (1961-2008 range)"},
        {"parameter": "ocean_co2_fraction_max", "value": OCEAN_CO2_FRACTION_MAX,
         "uncertainty": "", "unit": "fraction",
         "source": "Khatiwala et al. 2009 (Nature)",
         "notes": "Maximum ocean absorption of anthropogenic CO2 (1961-2008 range)"},
        {"parameter": "ocean_co2_fraction_default", "value": OCEAN_CO2_FRACTION_DEFAULT,
         "uncertainty": "", "unit": "fraction",
         "source": "Wackernagel et al. 2002 / IPCC 2001",
         "notes": "Commonly used constant for ocean CO2 absorption (~35%)"},
    ])
    _save(carbon_params, out / "carbon_sequestration_parameters.csv",
          "| Source: Literature compilation (Mancini, Khatiwala, IPCC)")

    # Forest reference yields
    forest_params = pd.DataFrame([
        {"parameter": "world_avg_forest_NAI", "value": FOREST_NAI_M3_PER_HA_YR,
         "unit": "m3 harvestable wood / ha / year",
         "source": "UNECE/FAO TBFRA 2000 + FAO GFSM 1998",
         "notes": "Net Annual Increment. Denominator for forest product Footprint."},
    ])
    _save(forest_params, out / "forest_nai_reference.csv",
          "| Source: UNECE/FAO TBFRA 2000")

    # Ocean CO2 uptake time series (Khatiwala et al. 2009, Table from paper)
    # Approximate decadal values from the paper
    ocean_ts = pd.DataFrame([
        {"year": 1960, "ocean_uptake_pgc_yr": 1.0, "source": "Khatiwala et al. 2009"},
        {"year": 1965, "ocean_uptake_pgc_yr": 1.2, "source": "Khatiwala et al. 2009"},
        {"year": 1970, "ocean_uptake_pgc_yr": 1.4, "source": "Khatiwala et al. 2009"},
        {"year": 1975, "ocean_uptake_pgc_yr": 1.6, "source": "Khatiwala et al. 2009"},
        {"year": 1980, "ocean_uptake_pgc_yr": 1.8, "source": "Khatiwala et al. 2009"},
        {"year": 1985, "ocean_uptake_pgc_yr": 1.9, "source": "Khatiwala et al. 2009"},
        {"year": 1990, "ocean_uptake_pgc_yr": 2.0, "source": "Khatiwala et al. 2009"},
        {"year": 1995, "ocean_uptake_pgc_yr": 2.1, "source": "Khatiwala et al. 2009"},
        {"year": 2000, "ocean_uptake_pgc_yr": 2.2, "source": "Khatiwala et al. 2009"},
        {"year": 2005, "ocean_uptake_pgc_yr": 2.3, "source": "Khatiwala et al. 2009"},
        {"year": 2008, "ocean_uptake_pgc_yr": 2.3, "source": "Khatiwala et al. 2009"},
    ])
    _save(ocean_ts, out / "ocean_co2_uptake_timeseries.csv",
          "| Source: Khatiwala et al. 2009 (approximate decadal values)")

    # Sustainable catch by species group (Gulland 1971 / FAO)
    catch_groups = pd.DataFrame([
        {"species_group": "Herrings, sardines, anchovies", "sustainable_catch_mt": 20.0},
        {"species_group": "Cods, hakes, haddocks", "sustainable_catch_mt": 15.0},
        {"species_group": "Jacks, mullets, sauries", "sustainable_catch_mt": 8.0},
        {"species_group": "Tunas, bonitos, billfishes", "sustainable_catch_mt": 5.0},
        {"species_group": "Mackerels, snoeks, cutlassfishes", "sustainable_catch_mt": 5.0},
        {"species_group": "Shrimps, prawns", "sustainable_catch_mt": 3.0},
        {"species_group": "Squids, cuttlefishes, octopuses", "sustainable_catch_mt": 3.0},
        {"species_group": "Flounders, halibuts, soles", "sustainable_catch_mt": 3.0},
        {"species_group": "Redfishes, basses, congers", "sustainable_catch_mt": 3.0},
        {"species_group": "Salmons, trouts, smelts", "sustainable_catch_mt": 1.5},
        {"species_group": "Lobsters, crabs", "sustainable_catch_mt": 1.5},
        {"species_group": "Freshwater fishes", "sustainable_catch_mt": 10.0},
        {"species_group": "Miscellaneous marine fishes", "sustainable_catch_mt": 10.0},
        {"species_group": "Other aquatic invertebrates", "sustainable_catch_mt": 5.0},
    ])
    catch_groups["source"] = "Gulland 1971 / FAO (approximate allocation)"
    catch_groups["notes"] = "Ref total: 93 Mt/yr. Allocation across groups is approximate."
    _save(catch_groups, out / "sustainable_catch_by_group.csv",
          "| Source: Gulland 1971 / FAO reference")

    _write_readme(out, [
        "REFERENCE PARAMETERS  –  Literature-based constants for the formula",
        "",
        "carbon_sequestration_parameters.csv",
        "    AFCS = 0.73 ± 0.37 t C/ha/yr (Mancini et al., NFA 2016)",
        "    Ocean CO₂ absorption: 28-35% (Khatiwala et al. 2009)",
        "    Formula: EF_C = CO₂ × (1 - S_Ocean) / Y_C × EQF_forest",
        "",
        "forest_nai_reference.csv",
        "    Net Annual Increment = 1.81 m³/ha/yr (UNECE/FAO TBFRA 2000)",
        "    Denominator for forest product Footprint",
        "",
        "ocean_co2_uptake_timeseries.csv",
        "    Approximate decadal ocean CO₂ uptake (Pg C/yr)",
        "    Source: Khatiwala et al. 2009",
        "    Divide by CDIAC total emissions for time-varying fraction",
        "",
        "sustainable_catch_by_group.csv",
        "    Reference MSY allocation across 14 species groups",
        "    Total: ~93 million tonnes/yr (Gulland 1971)",
        "",
        "FORMULA NOTES:",
        "  Carbon FP = [CO₂ × (1 - ocean_frac)] / AFCS × EQF_forest",
        "  Forest FP = timber_m3 / NAI × EQF_forest",
        "  Grazing FP = pasture_feed_demand / grassland_NPP × EQF_grazing",
        "  Fishing FP = PPR_harvest / (PPS / shelf_area) × EQF_fishing",
        "    where PPR = catch × discard_rate × (1/TE)^(TL-1) / carbon_ratio",
    ])


# ═══════════════════════════════════════════════════════════════════════
# Summary report
# ═══════════════════════════════════════════════════════════════════════

def write_summary():
    """Write a summary of all fetched data."""
    lines = [
        "=" * 72,
        "ECOLOGICAL FOOTPRINT / OVERSHOOT  –  DATA FETCH SUMMARY",
        "=" * 72,
        "",
        "Formula:  Overshoot = Ecological Footprint − Biocapacity",
        "  Footprint  = Σ (P_i × YF_i × EF_i)  for 6 land-use categories",
        "  Biocapacity = Σ (A_i × YF_i × EF_i)  for available productive area",
        "",
        "-" * 72,
    ]

    for key, d in sorted(PARAM_DIRS.items()):
        lines.append(f"\n{d.name}/")
        if d.exists():
            csvs = sorted(d.glob("*.csv"))
            for p in csvs:
                size = _human_size(p.stat().st_size)
                nrows = sum(1 for _ in open(p)) - 1
                lines.append(f"  {p.name:<45s} {nrows:>8,d} rows  {size:>10s}")
            if not csvs:
                lines.append("  (no CSV files)")
        else:
            lines.append("  (directory not created)")

    lines.extend([
        "",
        "-" * 72,
        "Raw downloads cached in: data/raw/",
        "",
        "Data requiring manual download (for full NFA-grade accuracy):",
        "  - GAEZ v4 (suitability indexes for time-varying EQFs):",
        "      https://gaez.fao.org/  Theme 4: Suitability & Attainable Yield",
        "  - GFN Calculation Factors (pre-computed YF/EQF by year):",
        "      https://data.footprintnetwork.org/",
        "  - GLASOD (soil degradation):",
        "      https://data.isric.org/",
        "  - GHSL (satellite built-up area):",
        "      https://human-settlement.emergency.copernicus.eu/",
        "  - IEA (detailed energy CO₂, licensed):",
        "      https://www.iea.org/data-and-statistics/",
        "  - GTAP (MRIO tables, licensed):",
        "      https://www.gtap.agecon.purdue.edu/",
        "  - FAO GLEAM (detailed regional feed coefficients):",
        "      https://www.fao.org/gleam/en/",
        "  - FAO FishSTAT (capture fisheries by species):",
        "      https://www.fao.org/fishery/en/statistics",
        "  - FAO SOFIA (stock status reports):",
        "      https://www.fao.org/publications/sofia/en/",
        "=" * 72,
    ])

    summary_path = DATA_DIR / "FETCH_SUMMARY.txt"
    summary_path.write_text("\n".join(lines) + "\n")
    log.info("Summary written to %s", summary_path.relative_to(BASE_DIR))
    print("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Fetch input data for the Ecological Footprint formula."
    )
    parser.add_argument(
        "--skip-trade", action="store_true",
        help="Skip the 265 MB trade bulk download",
    )
    parser.add_argument(
        "--skip-food-balance", action="store_true",
        help="Skip the 52 MB food-balance-sheets download",
    )
    parser.add_argument(
        "--redownload", action="store_true",
        help="Re-download files even if cached in data/raw/",
    )
    args = parser.parse_args()

    # Create directories
    for d in [DATA_DIR, RAW_DIR, *PARAM_DIRS.values()]:
        d.mkdir(parents=True, exist_ok=True)

    # Determine which FAOSTAT files to download
    # food_balance is needed for fishing data, so included by default
    fao_keys = [
        "land_use", "production", "forestry", "population", "emissions",
        "food_balance",
    ]
    if not args.skip_trade:
        fao_keys.append("trade")
    if args.skip_food_balance:
        fao_keys.remove("food_balance")

    # ── Step 1: Download raw data ─────────────────────────────────
    zips = download_faostat(fao_keys, redownload=args.redownload)

    if not zips:
        log.error("No FAOSTAT files downloaded. Check network / URLs.")
        log.error("Proceeding with World Bank API only ...")

    # ── Step 2: Process each formula parameter (FAOSTAT-based) ────
    process_cropland(zips)
    process_grazing(zips)
    process_forest(zips)
    process_fishing(zips)
    process_built_up(zips)
    process_carbon(zips)
    process_population(zips)
    if not args.skip_trade:
        process_trade(zips)
    process_factors()

    # ── Step 3: Gap-filling data (APIs + literature constants) ──
    process_gleam_coefficients()     # grazing: feed coefficients + grassland NPP
    fetch_fishbase_trophic()         # fishing: trophic levels from FishBase API
    fetch_sau_catch()                # fishing: Sea Around Us catch data
    process_reference_parameters()   # carbon, forest, ocean constants

    # ── Step 4: Summary ───────────────────────────────────────────
    write_summary()

    log.info("Done.")


if __name__ == "__main__":
    main()
