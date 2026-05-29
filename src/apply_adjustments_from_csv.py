import tomllib
import pandas as pd
from pathlib import Path
from symbol_tracker import SymbolTracker


def makeAdjustment(df, dt, adjustmentFactor):
    start = df.index[0]
    end = df.index[-1]

    if dt < start or dt > end:
        return df, None

    if dt in df.index:
        idx = df.index.get_loc(dt)
        last = df.iloc[idx:]
        df = df.iloc[:idx].copy()
    else:
        last = df.loc[dt:]

        df = df.loc[:dt].copy()
        idx = df.index.get_loc(df.index[-1])

    for col in ("Open", "High", "Low", "Close"):
        # nearest 0.05 = round(nu / 0.05) * 0.05
        df.loc[:, col] = ((df[col] / adjustmentFactor / 0.05).round() * 0.05).round(2)

    return pd.concat([df, last]), idx


DIR = Path(__file__).parent

config_path = DIR / "config.toml"

with config_path.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()
actions_file = output_folder / "final.csv"
isin_symbol_map_file = output_folder / "isin_symbol_map.json"

daily_folder = output_folder / "daily-with-udiff"

actions_df = pd.read_csv(actions_file, parse_dates=["EX_DATE"])

tracker = SymbolTracker(isin_symbol_map_file)

actions_df.SYMBOL = actions_df.SYMBOL.map(
    lambda x: tracker.get_last_symbol(x, by="symbol")
)

adj_types = ("BONUS", "SPLIT", "CONSOLIDATION")

for symbol in actions_df["SYMBOL"].unique():
    if pd.isna(symbol):
        continue

    file = daily_folder / f"{symbol.lower()}.csv"

    if not file.exists():
        continue

    df = pd.read_csv(file, index_col="Date", parse_dates=["Date"])

    filtered = actions_df.loc[
        (actions_df.SYMBOL == symbol) & actions_df.TYPE.isin(adj_types),
        ["EX_DATE", "TYPE", "PURPOSE", "ADJUSTMENT_FACTOR"],
    ]

    lst = []
    if len(filtered):
        for row in filtered.itertuples():
            df, pos = makeAdjustment(df, row.EX_DATE, row.ADJUSTMENT_FACTOR)

            if pos is None:
                continue

            lst.append(pos)

        for pos in lst:
            cur_idx = df.index[pos]
            prev_idx = df.index[pos - 1]
            close = df.at[cur_idx, "Close"]
            prev_close = df.at[prev_idx, "Close"]

            diff = close / prev_close

            if diff > 1.5 or diff < 0.67:
                print(
                    f"WARN: Adjustment failed {cur_idx} {symbol} {close} {prev_close}"
                )

    df.to_csv(file)
