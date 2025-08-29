import shutil
from datetime import timedelta
from pathlib import Path
import tomllib

import numpy as np
import pandas as pd

"""
Updated 8th July 2024
- Updated to include delivery data
- Udiff format not suported
"""

DIR = Path(__file__).parent
config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()
basePath = Path(config["general"]["bhav_folder"]).expanduser()
DAILY = output_folder / "daily-with-isin"
DELIVERY = Path(config["general"]["delivery_folder"]).expanduser()

# Remove any pre-existing folder from previous run
if DAILY.exists():
    shutil.rmtree(DAILY)

# Check DAILY_NO_ISIN folder exists and is not empty
DAILY_NO_ISIN = output_folder / "daily-no-isin"

if not DAILY_NO_ISIN.exists():
    raise RuntimeError(
        f"Folder not found: {DAILY_NO_ISIN.name}. Run collate_no_isin.py"
    )

if not any(DAILY_NO_ISIN.iterdir()):
    raise RuntimeError(
        f"Folder is empty: {DAILY_NO_ISIN.name}. Run collate_no_isin.py "
    )

shutil.copytree(DAILY_NO_ISIN, DAILY, dirs_exist_ok=False)


headerText = b"Date,Open,High,Low,Close,Volume,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"

# EDIT BELOW - which ever date you start, one day prior
dt = config["collate"]["with_isin"]["start_date"]

# Dont change BELOW - post this date bhav copies are in udiff format
end_date = config["collate"]["with_isin"]["end_date"]

# EDIT THIS TO FIRST BHAVCOPY YOU HAVE
isin = pd.read_csv(basePath / "2011/cm22JUN2011bhav.csv", index_col="ISIN")

isin = isin[isin["SERIES"].isin(["EQ", "BE", "BZ", "SM", "ST"])]

print("isin", isin.shape)

while dt <= end_date:
    dt = dt + timedelta(1)

    dt_str = dt.strftime("%d%b%Y").upper()

    bhav_file = basePath / f"{dt.year}/cm{dt_str}bhav.csv"

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="ISIN")

    df = df[df["SERIES"].isin(["EQ", "BE", "BZ", "SM", "ST"])]

    dlv_df = None

    dlv_file = DELIVERY / f"{dt.year}/sec_bhavdata_full_{dt:%d%m%Y}.csv"

    if dlv_file.exists():
        dlv_df = pd.read_csv(dlv_file, index_col="SYMBOL")
        dlv_df = dlv_df[dlv_df[" SERIES"].isin([" EQ", " BE", " BZ", " SM", " ST"])]

    dup = None

    if df.index.has_duplicates:
        dup = df.loc[df.index.duplicated(keep=False)]

        dup = dup.loc[dup["SERIES"] == "EQ"]

    pandas_dt = dt.strftime("%Y-%m-%d")

    for idx in df.index:
        sym, series = df.loc[idx, ["SYMBOL", "SERIES"]]

        if "-RE" in sym:
            continue

        prefix = ""

        if isinstance(series, pd.Series):
            if series.str.contains("SM|ST").any():
                prefix = "_sme"
        else:
            if series == "SM" or series == "ST":
                prefix = "_sme"

        sym_file = DAILY / f"{sym.lower()}{prefix}.csv"

        if idx not in isin.index:
            isin.at[idx, "SYMBOL"] = sym
        elif sym != isin.at[idx, "SYMBOL"]:
            old = isin.at[idx, "SYMBOL"]
            isin.at[idx, "SYMBOL"] = sym
            old_file = DAILY / f"{old.lower()}{prefix}.csv"
            sym_file = old_file.rename(DAILY / f"{sym.lower()}{prefix}.csv")

            print(old, sym, dt)

        txt = b""

        if dup is not None and idx in dup.index:
            O, H, L, C, V = dup.loc[idx, ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY"]]
        else:
            O, H, L, C, V = df.loc[idx, ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY"]]

        if dlv_df is not None:
            if sym in dlv_df.index:
                series, trdCnt, dq = dlv_df.loc[
                    sym, [" SERIES", " NO_OF_TRADES", " DELIV_QTY"]
                ]

                # BE and BZ series stocks are all delivery trades,
                # so we use the volume
                try:
                    dq = V if series in (" BE", " BZ") else int(dq)
                except ValueError:
                    dq = np.nan
            else:
                trdCnt = dq = np.nan

            avgTrdCnt = round(V / trdCnt, 2)
        else:
            trdCnt = dq = avgTrdCnt = ""

        if not sym_file.exists():
            sme_file = DAILY / f"{sym.lower()}_sme.csv"

            if prefix == "" and sme_file.exists():
                sme_file.rename(sym_file)
            else:
                txt += headerText

        txt += bytes(
            f"{pandas_dt},{O},{H},{L},{C},{V},{trdCnt},{avgTrdCnt},{dq}\n",
            encoding="utf-8",
        )

        with sym_file.open("ab") as f:
            f.write(txt)

print("isin", isin.shape)
isin.to_csv(DAILY / "isin.csv")
