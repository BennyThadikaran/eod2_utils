import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime

import tomllib

DIR = Path(__file__).parent
config_file = DIR.parent / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

db_file = Path(config["general"]["actions_db"]).expanduser()
json_folder = Path(config["general"]["actions_folder"]).expanduser()

con = sqlite3.connect(db_file)
con.row_factory = sqlite3.Row


def get_hash(symbol, subject, ex_date, rec_date) -> str:
    string = f"{symbol}-{subject}-{ex_date}-{rec_date}"
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


for file in json_folder.iterdir():
    data = json.loads(file.read_bytes())

    sym = file.name[:-5]

    cur = con.execute(
        "INSERT INTO Stocks (name) VALUES (:name)",
        dict(name=sym),
    )

    id = cur.lastrowid
    created_at = datetime.today().timestamp()

    for act in data:
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
                dict(id=id, hash=hash, sub=sub, ex_date=ex_date, rec_date=rec_date),
            )
        except Exception as e:
            print(sym, sub, repr(e))
            continue

con.commit()
con.close()
