import shutil
from datetime import timedelta
from pathlib import Path
import tomllib
from typing import cast, Iterable, NamedTuple
from collections import defaultdict

import pandas as pd


class Row(NamedTuple):
    Index: str
    SERIES: str
    OPEN: float
    HIGH: float
    LOW: float
    CLOSE: float
    TOTTRDQTY: int
    TOTTRDVAL: float


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

headerText = (
    b"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
)

dt = config["collate"]["no_isin"]["start_date"]
end_date = config["collate"]["no_isin"]["end_date"]

priority = dict(EQ=1, BE=2, BZ=3)

buffers = defaultdict(list)

while dt < end_date:
    dt = dt + timedelta(1)

    dt_str = dt.strftime("%d%b%Y").upper()

    print(dt.strftime("%d-%b-%Y"), flush=True, end="\r")

    bhav_file = BASE / f"{dt.year}/cm{dt_str}bhav.csv"

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="SYMBOL")

    df = df[df["SERIES"].isin(priority)]

    df.loc[:, "rank"] = df["SERIES"].map(priority)

    df = df.sort_values("rank")

    df = df[~df.index.duplicated(keep="first")]

    pandas_dt = dt.strftime("%Y-%m-%d")

    rows = cast(Iterable[Row], df.itertuples())

    for row in rows:
        sym_file = DAILY / f"{row.Index.lower()}.csv"

        buffers[row.Index].append(
            bytes(
                f"{pandas_dt},{row.OPEN},{row.HIGH},{row.LOW},{row.CLOSE},{row.TOTTRDQTY},{row.SERIES},,,\n",
                encoding="utf-8",
            )
        )

for symbol, lines in buffers.items():
    sym_file = DAILY / f"{symbol.lower()}.csv"

    sym_file.write_bytes(headerText + b"".join(lines))

print("complete")
