import shutil
from datetime import date, timedelta
from pathlib import Path
import tomllib
import json
from typing import cast, Iterable, NamedTuple
from collections import defaultdict

import pandas as pd


class Row(NamedTuple):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    pe: float


dir = Path(__file__).parent

config_file = dir / "config.toml"


with config_file.open("rb") as f:
    config = tomllib.load(f)

report_folder = Path(config["general"]["indices_folder"]).expanduser()

output_folder = Path(config["general"]["output_folder"]).expanduser()
index_out_folder = output_folder / "indices"
meta_file = output_folder / "meta-collate.json"

if meta_file.exists():
    meta = json.loads(meta_file.read_bytes())
else:
    meta = {}

if "last_update_indices" not in meta:
    if index_out_folder.exists():
        shutil.rmtree(index_out_folder)

    index_out_folder.mkdir(parents=True)

    dt = config["collate"]["indices"]["start_date"]
else:
    dt = date.fromisoformat(meta["last_update_indices"])

end_date = date.today()

dct = {
    "s&p cnx nifty": "nifty 50",
    "s&p cnx 500": "nifty 500",
    "s&p cnx nifty dividend": "nifty50 dividend points",
    "s&p cnx nifty shariah": "nifty50 shariah",
    "s&p cnx 500 shariah": "nifty500 shariah",
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

buffers = defaultdict(list)

while dt < end_date:
    dt = dt + timedelta(1)

    print(dt.strftime("%b-%Y"), flush=True, end="\r" * 11)

    indices_file = report_folder / f"{dt.year}/ind_close_all_{dt:%d%m%Y}.csv"

    if not indices_file.exists():
        continue

    # start delivery sync
    pandas_dt = dt.strftime("%Y-%m-%d")

    df = pd.read_csv(indices_file)
    df = df.replace("-", "")

    df.loc[:, "Index Name"] = (
        df["Index Name"].str.lower().str.replace(r"[/:]", "-", regex=True)
    )

    df.loc[:, "Index Name"] = df["Index Name"].map(lambda x: dct.get(x, x))

    df = df[
        [
            "Index Name",
            "Open Index Value",
            "High Index Value",
            "Low Index Value",
            "Closing Index Value",
            "Volume",
            "P/E",
        ]
    ]

    df = df[~df.duplicated(subset="Index Name")]

    df.columns = ["symbol", "open", "high", "low", "close", "volume", "pe"]

    rows = cast(Iterable[Row], df.itertuples())

    for row in rows:
        text = bytes(
            f"{pandas_dt},{row.open},{row.high},{row.low},{row.close},{row.volume},{row.pe},,,,\n",
            encoding="utf-8",
        )

        buffers[row.symbol].append(text)

    meta["last_update_indices"] = pandas_dt

header_text = (
    b"Date,Open,High,Low,Close,Volume,P/E,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
)

indices_set = set()

for symbol, lines in buffers.items():
    indices_set.add(symbol.lower())
    file = index_out_folder / f"{symbol}.csv"

    file.write_bytes(header_text + b"".join(lines))


(output_folder / "index.json").write_text(json.dumps(list(indices_set), indent=2))
meta_file.write_text(json.dumps(meta, indent=2))
