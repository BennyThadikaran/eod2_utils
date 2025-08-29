import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tomllib

import pandas as pd

DIR = Path(__file__).parent
config_file = DIR.parent / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

DAILY = Path(config["general"]["output_folder"]).expanduser() / "daily-with-udiff"

splitRegex = re.compile(r"(\d+\.?\d*)[\/\- a-z\.]+(\d+\.?\d*)")

bonusRegex = re.compile(r"(\d+) ?: ?(\d+)")

lastidx = {"idx": None}
adjs = {}


def getSplit(sym: str, string, dt):
    """Run a regex search for splits related corporate action and
    return the adjustment factor"""

    match = splitRegex.search(string)

    if match is None:
        print(f"#### WARNING {sym}: Not Matched. {string} {dt}")
        return match

    # print(sym, float(match.group(1)), float(match.group(2)))
    return float(match.group(1)) / float(match.group(2))


def getBonus(sym: str, string, dt):
    """Run a regex search for bonus related corporate action and
    return the adjustment factor"""

    match = bonusRegex.search(string)

    if match is None:
        print(f"#### WARNING {sym}: Not Matched. {string} {dt}")
        return match

    return 1 + int(match.group(1)) / int(match.group(2))


def makeAdjustment(df, sym: str, dt, adjustmentFactor):
    lastidx["idx"] = None
    start = df.index[0]
    end = df.index[-1]

    if start > dt > end:
        print(f"{sym} Out of bounds")
        return df

    if dt not in df.index:
        curDt = dt
        while curDt not in df.index:
            curDt = curDt + timedelta(1)

        dt = curDt

    idx = df.index.get_loc(dt)

    last = df.iloc[idx:]

    df = df.iloc[:idx].copy()

    for col in ("Open", "High", "Low", "Close"):
        # nearest 0.05 = round(nu / 0.05) * 0.05
        df[col] = ((df[col] / adjustmentFactor / 0.05).round() * 0.05).round(2)

    lastidx["idx"] = idx

    return pd.concat([df, last])


def getDf(file):
    return pd.read_csv(file, index_col="Date", parse_dates=["Date"])


con = sqlite3.connect(DIR / "db/main.db")
con.row_factory = sqlite3.Row

syms = con.execute("SELECT id, name from Stock").fetchall()

for sym in syms:
    file = DAILY / f"{sym['name'].lower()}.csv"

    if not file.exists():
        file = DAILY / f"{sym['name'].lower()}_sme.csv"

        if not file.exists():
            # print(f"{sym['name']} not found")
            continue

    df = None

    actions = con.execute(
        f"SELECT subject, exDate from Actions WHERE stock_id={sym['id']}"
    ).fetchall()

    for act in actions:
        subject = act["subject"].lower()
        dt = datetime.fromtimestamp(act["exDate"])
        bonus = split = None

        if "split" in subject or "splt" in subject:
            i = subject.index("spl")

            split = getSplit(sym["name"], subject[i:], dt)

            if split is None:
                print(f"Error: SPLIT - {dt:%d-%b-%Y} - {sym['name']:<15} - {subject}")
                continue

            if df is None:
                df = getDf(file)

            df = makeAdjustment(df, sym["name"], dt, split)

            # print(f"{sym['name']} - {subject} {dt}")

        if "bonus" in subject:
            if (
                "deb" in subject
                or "pref" in subject
                or "ncrps " in subject
                or "dvr" in subject
            ):
                continue

            bonus = getBonus(sym["name"], subject, dt)

            if bonus is None:
                print(f"Error: BONUS - {dt:%d-%b-%Y} - {sym['name']:<15} - {subject}")
                continue

            if df is None:
                df = getDf(file)

            df = makeAdjustment(df, sym["name"], dt, bonus)

            # print(f'{sym['name']} - {act["subject"]} {dt}')

        # applies to some corporate actions prior to 2011
        if "spl" in subject and split is None:
            if "div" in subject:
                continue

            i = subject.index("spl")
            split = getSplit(sym["name"], subject[i:], dt)

            if split is None:
                print(f"Error: SPLIT - {dt:%d-%b-%Y} - {sym['name']:<15} - {subject}")

            if df is None:
                df = getDf(file)

            df = makeAdjustment(df, sym["name"], dt, split)

        # applies to some corporate actions prior to 2011
        if "bon" in subject and bonus is None:
            if (
                "deb" in subject
                or "pref" in subject
                or "ncrps " in subject
                or "dvr" in subject
            ):
                continue

            bonus = getBonus(sym["name"], subject, dt)

            if bonus is None:
                print(f"Error: BONUS - {dt:%d-%b-%Y} - {sym['name']:<15} - {subject}")

            if df is None:
                df = getDf(file)

            df = makeAdjustment(df, sym["name"], dt, bonus)

        if (
            lastidx["idx"] is None
            or lastidx["idx"] == 0
            or df is None
            or (bonus is None or split is None)
        ):
            continue

        if sym["name"] not in adjs:
            adjs[sym["name"]] = []

        adjs[sym["name"]].append(
            {
                "idx": lastidx["idx"],
                "sub": subject,
                "dt": dt,
                "bonus": bonus,
                "split": split,
            }
        )

    if df is not None and sym["name"] in adjs:
        for dct in adjs[sym["name"]]:
            close = df.loc[df.index[dct["idx"]], "Close"]
            prev_close = df.loc[df.index[dct["idx"] - 1], "Close"]

            diff = close / prev_close

            if diff > 1.5 or diff < 0.67:
                print(
                    f"WARN: Adjustment failed {dct['dt']} {sym['name']} {close} {prev_close} {dct['sub']}, split {dct['split']} bonus {dct['bonus']}"
                )

    if df is not None:
        df.to_csv(file)

con.close()
