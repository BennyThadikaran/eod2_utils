import httpx
from time import sleep
import json
from nse import NSE
from pathlib import Path
import tomllib


def save_actions(data, file: Path):
    file.write_text(json.dumps(data, indent=2))


DIR = Path(__file__).parent

config_file = DIR / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)

etf_file = DIR / "etf.json"
output_folder = Path(config["general"]["actions_folder"])
meta_file = DIR / "actions_meta.json"
DAILY = Path(config["general"]["output_folder"]) / "daily-with-udiff"


class Actions:
    """
    Downloads corporate actions from NSE.

    Use actions/to_sqlite.py to move the data into SQLITE database.

    DO NOT ABUSE THIS SCRIPT. Use actions/init.py to update the database daily.

    Preferably run on weekend, around midnight hours to reduce network timeouts and rate limits.

    Since a lot of symbols must be updated, there is additional sleep added to avoid overloading
    the server with requests. Please leave the timeouts as is.
    """

    def __init__(self) -> None:
        # Keep track of last downloaded actions in file, in case of network failure
        if meta_file.exists():
            meta = json.loads(meta_file.read_bytes())
            self.last_updated = meta["last_updated"]
            meta_file.unlink()
        else:
            self.last_updated = None

        self.last = None

        if not output_folder.exists():
            output_folder.mkdir(parents=True)

        self.nse = NSE(download_folder="", server=True)

        if etf_file.exists():
            self.etf_lst = json.loads(etf_file.read_bytes())
        else:
            self.etf_lst = self.nse.listEtf()

            etf_file.write_text(json.dumps(self.etf_lst, indent=2))

        # Mechanism to continue download in case of network errors or timeouts
        while True:
            try:
                self.run()
            except (httpx.RemoteProtocolError, ConnectionError) as e:
                print(
                    f"Connection {'reset' if isinstance(e, ConnectionError) else 'error'}"
                )

                self.nse.exit()
                self.last_updated = self.last
                sleep(10)
                self.nse = NSE(download_folder="", server=True)
                continue
            except Exception as e:
                meta_file.write_text(json.dumps(dict(last_updated=self.last), indent=2))
                raise e
            break

        self.nse.exit()
        etf_file.unlink(missing_ok=True)
        meta_file.unlink(missing_ok=True)

    def run(self):
        for file in DAILY.iterdir():
            if "_sme" in file.name:
                sym = file.name[:-8].upper()
                series = "SM"
            else:
                sym = file.name[:-4].upper()
                series = "EQ"

            if self.last_updated:
                if self.last_updated != sym:
                    continue

                self.last_updated = None

            file = output_folder / f"{sym}.json"

            if file.exists():
                continue

            if sym in self.etf_lst:
                actions = self.nse.actions(
                    segment="mf",
                    symbol=sym,
                    from_date=from_date,
                    to_date=to_date,
                )

                sleep(0.5)

                if actions:
                    save_actions(actions, file)
                self.last = sym
            else:
                sme_actions = self.nse.actions(
                    segment="sme",
                    symbol=sym,
                    from_date=from_date,
                    to_date=to_date,
                )

                if isinstance(sme_actions, dict):
                    sme_actions = sme_actions["data"]

                sleep(0.5)

                if series == "EQ":
                    eq_actions = self.nse.actions(
                        segment="equities",
                        symbol=sym,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    sleep(0.5)

                    if isinstance(eq_actions, dict):
                        eq_actions = eq_actions["data"]

                    sme_actions.extend(eq_actions)

                if sme_actions:
                    save_actions(sme_actions, file)
                self.last = sym


if __name__ == "__main__":
    Actions()
