import shutil
from datetime import date, timedelta
from pathlib import Path
import tomllib

import numpy as np
import pandas as pd

"""
Updated 8th July 2024 for using udiff format
"""

DIR = Path(__file__).parent
config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()
basePath = Path(config["general"]["bhav_folder"]).expanduser()
DAILY = output_folder / "daily-with-udiff"
DELIVERY = Path(config["general"]["delivery_folder"]).expanduser()

if DAILY.exists():
    shutil.rmtree(DAILY)

DAILY_WITH_ISIN = output_folder / "daily-with-isin"

if not DAILY_WITH_ISIN.exists():
    raise RuntimeError(f"Missing {DAILY_WITH_ISIN.name} folder.")

if not any(DAILY_WITH_ISIN.iterdir()):
    raise RuntimeError(f"{DAILY_WITH_ISIN.name} folder is empty.")

shutil.copytree(DAILY_WITH_ISIN, DAILY, dirs_exist_ok=False)


headerText = (
    b"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
)

dt = config["collate"]["udiff"]["start_date"]

today = date.today()

isin = pd.read_csv(DAILY_WITH_ISIN / "isin.csv", index_col="ISIN")

print("isin", isin.shape)

while dt <= today:
    dt = dt + timedelta(1)

    dt_str = dt.strftime("%Y%m%d")

    bhav_file = basePath / f"{dt.year}/BhavCopy_NSE_CM_0_0_0_{dt_str}_F_0000.csv"

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="ISIN")

    df = df[df["SctySrs"].isin(["EQ", "BE", "BZ", "SM", "ST"])]

    dlv_df = None

    dlv_file = DELIVERY / f"{dt.year}/sec_bhavdata_full_{dt:%d%m%Y}.csv"

    if dlv_file.exists():
        dlv_df = pd.read_csv(dlv_file, index_col="SYMBOL")
        dlv_df = dlv_df[dlv_df[" SERIES"].isin([" EQ", " BE", " BZ", " SM", " ST"])]

    pandas_dt = dt.strftime("%Y-%m-%d")

    for idx in df.index:
        sym, series = df.loc[idx, ["TckrSymb", "SctySrs"]]

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
            new_file = DAILY / f"{sym.lower()}{prefix}.csv"
            sym_file = old_file.rename(new_file)

            print(old, sym, dt)

        txt = b""

        O, H, L, C, V = df.loc[
            idx, ["OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol"]
        ]

        if dlv_df is not None:
            if sym in dlv_df.index:
                trdCnt, dq = dlv_df.loc[sym, [" NO_OF_TRADES", " DELIV_QTY"]]

                # BE and BZ series stocks are all delivery trades,
                # so we use the volume
                try:
                    dq = V if series in ("BE", "BZ") else int(dq)
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
            f"{pandas_dt},{O},{H},{L},{C},{V},{series},{trdCnt},{avgTrdCnt},{dq}\n",
            encoding="utf-8",
        )

        with sym_file.open("ab") as f:
            f.write(txt)

print("isin", isin.shape)
isin.to_csv(DAILY / "isin.csv")
