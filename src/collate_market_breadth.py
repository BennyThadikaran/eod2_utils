"""
This script builds a daily market breadth dataset from historical NSE
bhavcopy and price data, then exports the consolidated metrics to a CSV
file (market_tracker.csv).

The generated dataset includes indicators such as:

Percentage of stocks trading above their 50-day moving average
Percentage of stocks trading above their 200-day moving average
Cumulative net new 52-week highs vs lows
Advance–decline line
McClellan Oscillator
Net advance ratio

The script processes a broad historical universe of stocks, including
delisted securities, to avoid survivorship bias and improve the accuracy
and reliability of long-term breadth indicators.
"""

import tomllib
import zipfile
from pathlib import Path
import pandas as pd
from datetime import date, timedelta
from symbol_tracker import SymbolTracker
from typing import Optional


def ema_seed(prices, period):
    """Calculate initial EMA seed (SMA of first period prices)"""
    lst = prices[:period]
    if len(lst) < period:
        raise ValueError("Not enough data for ema seed")
    return sum(lst) / period


def ema(price, period, prev_ema):
    """Calculate current EMA from previous EMA"""
    alpha = 2 / (period + 1)
    return alpha * price + (1 - alpha) * prev_ema


def load_symbol(sym) -> Optional[pd.DataFrame]:
    if sym in cache:
        df = cache[sym]
    else:
        file = DAILY / f"{sym.lower()}.csv"

        if not file.exists():
            print(f"{sym} not found")
            cache[sym] = None
            return None

        df = pd.read_csv(
            file,
            parse_dates=["Date"],
            index_col="Date",
            usecols=pd.Index(["Date", "High", "Low", "Close"]),
        )

        df.loc[:, "MA50"] = df.Close.rolling(50).mean().round(2)
        df.loc[:, "MA200"] = df.Close.rolling(200).mean().round(2)
        df.loc[:, "52WH"] = df.High.rolling(252).max().shift(1).round(2)
        df.loc[:, "52WL"] = df.Low.rolling(252).min().shift(1).round(2)
        df.loc[:, "pclose"] = df.Close.shift(1)

        cache[sym] = df
    return df


def extract_pr_zip(zip_file) -> Optional[pd.DataFrame]:
    with zipfile.ZipFile(zip_file) as zf:
        namelist = zf.namelist()
        file_to_extract = None

        for name in namelist:
            if name.lower().endswith(".csv") and "mcap" in name.lower():
                file_to_extract = name
                break

        if file_to_extract:
            file_info = zf.getinfo(file_to_extract)

            if file_info.file_size == 0:
                return None

            with zf.open(file_to_extract) as f:
                mcap = pd.read_csv(f, index_col="Symbol")

                mcap.columns = mcap.columns.str.strip()
                mcap.Category = mcap.Category.str.strip()

                mcap = mcap[
                    mcap.Series.isin(priority)
                    & mcap.Category.isin(("Listed", "Permitted"))
                    & ~mcap.index.str.contains(r"-RE\d*$", na=False)  # -RE or -RE1 etc
                ]

                mcap.loc[:, "rank"] = mcap.Series.map(priority)
                mcap = mcap.sort_values("rank")
                mcap = mcap[~mcap.index.duplicated(keep="first")]

            return mcap


DIR = Path(__file__).parent
config_path = DIR / "config.toml"

with config_path.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()

DAILY = output_folder / "daily-with-udiff"


pr_zip_folder = Path(config["download"]["pr_bhav"]["output_folder"])

priority = dict(EQ=1, BE=2, BZ=3)

start_date = config["collate"]["market_breadth"]["start_date"]
end_date = date.today()
cache = {}
ad_ratios = []
results = []

prev_ad_line = prev_net_new_high = 0

# McClellan Oscillator settings
slow_ema_len = 39
fast_ema_len = 19
prev_fast_ema = prev_slow_ema = None
osc = fast_ema = slow_ema = None

tracker = SymbolTracker(output_folder / "isin_symbol_map.json")

while start_date <= end_date:
    zip_file = pr_zip_folder / f"PR{start_date:%d%m%y}.zip"

    print(start_date.strftime("%d-%b-%Y"))

    if not zip_file.exists():
        start_date += timedelta(1)
        continue

    mcap = extract_pr_zip(zip_file)

    if mcap is None:
        start_date += timedelta(1)
        continue

    dt = pd.to_datetime(mcap["Trade Date"].iloc[-1], errors="raise")
    new_high = new_low = 0
    count_200 = count_50 = 0
    universe_50 = universe_200 = 0
    adv = dec = total = 0

    for sym in mcap.index:
        symbol = tracker.get_last_symbol(sym, by="symbol")

        if symbol is None:
            print(f"{sym} not in tracker")
            continue

        df = load_symbol(symbol)

        if df is None or dt not in df.index:
            continue

        sma_50, sma_200, w_high, w_low, high, low, close, prev_close = df.loc[
            dt, ["MA50", "MA200", "52WH", "52WL", "High", "Low", "Close", "pclose"]
        ]

        # Stocks above 50 MA
        if not pd.isna(sma_50):
            universe_50 += 1

            if close > sma_50:
                count_50 += 1

        # Stocks above 200 MA
        if not pd.isna(sma_200):
            universe_200 += 1

            if close > sma_200:
                count_200 += 1

        # New 52 week high
        if not pd.isna(w_high) and high > w_high:
            new_high += 1

        # New 52 week low
        if not pd.isna(w_low) and low < w_low:
            new_low += 1

        if pd.isna(prev_close):
            continue

        if close > prev_close:
            adv += 1

        if close < prev_close:
            dec += 1

        total += 1

    # Stocks above 50 and 200
    pct_50 = None if universe_50 == 0 else round(count_50 / universe_50 * 100, 2)
    pct_200 = None if universe_200 == 0 else round(count_200 / universe_200 * 100, 2)

    # New 52 week highs
    cumulative_net_new_highs = prev_net_new_high + (new_high - new_low)
    prev_net_new_high = cumulative_net_new_highs

    # advance decline line
    ad_line = prev_ad_line + ((adv - dec) / total if total else 0)
    prev_ad_line = ad_line

    # McClellan Ratio-Adjusted Oscillator
    net_adv_ratio = (adv - dec) / total * 100 if total else None

    if net_adv_ratio is not None:
        ad_ratios.append(net_adv_ratio)

    if prev_fast_ema is None:
        if len(ad_ratios) >= fast_ema_len:
            fast_ema = ema_seed(ad_ratios, fast_ema_len)
            prev_fast_ema = fast_ema

    else:
        if net_adv_ratio is not None:
            fast_ema = ema(net_adv_ratio, fast_ema_len, prev_fast_ema)
            prev_fast_ema = fast_ema

    if prev_slow_ema is None:
        if len(ad_ratios) >= slow_ema_len:
            slow_ema = ema_seed(ad_ratios, slow_ema_len)
            prev_slow_ema = slow_ema
    else:
        if net_adv_ratio is not None:
            slow_ema = ema(net_adv_ratio, slow_ema_len, prev_slow_ema)
            prev_slow_ema = slow_ema

    if fast_ema is not None and slow_ema is not None:
        osc = fast_ema - slow_ema

    results.append(
        dict(
            Date=dt,
            PCT_50=pct_50,
            PCT_200=pct_200,
            NET_NEW_HIGHS=cumulative_net_new_highs,
            AD_LINE=ad_line,
            MCCLELLAN_OSC=osc,
            NET_ADV_RATIO=net_adv_ratio,
            FAST_EMA=fast_ema,
            SLOW_EMA=slow_ema,
        )
    )

    start_date += timedelta(1)


df = pd.DataFrame(results)
df.sort_values("Date", inplace=True)
df.to_csv(output_folder / "market_tracker.csv", index=False)
