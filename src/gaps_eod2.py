from pathlib import Path
import tomllib

import pandas as pd

"""
Looks for large gaps in EOD2_DATA trading dates in case of suspension of trading

These are stocks with more than 365 days of no trading
"""

DIR = Path(__file__).parent
config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

daily = Path(config["general"]["output_folder"]).expanduser() / "daily-with-udiff"

lst = ["name,date"]

for file in daily.iterdir():
    if "nifty50 equal weight" in file.name:
        continue

    df = pd.read_csv(file, parse_dates=["Date"])

    df.loc[:, "days"] = (df["Date"] - df["Date"].shift()).dt.days

    if df["days"].max() > 365:
        dt = max(list(df[df["days"] > 365]["Date"]))
        df.set_index("Date", drop=True, inplace=True)
        df = df.drop("days", axis=1)

        df = df.loc[dt:]

        df.to_csv(file)

        lst.append(f"{file.name},{dt}")

(DIR / "mod_files.csv").write_text("\n".join(lst))
