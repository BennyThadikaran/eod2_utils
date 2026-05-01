import shutil
from datetime import timedelta
from pathlib import Path
import tomllib
from symbol_tracker import SymbolTracker
from typing import cast, Iterable, NamedTuple
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

"""
Updated 8th July 2024
- Updated to include delivery data
- Udiff format not suported
"""


class Row(NamedTuple):
    Index: str
    SYMBOL: str
    SERIES: str
    OPEN: float
    HIGH: float
    LOW: float
    CLOSE: float
    TOTTRDQTY: int
    TOTTRDVAL: float
    TOTALTRADES: int


@dataclass
class BufferEntry:
    lines: list[bytes] = field(default_factory=list)
    sme: bool = False


DIR = Path(__file__).parent
config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()
basePath = Path(config["general"]["bhav_folder"]).expanduser()
DAILY = output_folder / "daily-with-isin"
DELIVERY = Path(config["general"]["delivery_folder"]).expanduser()

isin_symbol_map_file = output_folder / "isin_symbol_map.json"

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

print(f"Copying files from {DAILY_NO_ISIN} to {DAILY}")
shutil.copytree(DAILY_NO_ISIN, DAILY, dirs_exist_ok=False)
print("Copy operation complete")


dt = config["collate"]["with_isin"]["start_date"]

end_date = config["collate"]["with_isin"]["end_date"]

# EDIT THIS TO FIRST BHAVCOPY YOU HAVE
isin = pd.read_csv(basePath / "2011/cm22JUN2011bhav.csv", index_col="ISIN")


priority = dict(EQ=1, BE=2, BZ=3, SM=4, ST=5)


isin = isin[
    isin["SERIES"].isin(priority)
    & ~isin.SYMBOL.str.contains(r"-RE\d*$", na=False, regex=True)
]

print("isin", isin.shape)

tracker = SymbolTracker()


buffers = defaultdict(BufferEntry)


while dt < end_date:
    dt = dt + timedelta(1)

    dt_str = dt.strftime("%d%b%Y").upper()

    bhav_file = basePath / f"{dt.year}/cm{dt_str}bhav.csv"

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="ISIN")

    df = df[
        df.SERIES.isin(priority)
        & ~df.SYMBOL.str.contains(r"-RE\d*$", na=False, regex=True)
    ]

    df.loc[:, "rank"] = df.SERIES.map(priority)

    df.sort_values("rank", inplace=True)

    df = df[~df.index.duplicated(keep="first")]

    dlv_df = None

    dlv_file = DELIVERY / f"{dt.year}/sec_bhavdata_full_{dt:%d%m%Y}.csv"

    if dlv_file.exists():
        dlv_df = pd.read_csv(dlv_file, index_col="SYMBOL")

        # Remove trailing whitespace in column names and SERIES string
        dlv_df.columns = dlv_df.columns.str.strip()
        dlv_df.loc[:, "SERIES"] = dlv_df.SERIES.str.strip()

        # Keep only Equity and SME series
        dlv_df = dlv_df[dlv_df.SERIES.isin(priority)]

        # assign rank based on series priority and sort by rank,
        dlv_df.loc[:, "rank"] = dlv_df.SERIES.map(priority)

        # keep only the first value to remove duplicate rows.
        dlv_df = dlv_df.sort_values("rank")

        dlv_df = dlv_df[~dlv_df.index.duplicated(keep="first")]

    pandas_dt = dt.strftime("%Y-%m-%d")
    rows = cast(Iterable[Row], df.itertuples())

    for row in rows:
        sym = row.SYMBOL
        idx = row.Index

        is_sme = row.SERIES == "SM" or row.SERIES == "ST"

        if idx not in isin.index:
            isin.at[idx, "SYMBOL"] = sym
        elif sym != isin.at[idx, "SYMBOL"]:
            old = isin.at[idx, "SYMBOL"]
            isin.at[idx, "SYMBOL"] = sym

            if sym in buffers:
                raise ValueError(f"New symbol {sym} already in buffer.")

            if old in buffers:
                buffers[sym] = buffers.pop(old)

            print(old, sym, dt)

        tracker.update(sym, idx, dt)

        if dlv_df is not None:
            if sym in dlv_df.index:
                trdCnt = dlv_df.at[sym, "NO_OF_TRADES"]
                dq = dlv_df.at[sym, "DELIV_QTY"]

                # BE and BZ series stocks are all delivery trades,
                # so we use the volume
                try:
                    dq = row.TOTTRDQTY if row.SERIES in ("BE", "BZ") else int(dq)
                except ValueError:
                    dq = ""
            else:
                trdCnt = dq = ""

            avgTrdCnt = "" if trdCnt == "" else round(row.TOTTRDQTY / trdCnt, 2)
        else:
            trdCnt = dq = avgTrdCnt = ""

        txt = bytes(
            f"{pandas_dt},{row.OPEN},{row.HIGH},{row.LOW},{row.CLOSE},{row.TOTTRDQTY},{row.SERIES},{trdCnt},{avgTrdCnt},{dq}\n",
            encoding="utf-8",
        )

        buffers[sym].lines.append(txt)
        buffers[sym].sme = is_sme


print("isin", isin.shape)
isin.to_csv(DAILY / "isin.csv")

headerText = (
    b"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
)

for symbol, entry in buffers.items():
    filepath = DAILY / f"{symbol.lower()}.csv"
    sme_filepath = filepath.with_stem(f"{symbol.lower()}_sme")

    if filepath.exists() and sme_filepath.exists():
        raise ValueError(
            f"Both EQ and SME file coexist. {filepath.name} and {sme_filepath.name}"
        )

    if entry.sme:
        target = sme_filepath
    else:
        if sme_filepath.exists():
            sme_filepath.rename(filepath)
        target = filepath

    if target.exists():
        with target.open("ab") as f:
            f.write(b"".join(entry.lines))
    else:
        target.write_bytes(headerText + b"".join(entry.lines))


isin_symbol_map_file.write_text(tracker.to_json())
