from collections import defaultdict
import shutil
import json
from datetime import date, timedelta
from pathlib import Path
import tomllib
from symbol_tracker import SymbolTracker
from typing import cast, Iterable, NamedTuple
from dataclasses import dataclass, field

import pandas as pd

"""
Updated 8th July 2024 for using udiff format
"""


class Row(NamedTuple):
    Index: str
    TckrSymb: str
    SctySrs: str
    OpnPric: float
    HghPric: float
    LwPric: float
    ClsPric: float
    TtlTradgVol: int


@dataclass
class BufferEntry:
    lines: list[bytes] = field(default_factory=list)
    sme: bool = False


dir = Path(__file__).parent
config_file = dir / "config.toml"


with config_file.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()
report_folder = Path(config["general"]["bhav_folder"]).expanduser()
daily_folder = output_folder / "daily-with-udiff"
delivery_folder = Path(config["general"]["delivery_folder"]).expanduser()
isin_symbol_map_file = output_folder / "isin_symbol_map.json"

isin_file = daily_folder / "isin.csv"

meta_file = output_folder / "meta-collate.json"

if meta_file.exists():
    meta = json.loads(meta_file.read_bytes())
else:
    meta = {}

if "last_update_udiff" not in meta:
    DAILY_WITH_ISIN = output_folder / "daily-with-isin"

    if not DAILY_WITH_ISIN.exists():
        raise RuntimeError(f"Missing {DAILY_WITH_ISIN.name} folder.")

    if not any(DAILY_WITH_ISIN.iterdir()):
        raise RuntimeError(f"{DAILY_WITH_ISIN.name} folder is empty.")

    if daily_folder.exists():
        shutil.rmtree(daily_folder)

    print(f"Copying files from {DAILY_WITH_ISIN} to {daily_folder}")
    shutil.copytree(DAILY_WITH_ISIN, daily_folder, dirs_exist_ok=False)
    print("Copy operation complete")

    isin = pd.read_csv(isin_file, index_col="ISIN")

    dt = config["collate"]["udiff"]["start_date"]
else:
    isin = pd.read_csv(isin_file, index_col="ISIN")
    dt = date.fromisoformat(meta["last_update_udiff"])


print("isin", isin.shape)


today = date.today()

t2t_segment = ("BE", "BZ")

priority = {"EQ": 1, "BE": 2, "BZ": 3, "SM": 4, "ST": 5}

tracker = SymbolTracker(isin_symbol_map_file)

buffers = defaultdict(BufferEntry)

while dt < today:
    dt = dt + timedelta(1)

    dt_str = dt.strftime("%Y%m%d")

    bhav_file = report_folder / f"{dt.year}/BhavCopy_NSE_CM_0_0_0_{dt_str}_F_0000.csv"

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="ISIN")

    df = df[
        df.SctySrs.isin(priority)
        & ~df.TckrSymb.str.contains(r"-RE\d*$", na=False, regex=True)
    ]

    df.loc[:, "rank"] = df.SctySrs.map(priority)

    df.sort_values("rank", inplace=True)

    df = df.loc[~df.index.duplicated(keep="first")]

    dlv_df = None

    dlv_file = delivery_folder / f"{dt.year}/sec_bhavdata_full_{dt:%d%m%Y}.csv"

    if dlv_file.exists():
        dlv_df = pd.read_csv(dlv_file, index_col="SYMBOL")
        dlv_df.columns = dlv_df.columns.str.strip()
        dlv_df.loc[:, "SERIES"] = dlv_df.SERIES.str.strip()

        # Keep only Equity and SME series
        dlv_df = dlv_df[dlv_df["SERIES"].isin(priority)]

        # assign rank based on series priority and sort by rank,
        dlv_df.loc[:, "rank"] = dlv_df.SERIES.map(priority)

        # keep only the first value to remove duplicate rows.
        dlv_df.sort_values("rank", inplace=True)

        dlv_df = dlv_df.loc[~dlv_df.index.duplicated(keep="first")]

    pandas_dt = dt.strftime("%Y-%m-%d")

    rows = cast(Iterable[Row], df.itertuples())

    for row in rows:
        sym = row.TckrSymb
        idx = row.Index

        is_sme = row.SctySrs == "SM" or row.SctySrs == "ST"

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
                    dq = row.TtlTradgVol if row.SctySrs in t2t_segment else int(dq)
                except ValueError:
                    dq = ""

            else:
                trdCnt = dq = ""

            avgTrdCnt = "" if trdCnt == "" else round(row.TtlTradgVol / trdCnt, 2)
        else:
            trdCnt = dq = avgTrdCnt = ""

        txt = bytes(
            f"{pandas_dt},{row.OpnPric},{row.HghPric},{row.LwPric},{row.ClsPric},{row.TtlTradgVol},{row.SctySrs},{trdCnt},{avgTrdCnt},{dq}\n",
            encoding="utf-8",
        )

        buffers[sym].lines.append(txt)
        buffers[sym].sme = is_sme

        meta["last_update_udiff"] = pandas_dt


print("isin", isin.shape)
isin.to_csv(daily_folder / "isin.csv")

headerText = (
    b"Date,Open,High,Low,Close,Volume,Series,TOTAL_TRADES,QTY_PER_TRADE,DLV_QTY\n"
)

for symbol, entry in buffers.items():
    filepath = daily_folder / f"{symbol.lower()}.csv"
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
isin.to_csv(isin_file)

meta_file.write_text(json.dumps(meta, indent=2))
