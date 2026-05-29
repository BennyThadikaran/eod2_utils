"""
Section 1 — Collate actions
--------------------------------
Reads daily PR ZIP archives, extracts corporate action rows,
normalizes dates, removes duplicate series entries based on
priority, and applies hardcoded corrections.

Section 2 — Clean output
--------------------------------
Standardizes PURPOSE text using regex cleanup and replacement
rules, removes unwanted meeting/consolidation rows, and splits
combined corporate actions into separate rows.

Section 3 — Convert to final CSV
--------------------------------
Identifies corporate action types (DIVIDEND, BONUS, SPLIT,
CONSOLIDATION), computes dividend values and adjustment factors,
formats dates, and writes the final cleaned dataset to final.csv.
"""

import tomllib
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import NamedTuple, cast, Iterable
import hashlib
import zipfile
import re

import pandas as pd


# =============================================================================
# COMMON HELPERS
# =============================================================================


def parse_dates(date_ser):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(date_ser, errors="raise", format=fmt)
        except Exception:
            continue


def get_hash(symbol, subject, ex_date, rec_date) -> str:
    string = f"{symbol}-{subject}-{ex_date}-{rec_date}"
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


# =============================================================================
# SECTION 1 — COLLATE ACTIONS
# =============================================================================


class CollateRow(NamedTuple):
    SYMBOL: str
    SERIES: str
    PURPOSE: str
    EX_DT: datetime
    RECORD_DT: datetime


def collate_actions():
    lines = []

    dt = pr_bhav_config["start_date"]

    end_date = date.today()

    folder = Path(pr_bhav_config["output_folder"]).expanduser()

    priority = dict(EQ=1, BE=2, BZ=3, SM=4, ST=5)

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
                    usecols=pd.Index(
                        ("SYMBOL", "SERIES", "RECORD_DT", "EX_DT", "PURPOSE")
                    ),
                )

                df = df[df.SERIES.isin(priority)]

                df.loc[:, "rank"] = df.SERIES.map(priority)
                df = df.sort_values("rank")

                df = df.drop_duplicates(
                    subset=["SYMBOL", "RECORD_DT", "EX_DT", "PURPOSE"],
                    keep="first",
                )

                df.RECORD_DT = parse_dates(df["RECORD_DT"].str.strip())
                df.EX_DT = parse_dates(df["EX_DT"].str.strip())

                rows = cast(Iterable[CollateRow], df.itertuples())

                for row in rows:
                    if pd.isna(row.EX_DT):
                        continue

                    if row.EX_DT.date() == dt:
                        record_dt = (
                            None if pd.isna(row.RECORD_DT) else row.RECORD_DT.date()
                        )

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

    # Manual corrections
    act_df.loc[
        (act_df.SYMBOL == "KSCL") & (act_df.EX_DATE.dt.date == date(2014, 1, 27)),
        "PURPOSE",
    ] = "Face Value Split From Rs 10/- To Rs 2/-"

    act_df.loc[
        (act_df.SYMBOL == "CONCOR") & (act_df.EX_DATE.dt.date == date(2018, 6, 26)),
        "PURPOSE",
    ] = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share"

    act_df.loc[
        (act_df.SYMBOL == "HDFCPVTBAN") & (act_df.EX_DATE.dt.date == date(2024, 2, 2)),
        "PURPOSE",
    ] = (
        "Face Value Split (Sub-Division) - "
        "From Rs 216.75/- Per Share To Rs 21.675/- Per Share"
    )

    act_df.loc[
        (act_df.SYMBOL == "HDFCNIFIT") & (act_df.EX_DATE.dt.date == date(2024, 2, 2)),
        "PURPOSE",
    ] = (
        "Face Value Split (Sub-Division) - "
        "From Rs 299.92/- Per Share To Rs 29.992/- Per Share"
    )

    act_df.loc[
        (act_df.SYMBOL == "HDFCNIFIT") & (act_df.REC_DATE.dt.date == date(2022, 8, 30)),
        "EX_DATE",
    ] = pd.to_datetime("2022-08-30")

    act_df.loc[
        (act_df.SYMBOL == "KRITIKA") & (act_df.REC_DATE.dt.date == date(2022, 8, 30)),
        "EX_DATE",
    ] = pd.to_datetime("2022-08-30")

    return act_df


# =============================================================================
# SECTION 2 — CLEAN OUTPUT
# =============================================================================

replace_map = {
    "RHTS": "RIGHTS",
    "GENREAL": "GENERAL",
    "FGENERAL": "GENERAL",
    "RGHTS": "RIGHTS",
    "RGTS": "RIGHTS",
    "RIGTS": "RIGHTS",
    "ARRNGMT": "ARRANGEMENT",
    "ARGMT": "ARRANGEMENT",
    "AGMT": "ARRANGEMENT",
    "ARRANGMNT": "ARRANGEMENT",
    "ARRNGMNT": "ARRANGEMENT",
    "ARNGMNT": "ARRANGEMENT",
    "ARNGMT": "ARRANGEMENT",
    "SCH": "SCHEME",
    "SCHM": "SCHEME",
    "CNSLDATN": "CONSOLIDATION",
    "CONSOLIDATIN": "CONSOLIDATION",
    "CONSO": "CONSOLIDATION",
    "AMLGMTN": "AMALGAMATION",
    "AMALGATION": "AMALGAMATION",
    "AMALAGMATION": "AMALGAMATION",
    "GENRAL": "GENERAL",
    "ANUUAL": "ANNUAL",
    "ANNAL": "ANNUAL",
    "ANNUL": "ANNUAL",
    "ANNAUL": "ANNUAL",
    "ANUAL": "ANNUAL",
    "MEEING": "MEETING",
    "MEETNG": "MEETING",
    "MEETINGQ": "MEETING",
    "MEETIG": "MEETING",
    "MEETIN": "MEETING",
    "MEEETING": "MEETING",
    "METING": "MEETING",
    "EETING": "MEETING",
    "SHAR": "SHARE",
    "SHR": "SHARE",
    "SHRE": "SHARE",
    "SAHR": "SHAREHOLDER",
    "SHAE": "SHARE",
    "SH": "SHARE",
    "SHA": "SHARE",
    "SPLDV": " DIVIDEND ",
    "SPLDIV": " DIVIDEND ",
    "DIVRS": " DIVIDEND ",
    "DIVRE": " DIVIDEND ",
    "SPDV": " DIVIDEND ",
    "AGMDIV": " DIVIDEND ",
    "DIVD": " DIVIDEND ",
    "SPDIV": " DIVIDEND ",
    "DIVDEND": " DIVIDEND ",
    "DIVINDEND": " DIVIDEND ",
    "FINDIV": " DIVIDEND ",
    "INTDV": " DIVIDEND ",
    "SPLRS": " DIVIDEND ",
    "DVSPDV": " DIVIDEND ",
    "IDV": " DIVIDEND ",
    "DIV-FINRS": " DIVIDEND ",
    "SPLDIVRS": " DIVIDEND ",
    "SPDIVRS": " DIVIDEND ",
    "DIVSPDV": " DIVIDEND ",
    "FDIV": " DIVIDEND ",
    "DIVIDNED": " DIVIDEND ",
    "SPLINTDIV": " DIVIDEND ",
    "DIVIVEND": " DIVIDEND ",
    "DIVIDND": " DIVIDEND ",
    "SPECIALDIV": " DIVIDEND ",
    "INTERIMD": " DIVIDEND ",
    "INTDIV": " DIVIDEND ",
    "DIV": " DIVIDEND ",
    "DIVI": " DIVIDEND ",
    "DIVID": " DIVIDEND ",
    "DIVIDEN": " DIVIDEN ",
    "RED": "CONSOLIDATION",
}

keys = []

for k in replace_map.keys():
    if k in (
        "SH",
        "SHA",
        "SHR",
        "SHRE",
        "SHAR",
        "SCH",
        "SCHM",
        "CONSO",
        "MEETIN",
        "EETING",
        "DIV",
        "DIVI",
        "DIVID",
        "DIVIDEN",
        "FGENERAL",
        "RED",
    ):
        keys.append(rf"\b{k}\b")
    else:
        keys.append(k)

pattern_regex = re.compile(rf"({'|'.join(keys)})")


def has_combination(s):
    keywords = ["BONUS", "SPLIT", "DIV"]
    count = sum(1 for k in keywords if k in s)
    return count >= 2


def clean_output(df):
    df = df.copy()

    df.loc[:, "PURPOSE"] = (
        df.PURPOSE.str.upper()
        .str.replace("DIVISION", " ")
        .str.replace("DE-MERGER", " DEMERGER ")
        .str.replace("/-", " ")
        .str.replace("FVSPLT", " FV SPLIT ")
        .str.replace("FVSPLIT", " FV SPLIT ")
        .str.replace("FVSPL", " FV SPLIT ")
        .str.replace("FVS ", " FV SPLIT ")
        .str.replace("SPLT", " SPLIT ")
        .str.replace("BUY BACK", " BUYBACK ")
        .str.replace("BUY-BACK", " BUYBACK ")
        .str.replace(
            "REDTN|REDUCTN|REDN|REDCTN",
            " CONSOLIDATION ",
            regex=True,
        )
        .str.replace("BON(?!US)", " BONUS ", regex=True)
        .str.replace(
            pattern_regex,
            lambda x: replace_map[x.group()],
            regex=True,
        )
        .str.replace("NCRPS", " NCRPS ")
        .str.replace(r"\b\d+\s*(ST|ND|RD|TH)\b", " ", regex=True)
        .str.replace(r"(RE|RS)\.?(?=\d+)", " RS ", regex=True)
        .str.replace(r"FIN(?:-|\s)?(?:RS|RE)", " ", regex=True)
        .str.replace(r"\bFV SPL\b", " FV SPLIT ", regex=True)
        .str.replace(
            r"(?:DV|DI|FIN|SPL|INT)(?:-|\s)?(?:RS|RE)",
            " DIVIDEND RS ",
            regex=True,
        )
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    row_to_drop = []
    row_to_add = []

    for row in df.copy().itertuples():
        if row.PURPOSE in (
            "EGM",
            "EOGM",
            "EXTRA GENERAL MEETING",
            "EXTR-ORDNRY GNRL MEETING",
            "CAPITAL REDUCTION",
            "CAP. CONSOLIDATION /CONSOLIDATION",
            "CAP CONSOLIDATION /CONSOLIDATION",
            "CAP CONSOLIDATION/ CONSOLIDATION",
            "CAP CONSOLIDATION",
            "CONSOLIDATION/CAP CONSOLIDATION",
        ):
            row_to_drop.append(row.Index)

        if has_combination(row.PURPOSE):
            key = "/" if "/" in row.PURPOSE else "+"

            if key not in row.PURPOSE:
                print("NOT FOUND", row.PURPOSE)
                continue

            for text in row.PURPOSE.split(key):
                if text.strip() in ("AGM", "BONUS"):
                    continue

                row_to_drop.append(row.Index)

                row_to_add.append(
                    dict(
                        SYMBOL=row.SYMBOL,
                        EX_DATE=row.EX_DATE,
                        REC_DATE=row.REC_DATE,
                        PURPOSE=text.strip(),
                        TYPE="",
                        DIVIDEND="",
                        ADJUSTMENT_FACTOR="",
                    )
                )

    df.drop(row_to_drop, inplace=True)

    new_df = pd.DataFrame(row_to_add)

    df = pd.concat([df, new_df], ignore_index=True)

    return df


# =============================================================================
# SECTION 3 — CONVERT TO FINAL CSV
# =============================================================================


class FinalRow(NamedTuple):
    Index: int
    SYMBOL: str
    EX_DATE: str
    REC_DATE: str
    PURPOSE: str
    TYPE: str
    DIVIDEND: str
    ADJUSTMENT_FACTOR: str


splitRegex = re.compile(r"(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)")

bonusRegex = re.compile(r"(\d+) ?: ?(\d+)")

dividend_regex = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d|st\b|nd\b|rd\b|th\b)")


def getDividend(text: str):
    amounts = tuple(float(x) for x in dividend_regex.findall(text))

    if not amounts:
        return None

    return sum(amounts)


def getSplit(text):
    match = splitRegex.search(text)

    if match is None:
        return match

    return float(match.group(1)) / float(match.group(2))


def getBonus(text):
    match = bonusRegex.search(text)

    if match is None:
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


def convert_to_final(df):
    df = df.copy()

    df = df[~df.PURPOSE.isin(["ANNUAL GENERAL MEETING", "INTERIM DIVIDEND"])]

    df = df[
        ~df.PURPOSE.str.contains(
            "RIGHTS|BUYBACK|VOTING",
            na=False,
            regex=True,
        )
    ]

    df = df[df.EX_DATE.notna() & df.REC_DATE.notna()]

    rows = cast(Iterable[FinalRow], df.itertuples())

    rows_to_remove = []

    for row in rows:
        if pd.isna(row.EX_DATE):
            continue

        dividend = _type = bonus = split = None

        try:
            subject = row.PURPOSE.lower()
        except AttributeError:
            print(row.PURPOSE)
            rows_to_remove.append(row.Index)
            continue

        err_msg = None

        if "split" in subject or "consolidation" in subject:
            if "consolidation" in subject:
                i = subject.index("consolidation")
                _type = "CONSOLIDATION"
            else:
                i = subject.index("spl")
                _type = "SPLIT"

            split = getSplit(subject[i:])

            if split is None:
                err_msg = (
                    f"#### WARNING SPLIT "
                    f"{row.EX_DATE} {row.SYMBOL}: "
                    f"Not Matched. {subject}"
                )

                _type = None

        if "bonus" in subject:
            if not (
                "deb" in subject
                or "pref" in subject
                or "ncrps" in subject
                or "dvr" in subject
            ):
                bonus = getBonus(subject)
                _type = "BONUS"

                if err_msg:
                    print(err_msg)

                if bonus is None:
                    _type = None

        if split is None and bonus is None and "div" in subject:
            _type = "DIVIDEND"

            dividend = getDividend(subject)

            if err_msg:
                err_msg = None

            if dividend is None:
                _type = None
                rows_to_remove.append(row.Index)
                continue

        if err_msg:
            print(err_msg)

        if split is not None:
            adj_factor = str(split)
        elif bonus is not None:
            adj_factor = str(bonus)
        else:
            adj_factor = ""

        df.loc[row.Index, "ADJUSTMENT_FACTOR"] = adj_factor
        df.loc[row.Index, "DIVIDEND"] = "" if dividend is None else str(dividend)
        df.loc[row.Index, "TYPE"] = _type or ""

    df.drop(rows_to_remove, inplace=True)

    df.loc[:, "EX_DATE"] = pd.to_datetime(
        df.EX_DATE,
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    df.sort_values("EX_DATE", inplace=True)

    return df


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    config_path = Path(__file__).parent / "config.toml"

    with config_path.open("rb") as f:
        config = tomllib.load(f)

    output_folder = Path(config["general"]["output_folder"]).expanduser()
    pr_bhav_config = config["download"]["pr_bhav"]

    print("Step 1 — Collate actions")
    df = collate_actions()
    print("Step 2 — Clean output")
    df = clean_output(df)
    print("Step 3 — Convert to final CSV")
    df = convert_to_final(df)

    df.to_csv(output_folder / "final.csv", index=False)

    print("\nDone. Saved final.csv")
