#!/usr/bin/env python3
"""
Ecological Overshoot Calculator
================================
Computes per-country, per-year Ecological Footprint and Biocapacity
for the most recent 10-year window available in the data (2014-2023),
and outputs country-level and global summary CSVs.

Based on the National Footprint Accounts methodology (Wackernagel et al.).
"""

import os
import warnings
import zipfile
import math
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# ── Paths (resolve relative to project root, one level up from scripts/) ────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = str(PROJECT_ROOT / "data")
OUT_COUNTRY = os.path.join(DATA, "overshoot_results.csv")
OUT_GLOBAL = os.path.join(DATA, "overshoot_global_summary.csv")

YEAR_MIN = 2014
YEAR_MAX = 2023
YEARS = list(range(YEAR_MIN, YEAR_MAX + 1))

# ── Equivalence Factors (gha per ha) ────────────────────────────────────────
EQF_CROPLAND = 2.1
EQF_BUILT_UP = 2.2
EQF_FOREST = 1.3
EQF_GRAZING = 0.5
EQF_FISHING = 0.4
EQF_CARBON = 1.3  # uses forest EQF

# ── Reference constants ─────────────────────────────────────────────────────
GRASSLAND_NPP = 2.45        # t DM / ha / yr
FOREST_NAI = 1.81           # m³ / ha / yr
AFCS = 0.73                 # t C / ha / yr
OCEAN_CO2_FRAC = 0.35       # fraction absorbed by oceans

# PPR / fishing parameters
TRANSFER_EFFICIENCY = 0.1013
DISCARD_RATE = 1.27
WET_TO_CARBON = 9.0
SUSTAINABLE_CATCH_MT = 93.0         # million tonnes
CONTINENTAL_SHELF_HA = 2_000_000_000  # 2 billion ha

# Trophic levels for FBS fish categories
# Trophic levels for FBS fish sub-categories only (NOT the aggregate "Fish, Seafood")
TROPHIC_LEVELS = {
    "Freshwater Fish": 2.5,
    "Demersal Fish": 3.8,
    "Pelagic Fish": 3.0,
    "Marine Fish, Other": 3.2,
    "Crustaceans": 2.5,
    "Cephalopods": 3.5,
    "Molluscs, Other": 2.1,
    "Aquatic Animals, Others": 3.0,
    "Aquatic Products, Other": 3.0,
    "Meat, Aquatic Mammals": 3.2,
    # "Fish, Seafood" excluded — it is the aggregate of the above subcategories
}

# GLEAM pasture demand mapping (FAOSTAT item → annual pasture DM tonnes/head)
GLEAM_PASTURE = {
    "Cattle": 2.35,       # average of dairy (2.382) and beef (2.325)
    "Buffalo": 2.409,
    "Sheep": 0.46,
    "Goats": 0.394,
    "Camels": 2.0,        # approximate, similar to cattle
    "Swine / pigs": 0.0,  # zero pasture
}


def load_faostat(path, year_range=None):
    """Load a FAOSTAT normalized CSV and optionally filter years."""
    df = pd.read_csv(path)
    if year_range is not None:
        df = df[df["Year"].between(year_range[0], year_range[1])]
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ═══════════════════════════════════════════════════════════════════════════════
print("Loading data files...")

crop_prod = load_faostat(
    os.path.join(DATA, "01_cropland", "crop_production.csv"), (YEAR_MIN, YEAR_MAX)
)
cropland_area = load_faostat(
    os.path.join(DATA, "01_cropland", "cropland_area.csv"), (YEAR_MIN, YEAR_MAX)
)
livestock = load_faostat(
    os.path.join(DATA, "02_grazing", "livestock_stocks.csv"), (YEAR_MIN, YEAR_MAX)
)
pasture_area = load_faostat(
    os.path.join(DATA, "02_grazing", "pasture_area.csv"), (YEAR_MIN, YEAR_MAX)
)
timber = load_faostat(
    os.path.join(DATA, "03_forest", "timber_production.csv"), (YEAR_MIN, YEAR_MAX)
)
forest_area = load_faostat(
    os.path.join(DATA, "03_forest", "forest_area.csv"), (YEAR_MIN, YEAR_MAX)
)
fish_fbs = load_faostat(
    os.path.join(DATA, "04_fishing", "fish_supply_fbs.csv"), (YEAR_MIN, YEAR_MAX)
)
co2_energy = load_faostat(
    os.path.join(DATA, "06_carbon", "co2_energy_faostat.csv"), (YEAR_MIN, YEAR_MAX)
)
population = load_faostat(
    os.path.join(DATA, "07_population", "population.csv"), (YEAR_MIN, YEAR_MAX)
)

# Load land-use data from ZIP for built-up area calculation
print("Loading land-use ZIP for built-up area...")
land_use_zip = os.path.join(DATA, "raw", "Inputs_LandUse_E_All_Data_(Normalized).zip")
with zipfile.ZipFile(land_use_zip) as z:
    csv_name = [n for n in z.namelist() if n.endswith(".csv") and "Data" in n][0]
    land_use_all = pd.read_csv(z.open(csv_name), encoding="latin-1")
land_use_all = land_use_all[land_use_all["Year"].between(YEAR_MIN, YEAR_MAX)]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PRE-COMPUTE WORLD-LEVEL AGGREGATES
# ═══════════════════════════════════════════════════════════════════════════════
print("Computing world-level aggregates...")

# ── Cropland: world yield per crop group per year ────────────────────────────
# World = Area Code 5000 or aggregate rows with Area containing "World"
# Safer: sum all countries (exclude aggregates: Area Code < 5000)
_cp = crop_prod[crop_prod["Area Code"] < 5000].copy()
_cp_prod = (
    _cp[_cp["Element"] == "Production"]
    .groupby(["Item Code", "Year"])["Value"]
    .sum()
    .rename("world_production_t")
)
_cp_area = (
    _cp[_cp["Element"] == "Area harvested"]
    .groupby(["Item Code", "Year"])["Value"]
    .sum()
    .rename("world_area_ha")
)
world_crop_yield = pd.concat([_cp_prod, _cp_area], axis=1)
world_crop_yield["world_yield_t_per_ha"] = (
    world_crop_yield["world_production_t"] / world_crop_yield["world_area_ha"]
)
# Replace inf/nan with 0
world_crop_yield["world_yield_t_per_ha"] = world_crop_yield[
    "world_yield_t_per_ha"
].replace([np.inf, -np.inf], 0).fillna(0)

# ── Fishing: world total fish production per year (for BC allocation) ────────
_fish = fish_fbs[
    (fish_fbs["Element"] == "Production") & (fish_fbs["Area Code"] < 5000)
].copy()
# Production is in 1000 tonnes
world_fish_prod_by_year = (
    _fish.groupby("Year")["Value"].sum().rename("world_fish_prod_kt")
)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. COMPONENT CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_cropland_ef(area_code, year):
    """
    Cropland EF = Σ_crops (Production_t / WorldYield_t_per_ha) × EQF_cropland
    """
    rows = crop_prod[
        (crop_prod["Area Code"] == area_code)
        & (crop_prod["Year"] == year)
        & (crop_prod["Element"] == "Production")
    ]
    total_ha = 0.0
    for _, r in rows.iterrows():
        item_code = r["Item Code"]
        prod_t = r["Value"]
        if pd.isna(prod_t) or prod_t <= 0:
            continue
        try:
            yw = world_crop_yield.loc[(item_code, year), "world_yield_t_per_ha"]
        except KeyError:
            continue
        if yw > 0:
            total_ha += prod_t / yw
    return total_ha * EQF_CROPLAND


def calc_cropland_bc(area_code, year):
    """
    Cropland BC = (Arable land + Permanent crops) in ha × YF × EQF_cropland
    YF = national_yield / world_yield  (computed as weighted average across crops)
    Simplified: just use area × EQF (YF ≈ 1.0 when aggregated)
    Better: compute YF from crop data.
    """
    # Get national cropland area (Arable land 6621 + Permanent crops 6650)
    cond = (
        (cropland_area["Area Code"] == area_code)
        & (cropland_area["Year"] == year)
        & (cropland_area["Item Code"].isin([6621, 6650]))
    )
    area_1000ha = cropland_area.loc[cond, "Value"].sum()
    area_ha = area_1000ha * 1000  # convert from 1000 ha to ha

    # Compute yield factor: national yield / world yield (weighted by production)
    nat_prod = crop_prod[
        (crop_prod["Area Code"] == area_code)
        & (crop_prod["Year"] == year)
        & (crop_prod["Element"] == "Production")
    ]
    nat_area_harv = crop_prod[
        (crop_prod["Area Code"] == area_code)
        & (crop_prod["Year"] == year)
        & (crop_prod["Element"] == "Area harvested")
    ]
    nat_prod_total = nat_prod["Value"].sum()
    nat_area_total = nat_area_harv["Value"].sum()

    if nat_area_total > 0 and nat_prod_total > 0:
        nat_yield = nat_prod_total / nat_area_total
        # World average yield across all crops
        wld = world_crop_yield.loc[world_crop_yield.index.get_level_values("Year") == year]
        world_prod_total = wld["world_production_t"].sum()
        world_area_total = wld["world_area_ha"].sum()
        if world_area_total > 0:
            world_yield = world_prod_total / world_area_total
            yf = nat_yield / world_yield
        else:
            yf = 1.0
    else:
        yf = 1.0

    return area_ha * yf * EQF_CROPLAND


def calc_grazing_ef(area_code, year):
    """
    Grazing EF = Σ (livestock_heads × annual_pasture_demand_t) / grassland_NPP × EQF
    """
    rows = livestock[
        (livestock["Area Code"] == area_code) & (livestock["Year"] == year)
    ]
    total_pasture_demand_t = 0.0
    for _, r in rows.iterrows():
        item = r["Item"]
        heads = r["Value"]
        if pd.isna(heads) or heads <= 0:
            continue
        demand = GLEAM_PASTURE.get(item, 0.0)
        total_pasture_demand_t += heads * demand

    if total_pasture_demand_t <= 0:
        return 0.0
    area_ha = total_pasture_demand_t / GRASSLAND_NPP
    return area_ha * EQF_GRAZING


def calc_grazing_bc(area_code, year):
    """
    Grazing BC = pasture_area_ha × YF_grazing × EQF_grazing
    YF_grazing ≈ 1.0
    """
    cond = (
        (pasture_area["Area Code"] == area_code) & (pasture_area["Year"] == year)
    )
    area_1000ha = pasture_area.loc[cond, "Value"].sum()
    return area_1000ha * 1000 * 1.0 * EQF_GRAZING


def calc_forest_ef(area_code, year):
    """
    Forest EF = roundwood_production_m3 / NAI × EQF_forest
    """
    cond = (
        (timber["Area Code"] == area_code)
        & (timber["Year"] == year)
        & (timber["Item"] == "Roundwood")
        & (timber["Element"] == "Production")
    )
    prod_m3 = timber.loc[cond, "Value"].sum()
    if prod_m3 <= 0:
        return 0.0
    return (prod_m3 / FOREST_NAI) * EQF_FOREST


def calc_forest_bc(area_code, year):
    """
    Forest BC = forest_area_ha × YF_forest × EQF_forest
    YF_forest ≈ 1.0
    """
    cond = (
        (forest_area["Area Code"] == area_code) & (forest_area["Year"] == year)
    )
    area_1000ha = forest_area.loc[cond, "Value"].sum()
    return area_1000ha * 1000 * 1.0 * EQF_FOREST


def calc_fishing_ef(area_code, year):
    """
    Fishing EF using PPR method:
    PPR = catch_t × discard_rate × (1/TE)^(TL-1) / wet_to_carbon
    EF = PPR / marine_yield_per_ha × EQF

    marine_yield_per_ha = world sustainable PPR / continental_shelf_area
    """
    rows = fish_fbs[
        (fish_fbs["Area Code"] == area_code)
        & (fish_fbs["Year"] == year)
        & (fish_fbs["Element"] == "Production")
    ]
    total_ppr = 0.0
    for _, r in rows.iterrows():
        item = r["Item"]
        prod_kt = r["Value"]
        if pd.isna(prod_kt) or prod_kt <= 0:
            continue
        tl = TROPHIC_LEVELS.get(item)
        if tl is None:
            continue  # skip non-fish items like Aquatic Plants, Fish Oil
        prod_t = prod_kt * 1000  # convert from 1000 tonnes to tonnes
        ppr = prod_t * DISCARD_RATE * (1.0 / TRANSFER_EFFICIENCY) ** (tl - 1) / WET_TO_CARBON
        total_ppr += ppr

    if total_ppr <= 0:
        return 0.0

    # World sustainable PPR (from 93 Mt sustainable catch at avg TL ~3.1)
    avg_tl = 3.1
    world_sust_ppr = (
        SUSTAINABLE_CATCH_MT * 1e6
        * DISCARD_RATE
        * (1.0 / TRANSFER_EFFICIENCY) ** (avg_tl - 1)
        / WET_TO_CARBON
    )
    marine_yield = world_sust_ppr / CONTINENTAL_SHELF_HA  # PPR per ha
    area_ha = total_ppr / marine_yield
    return area_ha * EQF_FISHING


def calc_fishing_bc(area_code, year):
    """
    Fishing BC allocated proportionally by country's share of world fish production.
    World fishing BC = continental_shelf_area × EQF_fishing
    Country BC = world_BC × (country_prod / world_prod)
    """
    world_bc = CONTINENTAL_SHELF_HA * EQF_FISHING

    cond = (
        (fish_fbs["Area Code"] == area_code)
        & (fish_fbs["Year"] == year)
        & (fish_fbs["Element"] == "Production")
    )
    country_prod = fish_fbs.loc[cond, "Value"].sum()  # in 1000 t
    try:
        world_prod = world_fish_prod_by_year.loc[year]
    except KeyError:
        return 0.0
    if world_prod <= 0:
        return 0.0
    share = country_prod / world_prod
    return world_bc * share


def calc_built_up(area_code, year):
    """
    Built-up area = Land area (6601) - Agricultural land (6610) - Forest land (6646)
                    - Other land (6670) - Inland waters (6680)
    EF = BC = built_up_area_ha × EQF_built_up
    """
    items_needed = {6601: 0, 6610: 0, 6646: 0, 6670: 0, 6680: 0}
    cond = (
        (land_use_all["Area Code"] == area_code)
        & (land_use_all["Year"] == year)
        & (land_use_all["Item Code"].isin(items_needed.keys()))
    )
    subset = land_use_all.loc[cond, ["Item Code", "Value"]]
    for _, r in subset.iterrows():
        items_needed[r["Item Code"]] = r["Value"] if not pd.isna(r["Value"]) else 0

    land_area = items_needed[6601]
    ag_land = items_needed[6610]
    forest = items_needed[6646]
    other = items_needed[6670]
    inland_water = items_needed[6680]

    built_up_1000ha = land_area - ag_land - forest - other - inland_water
    # Clamp to 0 if negative (data inconsistency)
    built_up_1000ha = max(0, built_up_1000ha)
    built_up_ha = built_up_1000ha * 1000
    return built_up_ha * EQF_BUILT_UP


def calc_carbon_ef(area_code, year):
    """
    Carbon EF = CO2_kt × 1000 × (1 - ocean_frac) / (AFCS × 44/12) × EQF_carbon
    AFCS in t C/ha/yr → convert to t CO2/ha/yr: AFCS × 44/12
    """
    cond = (
        (co2_energy["Area Code"] == area_code)
        & (co2_energy["Year"] == year)
    )
    co2_kt = co2_energy.loc[cond, "Value"].sum()
    if co2_kt <= 0:
        return 0.0
    co2_tonnes = co2_kt * 1000
    land_co2 = co2_tonnes * (1 - OCEAN_CO2_FRAC)
    seq_rate_co2 = AFCS * (44.0 / 12.0)  # t CO2 / ha / yr
    area_ha = land_co2 / seq_rate_co2
    return area_ha * EQF_CARBON


def get_population(area_code, year):
    """Get population in thousands."""
    cond = (
        (population["Area Code"] == area_code) & (population["Year"] == year)
    )
    val = population.loc[cond, "Value"]
    if len(val) == 0:
        return np.nan
    return val.iloc[0]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BUILD COUNTRY LIST & COMPUTE
# ═══════════════════════════════════════════════════════════════════════════════
print("Building country list...")

# Use population file as the master country list (excludes aggregates)
pop_countries = population[population["Area Code"] < 5000][
    ["Area Code", "Area"]
].drop_duplicates()
countries = list(pop_countries.itertuples(index=False, name=None))
# countries is list of (area_code, area_name)

print(f"Processing {len(countries)} countries × {len(YEARS)} years...")

# Pre-index dataframes for faster lookup
print("  Indexing dataframes...")
crop_prod.set_index(["Area Code", "Year", "Element", "Item Code"], inplace=True)
crop_prod.sort_index(inplace=True)

# Revert to row-by-row but with faster filtering using pre-grouped data
# Actually, let's use a vectorized approach where possible

# Reset index for crop_prod (we set it above prematurely)
crop_prod.reset_index(inplace=True)

# ── Vectorized Cropland EF ──────────────────────────────────────────────────
print("  Computing cropland EF (vectorized)...")
_cp_nat = crop_prod[
    (crop_prod["Area Code"] < 5000) & (crop_prod["Element"] == "Production")
].copy()
_cp_nat = _cp_nat.merge(
    world_crop_yield[["world_yield_t_per_ha"]].reset_index(),
    on=["Item Code", "Year"],
    how="left",
)
_cp_nat["ha_equivalent"] = np.where(
    _cp_nat["world_yield_t_per_ha"] > 0,
    _cp_nat["Value"] / _cp_nat["world_yield_t_per_ha"],
    0,
)
cropland_ef_df = (
    _cp_nat.groupby(["Area Code", "Year"])["ha_equivalent"]
    .sum()
    .reset_index()
    .rename(columns={"ha_equivalent": "ef_cropland_gha"})
)
cropland_ef_df["ef_cropland_gha"] *= EQF_CROPLAND

# ── Vectorized Cropland BC ──────────────────────────────────────────────────
print("  Computing cropland BC (vectorized)...")
# National cropland area
_cla = cropland_area[
    (cropland_area["Area Code"] < 5000)
    & (cropland_area["Item Code"].isin([6621, 6650]))
].copy()
nat_cropland_ha = (
    _cla.groupby(["Area Code", "Year"])["Value"]
    .sum()
    .reset_index()
    .rename(columns={"Value": "cropland_1000ha"})
)
nat_cropland_ha["cropland_ha"] = nat_cropland_ha["cropland_1000ha"] * 1000

# National yield factor
_cp_nat_prod = (
    crop_prod[
        (crop_prod["Area Code"] < 5000) & (crop_prod["Element"] == "Production")
    ]
    .groupby(["Area Code", "Year"])["Value"]
    .sum()
    .rename("nat_prod")
)
_cp_nat_area = (
    crop_prod[
        (crop_prod["Area Code"] < 5000) & (crop_prod["Element"] == "Area harvested")
    ]
    .groupby(["Area Code", "Year"])["Value"]
    .sum()
    .rename("nat_area")
)
nat_yields = pd.concat([_cp_nat_prod, _cp_nat_area], axis=1).reset_index()
nat_yields["nat_yield"] = np.where(
    nat_yields["nat_area"] > 0,
    nat_yields["nat_prod"] / nat_yields["nat_area"],
    np.nan,
)

# World average yield per year
wld_yields = world_crop_yield.groupby("Year").agg(
    world_prod=("world_production_t", "sum"),
    world_area=("world_area_ha", "sum"),
).reset_index()
wld_yields["world_yield"] = wld_yields["world_prod"] / wld_yields["world_area"]

nat_yields = nat_yields.merge(wld_yields[["Year", "world_yield"]], on="Year", how="left")
nat_yields["yf"] = np.where(
    (nat_yields["world_yield"] > 0) & (nat_yields["nat_yield"].notna()),
    nat_yields["nat_yield"] / nat_yields["world_yield"],
    1.0,
)
# Cap YF at reasonable range to prevent outliers
nat_yields["yf"] = nat_yields["yf"].clip(0.01, 10.0)

cropland_bc_df = nat_cropland_ha.merge(
    nat_yields[["Area Code", "Year", "yf"]], on=["Area Code", "Year"], how="left"
)
cropland_bc_df["yf"] = cropland_bc_df["yf"].fillna(1.0)
cropland_bc_df["bc_cropland_gha"] = (
    cropland_bc_df["cropland_ha"] * cropland_bc_df["yf"] * EQF_CROPLAND
)

# ── Vectorized Grazing EF ───────────────────────────────────────────────────
print("  Computing grazing EF (vectorized)...")
_ls = livestock[livestock["Area Code"] < 5000].copy()
_ls["pasture_demand"] = _ls["Item"].map(GLEAM_PASTURE).fillna(0)
_ls["total_demand_t"] = _ls["Value"].fillna(0) * _ls["pasture_demand"]
grazing_ef_df = (
    _ls.groupby(["Area Code", "Year"])["total_demand_t"]
    .sum()
    .reset_index()
)
grazing_ef_df["ef_grazing_gha"] = np.where(
    grazing_ef_df["total_demand_t"] > 0,
    (grazing_ef_df["total_demand_t"] / GRASSLAND_NPP) * EQF_GRAZING,
    0,
)

# ── Vectorized Grazing BC ───────────────────────────────────────────────────
print("  Computing grazing BC (vectorized)...")
_pa = pasture_area[pasture_area["Area Code"] < 5000].copy()
grazing_bc_df = (
    _pa.groupby(["Area Code", "Year"])["Value"]
    .sum()
    .reset_index()
    .rename(columns={"Value": "pasture_1000ha"})
)
grazing_bc_df["bc_grazing_gha"] = grazing_bc_df["pasture_1000ha"] * 1000 * EQF_GRAZING

# ── Vectorized Forest EF ────────────────────────────────────────────────────
print("  Computing forest EF (vectorized)...")
_tm = timber[
    (timber["Area Code"] < 5000)
    & (timber["Item"] == "Roundwood")
    & (timber["Element"] == "Production")
].copy()
forest_ef_df = (
    _tm.groupby(["Area Code", "Year"])["Value"]
    .sum()
    .reset_index()
    .rename(columns={"Value": "roundwood_m3"})
)
forest_ef_df["ef_forest_gha"] = np.where(
    forest_ef_df["roundwood_m3"] > 0,
    (forest_ef_df["roundwood_m3"] / FOREST_NAI) * EQF_FOREST,
    0,
)

# ── Vectorized Forest BC ────────────────────────────────────────────────────
print("  Computing forest BC (vectorized)...")
_fa = forest_area[forest_area["Area Code"] < 5000].copy()
forest_bc_df = (
    _fa.groupby(["Area Code", "Year"])["Value"]
    .sum()
    .reset_index()
    .rename(columns={"Value": "forest_1000ha"})
)
forest_bc_df["bc_forest_gha"] = forest_bc_df["forest_1000ha"] * 1000 * EQF_FOREST

# ── Vectorized Fishing EF ───────────────────────────────────────────────────
print("  Computing fishing EF (vectorized)...")
_ff = fish_fbs[
    (fish_fbs["Area Code"] < 5000)
    & (fish_fbs["Element"] == "Production")
].copy()
_ff["tl"] = _ff["Item"].map(TROPHIC_LEVELS)
_ff = _ff.dropna(subset=["tl"])
_ff["prod_t"] = _ff["Value"].fillna(0) * 1000  # 1000 t → t
_ff["ppr"] = (
    _ff["prod_t"]
    * DISCARD_RATE
    * (1.0 / TRANSFER_EFFICIENCY) ** (_ff["tl"] - 1)
    / WET_TO_CARBON
)

# World sustainable PPR for marine yield denominator
avg_tl = 3.1
world_sust_ppr = (
    SUSTAINABLE_CATCH_MT * 1e6
    * DISCARD_RATE
    * (1.0 / TRANSFER_EFFICIENCY) ** (avg_tl - 1)
    / WET_TO_CARBON
)
marine_yield_per_ha = world_sust_ppr / CONTINENTAL_SHELF_HA

fishing_ef_df = (
    _ff.groupby(["Area Code", "Year"])["ppr"]
    .sum()
    .reset_index()
)
fishing_ef_df["ef_fishing_gha"] = (
    fishing_ef_df["ppr"] / marine_yield_per_ha * EQF_FISHING
)

# ── Vectorized Fishing BC ───────────────────────────────────────────────────
print("  Computing fishing BC (vectorized)...")
world_fishing_bc = CONTINENTAL_SHELF_HA * EQF_FISHING

country_fish_prod = (
    _ff.groupby(["Area Code", "Year"])["prod_t"]
    .sum()
    .reset_index()
    .rename(columns={"prod_t": "country_prod_t"})
)
world_fish_by_year = (
    _ff.groupby("Year")["prod_t"].sum().rename("world_prod_t").reset_index()
)
fishing_bc_df = country_fish_prod.merge(world_fish_by_year, on="Year", how="left")
fishing_bc_df["bc_fishing_gha"] = np.where(
    fishing_bc_df["world_prod_t"] > 0,
    world_fishing_bc * (fishing_bc_df["country_prod_t"] / fishing_bc_df["world_prod_t"]),
    0,
)

# ── Vectorized Built-up EF/BC ───────────────────────────────────────────────
print("  Computing built-up area (vectorized)...")
# Strategy: Use item 6649 (Farm buildings & Farmyards) where available.
# For countries without it, estimate built-up as residual of land area minus other uses,
# clamped to zero. Where residual is negative (data inconsistency), fall back to
# 3% of cropland area as a proxy (GFN treats built-up as replacing cropland).
_lu = land_use_all[
    (land_use_all["Area Code"] < 5000)
    & (land_use_all["Unit"] == "1000 ha")
].copy()

# First try item 6649 directly
_bu_direct = _lu[_lu["Item Code"] == 6649][["Area Code", "Year", "Value"]].copy()
_bu_direct = _bu_direct.rename(columns={"Value": "built_up_1000ha"})

# For countries without 6649, compute residual
_lu_pivot = _lu[_lu["Item Code"].isin([6601, 6610, 6646, 6670, 6680])].pivot_table(
    index=["Area Code", "Year"],
    columns="Item Code",
    values="Value",
    aggfunc="first",
).reset_index()
for col in [6601, 6610, 6646, 6670, 6680]:
    if col not in _lu_pivot.columns:
        _lu_pivot[col] = 0
_lu_pivot = _lu_pivot.fillna(0)
_lu_pivot["residual"] = (
    _lu_pivot[6601] - _lu_pivot[6610] - _lu_pivot[6646]
    - _lu_pivot[6670] - _lu_pivot[6680]
)

# Merge: prefer 6649, then positive residual, then cropland proxy
built_up_df = _lu_pivot[["Area Code", "Year", "residual"]].merge(
    _bu_direct, on=["Area Code", "Year"], how="left"
)
# Also get cropland area for fallback
_cropland_for_bu = nat_cropland_ha[["Area Code", "Year", "cropland_1000ha"]].copy()
built_up_df = built_up_df.merge(_cropland_for_bu, on=["Area Code", "Year"], how="left")
built_up_df["cropland_1000ha"] = built_up_df["cropland_1000ha"].fillna(0)

# Use 6649 if available, else positive residual, else 3% of cropland
built_up_df["final_1000ha"] = np.where(
    built_up_df["built_up_1000ha"].notna(),
    built_up_df["built_up_1000ha"],
    np.where(
        built_up_df["residual"] > 0,
        built_up_df["residual"],
        built_up_df["cropland_1000ha"] * 0.03,
    ),
)
built_up_df["built_up_1000ha"] = built_up_df["final_1000ha"]
built_up_df["ef_built_up_gha"] = built_up_df["built_up_1000ha"] * 1000 * EQF_BUILT_UP
built_up_df["bc_built_up_gha"] = built_up_df["ef_built_up_gha"]  # EF = BC for built-up

# ── Vectorized Carbon EF ────────────────────────────────────────────────────
print("  Computing carbon EF (vectorized)...")
_co2 = co2_energy[co2_energy["Area Code"] < 5000].copy()
carbon_ef_df = (
    _co2.groupby(["Area Code", "Year"])["Value"]
    .sum()
    .reset_index()
    .rename(columns={"Value": "co2_kt"})
)
seq_rate_co2 = AFCS * (44.0 / 12.0)
carbon_ef_df["ef_carbon_gha"] = np.where(
    carbon_ef_df["co2_kt"] > 0,
    (carbon_ef_df["co2_kt"] * 1000 * (1 - OCEAN_CO2_FRAC) / seq_rate_co2) * EQF_CARBON,
    0,
)

# ── Population ──────────────────────────────────────────────────────────────
print("  Extracting population...")
pop_df = population[
    (population["Area Code"] < 5000)
    & (population["Element"] == "Total Population - Both sexes")
][["Area Code", "Area", "Year", "Value"]].copy()
pop_df = pop_df.rename(columns={"Value": "population"})
# population is in thousands


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MERGE ALL COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════
print("Merging components...")

# Start from population as base
result = pop_df[["Area Code", "Area", "Year", "population"]].copy()
result = result.rename(columns={"Area Code": "area_code", "Area": "area", "Year": "year"})

# Merge each component
def merge_component(result_df, comp_df, cols, key_cols=["Area Code", "Year"]):
    comp_df = comp_df[key_cols + cols].copy()
    comp_df = comp_df.rename(columns={"Area Code": "area_code", "Year": "year"})
    return result_df.merge(comp_df, on=["area_code", "year"], how="left")

result = merge_component(result, cropland_ef_df, ["ef_cropland_gha"])
result = merge_component(result, cropland_bc_df, ["bc_cropland_gha"])
result = merge_component(result, grazing_ef_df, ["ef_grazing_gha"])
result = merge_component(result, grazing_bc_df, ["bc_grazing_gha"])
result = merge_component(result, forest_ef_df, ["ef_forest_gha"])
result = merge_component(result, forest_bc_df, ["bc_forest_gha"])
result = merge_component(result, fishing_ef_df, ["ef_fishing_gha"])
result = merge_component(result, fishing_bc_df, ["bc_fishing_gha"])
result = merge_component(result, built_up_df, ["ef_built_up_gha", "bc_built_up_gha"])
result = merge_component(result, carbon_ef_df, ["ef_carbon_gha"])

# Fill NaN with 0 for footprint/biocapacity columns
ef_bc_cols = [
    "ef_cropland_gha", "ef_grazing_gha", "ef_forest_gha",
    "ef_fishing_gha", "ef_built_up_gha", "ef_carbon_gha",
    "bc_cropland_gha", "bc_grazing_gha", "bc_forest_gha",
    "bc_fishing_gha", "bc_built_up_gha",
]
result[ef_bc_cols] = result[ef_bc_cols].fillna(0)

# Compute totals
result["ef_total_gha"] = (
    result["ef_cropland_gha"]
    + result["ef_grazing_gha"]
    + result["ef_forest_gha"]
    + result["ef_fishing_gha"]
    + result["ef_built_up_gha"]
    + result["ef_carbon_gha"]
)
result["bc_total_gha"] = (
    result["bc_cropland_gha"]
    + result["bc_grazing_gha"]
    + result["bc_forest_gha"]
    + result["bc_fishing_gha"]
    + result["bc_built_up_gha"]
)
result["ecological_deficit_gha"] = result["bc_total_gha"] - result["ef_total_gha"]

# Per capita (population is in thousands)
result["ef_per_capita_gha"] = np.where(
    result["population"] > 0,
    result["ef_total_gha"] / (result["population"] * 1000),
    np.nan,
)
result["bc_per_capita_gha"] = np.where(
    result["population"] > 0,
    result["bc_total_gha"] / (result["population"] * 1000),
    np.nan,
)

# Order columns
output_cols = [
    "area_code", "area", "year",
    "ef_cropland_gha", "ef_grazing_gha", "ef_forest_gha",
    "ef_fishing_gha", "ef_built_up_gha", "ef_carbon_gha",
    "ef_total_gha",
    "bc_cropland_gha", "bc_grazing_gha", "bc_forest_gha",
    "bc_fishing_gha", "bc_built_up_gha",
    "bc_total_gha",
    "ecological_deficit_gha",
    "population",
    "ef_per_capita_gha", "bc_per_capita_gha",
]
result = result[output_cols].sort_values(["area_code", "year"])

# ═══════════════════════════════════════════════════════════════════════════════
# 6. SAVE COUNTRY-LEVEL RESULTS
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Saving country results to {OUT_COUNTRY}...")
result.to_csv(OUT_COUNTRY, index=False)
print(f"  → {len(result)} rows, {len(result['area_code'].unique())} countries")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. GLOBAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("Computing global summary...")

global_summary = result.groupby("year").agg(
    world_ef_gha=("ef_total_gha", "sum"),
    world_bc_gha=("bc_total_gha", "sum"),
).reset_index()

global_summary["overshoot_gha"] = (
    global_summary["world_ef_gha"] - global_summary["world_bc_gha"]
)
global_summary["number_of_earths"] = (
    global_summary["world_ef_gha"] / global_summary["world_bc_gha"]
)
# Overshoot Day = day of year when humanity has used a year's worth of BC
# = 365 × (BC / EF)
global_summary["overshoot_day"] = np.where(
    global_summary["number_of_earths"] > 1,
    np.floor(365 * global_summary["world_bc_gha"] / global_summary["world_ef_gha"]).astype(int),
    np.nan,  # no overshoot
)

print(f"Saving global summary to {OUT_GLOBAL}...")
global_summary.to_csv(OUT_GLOBAL, index=False)

# ═══════════════════════════════════════════════════════════════════════════════
# 8. VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

# Global summary
print("\nGlobal Summary:")
print(global_summary.to_string(index=False))

# Spot-check USA (Area Code 231)
usa = result[result["area_code"] == 231]
if not usa.empty:
    print("\n\nUSA spot check (2023):")
    usa_2023 = usa[usa["year"] == 2023]
    if not usa_2023.empty:
        for col in output_cols[3:]:
            print(f"  {col:30s}: {usa_2023[col].iloc[0]:>15,.2f}")

# Spot-check China (Area Code 351)
chn = result[result["area_code"] == 351]
if chn.empty:
    # Try area code 41 (China, mainland)
    chn = result[result["area_code"] == 41]
if not chn.empty:
    print(f"\n\nChina spot check (2023) [area_code={chn['area_code'].iloc[0]}]:")
    chn_2023 = chn[chn["year"] == 2023]
    if not chn_2023.empty:
        for col in output_cols[3:]:
            print(f"  {col:30s}: {chn_2023[col].iloc[0]:>15,.2f}")

print("\nDone!")
