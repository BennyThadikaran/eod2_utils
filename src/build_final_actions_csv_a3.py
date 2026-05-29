"""
Identifies corporate action types (DIVIDEND, BONUS, SPLIT,
CONSOLIDATION), computes dividend values and adjustment factors,
formats dates, and writes the final cleaned dataset to final.csv.
"""

import tomllib
from pathlib import Path
import re
import pandas as pd
from typing import cast, Iterable, NamedTuple


class Row(NamedTuple):
    Index: int
    SYMBOL: str
    EX_DATE: str
    REC_DATE: str
    PURPOSE: str
    TYPE: str
    DIVIDEND: str
    ADJUSTMENT_FACTOR: str


def getDividend(text: str):
    amounts = tuple(float(x) for x in dividend_regex.findall(text))

    if not amounts:
        return None

    return sum(amounts)


def getSplit(text):
    """Run a regex search for splits related corporate action and
    return the adjustment factor"""

    match = splitRegex.search(text)

    if match is None:
        return match

    return float(match.group(1)) / float(match.group(2))


def getBonus(text):
    """Run a regex search for bonus related corporate action and
    return the adjustment factor"""

    match = bonusRegex.search(text)

    if match is None:
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


DIR = Path(__file__).parent

config_path = DIR / "config.toml"

with config_path.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()

splitRegex = re.compile(r"(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)")

bonusRegex = re.compile(r"(\d+) ?: ?(\d+)")

dividend_regex = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d|st\b|nd\b|rd\b|th\b)")

df = pd.read_csv(output_folder / "cleaned_actions.csv", dtype=str)

df = df[~df.PURPOSE.isin(["ANNUAL GENERAL MEETING", "INTERIM DIVIDEND"])]
df = df[~df.PURPOSE.str.contains("RIGHTS|BUYBACK|VOTING", na=False, regex=True)]

df = df[df.EX_DATE.notna() & df.REC_DATE.notna()]

rows = cast(Iterable[Row], df.itertuples())

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

    # if (
    #     "meeting" in subject
    #     or "closure" in subject
    #     or "rights" in subject
    #     or "rhts" in subject
    # ):
    #     continue

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
                f"#### WARNING SPLIT {row.EX_DATE} {row.SYMBOL}: Not Matched. {subject}"
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
                # err_msg = f"#### WARNING BONUS {row.EX_DATE} {row.SYMBOL}: Not Matched. {subject}"
                _type = None

    if split is None and bonus is None and "div" in subject:
        _type = "DIVIDEND"
        dividend = getDividend(subject)

        if err_msg:
            err_msg = None

        if dividend is None:
            # err_msg = (
            #     f"#### WARNING DIV {row.EX_DATE} {row.SYMBOL}: Not Matched. {subject}"
            # )

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
df.loc[:, "EX_DATE"] = pd.to_datetime(df.EX_DATE, errors="raise").dt.strftime(
    "%Y-%m-%d"
)

df.sort_values("EX_DATE", inplace=True)
df.to_csv(output_folder / "final.csv", index=False)
