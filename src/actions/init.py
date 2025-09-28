import json
import logging
import hashlib
import sqlite3
from datetime import datetime, timedelta
from itertools import chain
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
import tzlocal
from nse import NSE


def get_hash(symbol, subject, ex_date, rec_date) -> str:
    string = f"{symbol}-{subject}-{ex_date}-{rec_date}"
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


def get_index_by_value(series, value):
    result = series.loc[series == value]
    if not result.empty:
        return result.index[0]


def configure_logger(name: str) -> logging.Logger:
    """Return a logger instance by name

    Creates a file handler to log messages with level WARNING and above

    Creates a stream handler to log messages with level INFO and above

    Parameters:
    name (str): Pass __name__ for module level logger
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(logging.INFO)

    stdout_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    file_handler = logging.FileHandler(DIR / "error.log")
    file_handler.setLevel(logging.WARNING)

    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)

    return logger


class Dates:
    "A class for date related functions in EOD2"

    def __init__(self, lastUpdate: str):
        today = datetime.now(tz_IN)

        self.today = datetime.combine(today, datetime.min.time())

        dt = datetime.fromisoformat(lastUpdate).astimezone(tz_IN)

        self.dt = self.lastUpdate = dt

        self.pandasDt = self.dt.strftime("%Y-%m-%d")

    def nextDate(self):
        """Set the next trading date and return True.
        If its a future date, return False"""

        curTime = datetime.now(tz_IN)
        self.dt = self.dt + timedelta(1)

        if self.dt > curTime:
            logger.info("All Up To Date")
            return False

        if self.dt.day == curTime.day and curTime.hour < 18:
            # Display the users local time
            local_time = curTime.replace(hour=19, minute=0).astimezone(tz_local)

            t_str = local_time.strftime("%I:%M%p")  # 07:00PM

            logger.info(
                f"All Up To Date. Check again after {t_str} for today's EOD data"
            )
            return False

        self.pandasDt = self.dt.strftime("%Y-%m-%d")
        return True


DIR = Path(__file__).parent
META_FILE = DIR / "meta.json"
ISIN_FILE = DIR / "isin.csv"

tz_local = tzlocal.get_localzone()
tz_IN = ZoneInfo("Asia/Kolkata")

isin = pd.read_csv(ISIN_FILE, index_col="ISIN")

con = sqlite3.connect(DIR / "db/main.db")
con.row_factory = sqlite3.Row

logger = configure_logger("init.py")

meta = json.loads(META_FILE.read_bytes())
dates = Dates(meta["last_update"])

new_symbols = []
update_symbols = []

while True:
    if not dates.nextDate():
        break

    yr = dates.dt.year
    dt_str = dates.dt.strftime("%Y%m%d")

    bhav_file = Path(
        f"~/Documents/python/eod2/src/nseBhav/{yr}/BhavCopy_NSE_CM_0_0_0_{dt_str}_F_0000.csv"
    ).expanduser()

    if not bhav_file.exists():
        continue

    df = pd.read_csv(bhav_file, index_col="ISIN")

    df = df[df["SctySrs"].isin(["EQ", "BE", "BZ", "SM", "ST"])]

    for idx in df.index:
        sym = df.at[idx, "TckrSymb"]

        if "-RE" in sym:
            continue

        if idx not in isin.index:
            isin.loc[idx, "SYMBOL"] = sym
            idx = get_index_by_value(isin.SYMBOL, sym)

            logger.info(f"New symbol: {sym}")

            if not idx:
                # add new symbol
                new_symbols.append({"name": sym})
        elif sym != isin.at[idx, "SYMBOL"]:
            logger.info(f"Symbol update: {isin.at[idx, 'SYMBOL']} -> {sym}")

            isin.loc[idx, "SYMBOL"] = sym
            # update existing symbol
            update_symbols.append({"name": sym})

    if new_symbols:
        logger.info(f"{len(new_symbols)} symbols added to Db.")

        con.executemany(
            "INSERT INTO Stocks (name) VALUES (:name)",
            new_symbols,
        )

        new_symbols.clear()

    if update_symbols:
        logger.info(f"{len(update_symbols)} symbol names updated.")

        con.executemany("UPDATE Stocks SET name=:name WHERE name=:name", update_symbols)

        update_symbols.clear()

    isin.to_csv(ISIN_FILE)
    con.commit()

    try:
        with NSE(DIR, server=True) as nse:
            eq_actions = nse.actions(
                segment="equities", from_date=dates.dt, to_date=dates.dt
            )

            sme_actions = nse.actions(
                segment="sme", from_date=dates.dt, to_date=dates.dt
            )

            etf_actions = nse.actions(
                segment="mf", from_date=dates.dt, to_date=dates.dt
            )
    except (httpx.NetworkError, TimeoutError, ConnectionError) as e:
        exit(repr(e))

    for act in chain(eq_actions, sme_actions, etf_actions):
        sym = act["symbol"]
        series = act["series"]

        if series not in ("EQ", "BE", "BZ", "SM", "ST"):
            continue

        res = con.execute(f"SELECT id from Stocks WHERE name='{sym}'").fetchone()

        if res is None:
            cur = con.execute("INSERT INTO Stocks (name) VALUES (:sym)", dict(sym=sym))
            res = dict(id=cur.lastrowid)

        sub = act["subject"].strip()

        if act["exDate"] == "-":
            ex_date = None
        else:
            ex_date = datetime.strptime(act["exDate"], "%d-%b-%Y").timestamp()

        if act["recDate"] == "-":
            rec_date = None
        else:
            rec_date = datetime.strptime(act["recDate"], "%d-%b-%Y").timestamp()

        hash = get_hash(sym, sub, ex_date, rec_date)

        try:
            cur = con.execute(
                f"INSERT INTO Actions (stock_id, hash, subject, exDate, recDate) VALUES (:id, :hash, :sub, :ex_date, :rec_date)",
                dict(
                    id=res["id"], hash=hash, sub=sub, ex_date=ex_date, rec_date=rec_date
                ),
            )
        except sqlite3.IntegrityError as e:
            continue

    meta["last_update"] = dates.dt.isoformat()
    META_FILE.write_text(json.dumps(meta))
    con.commit()
    logger.info(f"{dates.dt:%d %b %Y} sync complete")

con.close()
