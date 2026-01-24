from datetime import date, timedelta
import tomllib
from pathlib import Path

import pandas as pd

dir = Path(__file__).parent

config_file = dir / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

daily_folder = Path(
    f"{config['general']['output_folder']}/daily-with-udiff"
).expanduser()

isin_file = daily_folder / "isin.csv"

if isin_file.exists():
    isin_file.replace(daily_folder.parent / "isin.csv")

dt = date.today() - timedelta(365)
dups = 0
count = 0

for file in daily_folder.iterdir():
    try:
        df = pd.read_csv(file, index_col="Date", parse_dates=["Date"])
    except Exception as e:
        print(file)
        raise e

    if config["cleanup"]["remove_outdated"]:
        if df.index[-1].date() <= dt:
            print(f"expired -> {file.name}")
            file.unlink()
            count += 1
            continue

    if df.index.has_duplicates:
        df = df.loc[~df.index.duplicated(keep="first")]
        # print(f"duplicates -> {file.name}")
        df.to_csv(file)
        dups += 1

    if not df.index.is_monotonic_increasing:
        df = df.sort_index(ascending=True)
        df.to_csv(file)
        print("sorting issues ->", file.name)


print("Deleted", count, "DUPS", dups)
