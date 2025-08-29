import shutil
from datetime import timedelta
from pathlib import Path
import tomllib

import pandas as pd

DIR = Path(__file__).parent
config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)


BASE = Path(config["general"]["bhav_folder"]).expanduser()
DAILY = Path(f"{config['general']['output_folder']}/daily-no-isin").expanduser()

if DAILY.exists():
    # delete the folder and its contents
    shutil.rmtree(DAILY)

DAILY.mkdir(parents=True)

headerText = b"Date,Open,High,Low,Close,Volume,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"

dt = config["collate"]["no_isin"]["start_date"]
end_date = config["collate"]["no_isin"]["end_date"]

while dt <= end_date:
    dt = dt + timedelta(1)

    dt_str = dt.strftime("%d%b%Y").upper()

    print(dt.strftime("%d-%b-%Y"), flush=True, end="\r" * 11)

    bhav_file = BASE / f"{dt.year}/cm{dt_str}bhav.csv"

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="SYMBOL")

    df = df[df["SERIES"].isin(["EQ", "BE", "BZ", "SM", "ST"])]

    dup = None

    if df.index.has_duplicates:
        dup = df.loc[df.index.duplicated()]

        dup = dup.loc[dup["SERIES"] == "EQ"]

    pandas_dt = dt.strftime("%Y-%m-%d")

    for symbol in df.index:
        series = df.at[symbol, "SERIES"]

        prefix = ""

        if isinstance(series, pd.Series):
            if series.str.contains("SM|ST").any():
                prefix = "_sme"
        else:
            if series == "SM" or series == "ST":
                prefix = "_sme"

        if dup is not None and symbol in dup.index:
            O, H, L, C, V = dup.loc[
                symbol, ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY"]
            ]
        else:
            O, H, L, C, V = df.loc[
                symbol, ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY"]
            ]

        sym_file = DAILY / f"{symbol.lower()}{prefix}.csv"

        txt = b""

        if not sym_file.exists():
            txt += headerText

        txt += bytes(f"{pandas_dt},{O},{H},{L},{C},{V},,,\n", encoding="utf-8")

        with sym_file.open("ab") as f:
            f.write(txt)

print("complete")
