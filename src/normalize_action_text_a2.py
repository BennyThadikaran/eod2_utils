"""
Standardizes PURPOSE text using regex cleanup and replacement
rules, removes unwanted meeting/consolidation rows, and splits
combined corporate actions into separate rows.
"""

import tomllib
from pathlib import Path
import pandas as pd
import re

# from itertools import chain
# from collections import Counter

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
    "DIVIVEND": " DIVIDEND ",
    "DIVIDND": " DIVIDEND ",
    "SPECIALDIV": " DIVIDEND ",
    "DIVIDND": " DIVIDEND ",
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

DIR = Path(__file__).parent
config_path = DIR / "config.toml"

with config_path.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["general"]["output_folder"]).expanduser()

df = pd.read_csv(output_folder / "pr_zip_output.csv")


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
    .str.replace("REDTN|REDUCTN|REDN|REDCTN", " CONSOLIDATION ", regex=True)
    .str.replace("BON(?!US)", " BONUS ", regex=True)
    .str.replace(pattern_regex, lambda x: replace_map[x.group()], regex=True)
    .str.replace("NCRPS", " NCRPS ")
    .str.replace(r"\b\d+\s*(ST|ND|RD|TH)\b", " ", regex=True)
    .str.replace(r"(RE|RS)\.?(?=\d+)", " RS ", regex=True)
    .str.replace(r"FIN(?:-|\s)?(?:RS|RE)", " ", regex=True)
    .str.replace(r"\bFV SPL\b", " FV SPLIT ", regex=True)
    .str.replace(
        r"(?:DV|DI|FIN|SPL|INT)(?:-|\s)?(?:RS|RE)", " DIVIDEND RS ", regex=True
    )
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)


def has_combination(s):
    keywords = ["BONUS", "SPLIT", "DIV"]
    count = sum(1 for k in keywords if k in s)
    return count >= 2


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

df.to_csv(output_folder / "cleaned_actions.csv", index=False)


# tokens = (
#     df["cleaned"]
#     .str.replace("/-", " ")
#     .str.replace("-", " ")
#     .str.replace(r"\d+(\.\d+)?", " ", regex=True)
#     .str.replace(r"[^\w\s]", " ", regex=True)
#     .str.replace(r"\s+", " ", regex=True)
#     .str.split()
# )
#
# token_counts = Counter(list(chain.from_iterable(tokens)))
#
# freq_df = pd.DataFrame(
#     token_counts.items(), columns=pd.Index(["token", "count"])
# ).sort_values("count", ascending=False)
#
# freq_df.to_csv("freq.csv", index=False)
