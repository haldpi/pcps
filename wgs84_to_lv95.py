# Script to convert WGS84 coordinates to LV95 / EPSG:2056

import os
from pathlib import Path

import pandas as pd
import yaml
from pyproj import Transformer

SETTINGS_PATH = "data/settings.yaml"
REQUIRED_KEYS = ("input_file", "lat_col", "lon_col")


def main():
    print("Welcome to the WGS84 to LV95 transformer.\n")
    print("Supported file formats: .xlsx, .csv, .ods\n")

    settings = fileLoader()      # load + maybe prompt for changes
    save_settings(settings)      # persist (first run creates the file)
    transformation(settings)     # do the work


# ----- settings I/O ----- #

def load_settings():
    defaults = {"input_file": "", "lat_col": "", "lon_col": ""}
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return defaults
    except yaml.YAMLError as e:
        print(f"Invalid settings file ({e}); using defaults.")
        return defaults
    return {**defaults, **{k: data.get(k, defaults[k]) for k in REQUIRED_KEYS}}


def save_settings(settings):
    parent = os.path.dirname(SETTINGS_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


def have_settings(settings):
    return all(settings.get(k) for k in REQUIRED_KEYS)


# ----- interactive flow ----- #

def fileLoader():
    """Load settings, prompt to fill/change them, return the final dict."""
    settings = load_settings()

    if not have_settings(settings):
        print("\nNo saved settings found.")
        return input_prompt(settings)

    print("\nFollowing settings have been loaded:")
    for k in REQUIRED_KEYS:
        print(f"  {k}: {settings[k]}")

    if settingsRequester():
        return input_prompt(settings)   # keep loaded values as defaults
    return settings


def settingsRequester():
    """Return True if the user wants to change settings."""
    while True:
        raw = input("\nDo you want to change the settings? (y | n) [y]: ").strip().lower()
        if not raw or raw in ("y", "j"):
            return True
        if raw == "n":
            return False
        print("Please answer 'y' or 'n'.")


def ask_with_default(prompt, current):
    shown = current if current else "<empty>"
    answer = input(f"{prompt} [current: {shown}]: ").strip().strip('"\'')
    return answer if answer else current


def input_prompt(current):
    """Collect settings; empty input keeps the current value."""
    print("\nPlease confirm the following prompts (Enter keeps current):\n")
    input_file = ask_with_default("Path/name of the input file", current["input_file"])
    lat_col    = ask_with_default("Name of the latitude column",  current["lat_col"])
    lon_col    = ask_with_default("Name of the longitude column", current["lon_col"])
    return {"input_file": input_file, "lat_col": lat_col, "lon_col": lon_col}


# ----- conversion ----- #

def read_table(path):
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return read_csv(path)
    if ext in (".xlsx", ".xlsm"):
        return pd.read_excel(path, sheet_name=0)            # openpyxl
    if ext == ".ods":
        return pd.read_excel(path, sheet_name=0, engine="odf")  # odfpy
    raise ValueError(f"Unsupported file type: {ext} "
                     f"(expected .csv, .xlsx, .xlsm or .ods)")


def read_csv(path):
    """Read a CSV, tolerating European formatting (; separator, , decimal,
    non-UTF-8 encodings)."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                first_line = f.readline()
            # Delimiter heuristic on the header line.
            sep = ";" if first_line.count(";") >= first_line.count(",") else ","
            decimal = "," if sep == ";" else "."
            return pd.read_csv(path, sep=sep, decimal=decimal, encoding=encoding)
        except UnicodeDecodeError:
            continue  # try the next encoding
    raise ValueError(f"Could not decode {path} with any known encoding")
    

def make_output_path(input_file):
    src = Path(input_file)
    return src.with_name(f"{src.stem}_converted.xlsx")       # always xlsx


def transformation(settings):
    input_file = settings["input_file"]
    lat_col    = settings["lat_col"]
    lon_col    = settings["lon_col"]

    df = read_table(input_file)

    for col in (lat_col, lon_col):
        if col not in df.columns:
            raise KeyError(f"Column '{col}' not found. Available: {list(df.columns)}")

    # WGS84 (lon, lat) -> LV95/EPSG:2056 (east, north)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)
    east, north = transformer.transform(df[lon_col].values, df[lat_col].values)

    df["E_2056"] = east
    df["N_2056"] = north

    output_file = make_output_path(input_file)
    df.to_excel(output_file, index=False)
    print(f"\nConverted {len(df)} rows to {output_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to exit...")