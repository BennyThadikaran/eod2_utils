import shutil
from datetime import date, timedelta
from pathlib import Path
import tomllib

import pandas as pd

DIR = Path(__file__).parent

config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

FOLDER = Path(config["general"]["indices_folder"]).expanduser()

OUT_FOLDER = Path(f"{config['general']['output_folder']}/indices").expanduser()

if OUT_FOLDER.exists():
    shutil.rmtree(OUT_FOLDER)

OUT_FOLDER.mkdir(parents=True)

dt = config["collate"]["indices"]["start_date"]

end_date = date.today()

old_dct = {
    "s&p cnx nifty": "nifty 50",
    "s&p cnx 500": "nifty 500",
    "s&p cnx nifty dividend": "nifty50 dividend points",
    "s&p cnx nifty shariah": "nifty50 shariah",
    "s&p cnx 500 shariah": "nifty500 shariah",
}

dct = {
    "cnx 100": "nifty 100",
    "cnx 100 equal weight": "nifty50 equal weight",
    "cnx 200": "nifty 200",
    "cnx 500": "nifty 500",
    "cnx 500 shariah": "nifty500 shariah",
    "cnx alpha index": "nifty alpha 50",
    "cnx auto": "nifty auto",
    "cnx bank": "nifty bank",
    "cnx commodities": "nifty commodities",
    "cnx consumption": "nifty india consumption",
    "cnx dividend opportunities": "nifty dividend opportunities 50",
    "cnx energy": "nifty energy",
    "cnx finance": "nifty financial services",
    "cnx fmcg": "nifty fmcg",
    "cnx high beta": "nifty high beta 50",
    "cnx infrastructure": "nifty infrastructure",
    "cnx it": "nifty it",
    "cnx low volatility": "nifty low volatility 50",
    "cnx media": "nifty media",
    "cnx metal": "nifty metal",
    "cnx midcap": "nifty midcap 50",
    "cnx mnc": "nifty mnc",
    "cnx nifty": "nifty 50",
    "cnx nifty dividend": "nifty50 dividend points",
    "cnx nifty junior": "nifty next 50",
    "cnx nifty shariah": "nifty50 shariah",
    "cnx pharma": "nifty pharma",
    "cnx pse": "nifty pse",
    "cnx psu bank": "nifty psu bank",
    "cnx realty": "nifty realty",
    "cnx service sector": "nifty services sector",
    "cnx shariah25": "nifty shariah 25",
    "cnx smallcap": "nifty smallcap 50",
    "cpse": "nifty cpse",
    "nse quality 30": "nifty quality 30",
}

while dt < end_date:
    dt = dt + timedelta(1)

    print(dt.strftime("%b-%Y"), flush=True, end="\r" * 11)

    indices_file = FOLDER / f"{dt.year}/ind_close_all_{dt:%d%m%Y}.csv"

    if not indices_file.exists():
        continue

    # start delivery sync
    pandas_dt = dt.strftime("%Y-%m-%d")

    df = pd.read_csv(indices_file, index_col="Index Name")
    df = df.replace("-", "")

    for sym in df.index:
        sym_lower_case = sym.lower()

        if sym_lower_case in old_dct:
            fname = f"{old_dct[sym_lower_case]}.csv"
        elif sym_lower_case in dct:
            fname = f"{dct[sym_lower_case]}.csv"
        else:
            fname = f"{sym_lower_case}.csv"

        if "/" in fname or ":" in fname:
            fname = fname.replace("/", "-").replace(":", "-")

        file = OUT_FOLDER / fname

        text = b""

        ser = df.loc[
            sym,
            [
                "Open Index Value",
                "High Index Value",
                "Low Index Value",
                "Closing Index Value",
                "Volume",
                "P/E",
            ],
        ]

        if len(ser.shape) > 1:
            ser = ser.iloc[0]

        O, H, L, C, V, pe = ser

        if V == "-":
            V = ""

        if pe == "-":
            pe = ""

        if not file.exists():
            text += b"Date,Open,High,Low,Close,Volume,P/E,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"

        text += bytes(f"{pandas_dt},{O},{H},{L},{C},{V},{pe},,,,\n", encoding="utf-8")

        with file.open("ab") as f:
            f.write(text)
