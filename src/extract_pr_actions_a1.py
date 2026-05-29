"""
Reads daily PR ZIP archives, extracts corporate action rows,
normalizes dates, removes duplicate series entries based on
priority, and applies hardcoded corrections.
"""

import tomllib
import pandas as pd
import hashlib
import zipfile
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import NamedTuple, cast, Iterable


def parse_dates(date_ser):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(date_ser, errors="raise", format=fmt)
        except Exception:
            continue


def get_hash(symbol, subject, ex_date, rec_date) -> str:
    string = f"{symbol}-{subject}-{ex_date}-{rec_date}"
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


class Row(NamedTuple):
    SYMBOL: str
    SERIES: str
    PURPOSE: str
    EX_DT: datetime
    RECORD_DT: datetime


DIR = Path(__file__).parent
config_path = DIR / "config.toml"

with config_path.open("rb") as f:
    config = tomllib.load(f)

dt = config["download"]["pr_bhav"]["start_date"]
end_date = date.today()

folder = Path(config["download"]["pr_bhav"]["output_folder"]).expanduser()
output_folder = Path(config["general"]["output_folder"]).expanduser()

priority = dict(EQ=1, BE=2, BZ=3, SM=4, ST=5)

lines = []

while dt < end_date:
    filename = folder / f"PR{dt:%d%m%y}.zip"

    print(dt.strftime("%d-%b-%Y"), end="\r", flush=True)

    if not filename.exists():
        dt += timedelta(1)
        continue

    with zipfile.ZipFile(filename) as zf:
        namelist = zf.namelist()
        file_to_extract = None

        for name in namelist:
            if "bc" in name.lower():
                file_to_extract = name
                break

        if file_to_extract is None:
            dt += timedelta(1)
            continue

        file_info = zf.getinfo(file_to_extract)

        if file_info.file_size == 0:
            dt += timedelta(1)
            continue

        with zf.open(file_to_extract) as f:
            df = pd.read_csv(
                f,
                usecols=pd.Index(("SYMBOL", "SERIES", "RECORD_DT", "EX_DT", "PURPOSE")),
            )

            df = df[df.SERIES.isin(priority)]

            df.loc[:, "rank"] = df.SERIES.map(priority)
            df = df.sort_values("rank")

            df = df.drop_duplicates(
                subset=["SYMBOL", "RECORD_DT", "EX_DT", "PURPOSE"], keep="first"
            )

            df.RECORD_DT = parse_dates(df["RECORD_DT"].str.strip())
            df.EX_DT = parse_dates(df["EX_DT"].str.strip())

            rows = cast(Iterable[Row], df.itertuples())

            for row in rows:
                if pd.isna(row.EX_DT):
                    continue

                if row.EX_DT.date() == dt:
                    record_dt = None if pd.isna(row.RECORD_DT) else row.RECORD_DT.date()

                    lines.append(
                        dict(
                            SYMBOL=row.SYMBOL,
                            PURPOSE=row.PURPOSE,
                            EX_DATE=row.EX_DT.date(),
                            REC_DATE=record_dt,
                            TYPE="",
                            DIVIDEND="",
                            ADJUSTMENT_FACTOR="",
                        )
                    )
        dt += timedelta(1)

act_df = pd.DataFrame(lines)
act_df.sort_values(by="EX_DATE", inplace=True)
act_df.EX_DATE = parse_dates(act_df.EX_DATE)
act_df.REC_DATE = parse_dates(act_df.REC_DATE)

act_df.loc[
    (act_df.SYMBOL == "KSCL") & (act_df.EX_DATE.dt.date == date(2014, 1, 27)), "PURPOSE"
] = "Face Value Split From Rs 10/- To Rs 2/-"

act_df.loc[
    (act_df.SYMBOL == "CONCOR") & (act_df.EX_DATE.dt.date == date(2018, 6, 26)),
    "PURPOSE",
] = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share"

act_df.loc[
    (act_df.SYMBOL == "HDFCPVTBAN") & (act_df.EX_DATE.dt.date == date(2024, 2, 2)),
    "PURPOSE",
] = "Face Value Split (Sub-Division) - From Rs 216.75/- Per Share To Rs 21.675/- Per Share"

act_df.loc[
    (act_df.SYMBOL == "HDFCNIFIT") & (act_df.EX_DATE.dt.date == date(2024, 2, 2)),
    "PURPOSE",
] = "Face Value Split (Sub-Division) - From Rs 299.92/- Per Share To Rs 29.992/- Per Share"

act_df.loc[
    (act_df.SYMBOL == "HDFCNIFIT") & (act_df.REC_DATE.dt.date == date(2022, 8, 30)),
    "EX_DATE",
] = pd.to_datetime("2022-08-30")

act_df.loc[
    (act_df.SYMBOL == "KRITIKA") & (act_df.REC_DATE.dt.date == date(2022, 8, 30)),
    "EX_DATE",
] = pd.to_datetime("2022-08-30")

act_df.to_csv(output_folder / "pr_zip_output.csv", index=False)
