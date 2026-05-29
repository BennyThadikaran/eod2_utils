from nse import NSE
from pathlib import Path
from datetime import datetime, timedelta
import time
import httpx
import json
import tomllib

dir = Path(__file__).parent
config_file = dir / "config.toml"

with config_file.open("rb") as f:
    config = tomllib.load(f)


output_folder = Path(config["general"]["output_folder"]).expanduser()
pr_bhav_folder = Path(config["download"]["pr_bhav"]["output_folder"]).expanduser()

meta_file = output_folder / "download_pr_bhav_meta.json"


class PR:
    def __init__(self) -> None:
        self.nse = NSE(download_folder=dir, server=True)
        self.max_retries = 5

        if meta_file.exists():
            meta = json.loads(meta_file.read_bytes())
            self.dt = datetime.fromisoformat(meta["last_updated"])
            meta_file.unlink()

            if not pr_bhav_folder.exists():
                raise RuntimeError(f"Mising output_folder: {pr_bhav_folder}")
        else:
            self.dt = datetime(2011, 6, 22)

            if pr_bhav_folder.exists() and any(pr_bhav_folder.iterdir()):
                raise RuntimeError(f"Folder is not empty: {pr_bhav_folder.name}.")
            else:
                pr_bhav_folder.mkdir(parents=True, exist_ok=True)

        print(self.dt)
        end_date = datetime.now()

        retry_count = 0
        error_occurred = False

        while True:
            try:
                while self.dt <= end_date:
                    self.nse.pr_bhavcopy(date=self.dt, folder=pr_bhav_folder)
                    self.dt += timedelta(1)
                    retry_count = 0
                    error_occurred = False
            except (RuntimeError, FileNotFoundError):
                self.dt += timedelta(1)
                retry_count = 0
                error_occurred = False
                continue

            except (httpx.RemoteProtocolError, ConnectionError):
                self.nse.exit()

                if retry_count > self.max_retries:
                    self.save_progress()
                    exit("Max retry count reached")

                print("Retrying in 10 secs")
                time.sleep(10)
                self.nse = NSE(download_folder=pr_bhav_folder, server=True)
                retry_count += 1
                error_occurred = True
                continue
            except Exception as e:
                error_occurred = True
                self.save_progress()
                raise e
            finally:
                print(self.dt.strftime("%d-%b-%Y"), flush=True, end="\r" * 11)

                if not error_occurred:
                    time.sleep(0.5)
            break

        self.nse.exit()

    def save_progress(self):
        meta_file.write_text(
            json.dumps(dict(last_updated=self.dt.isoformat()), indent=2)
        )


if __name__ == "__main__":
    PR()
