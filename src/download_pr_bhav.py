from nse import NSE
from pathlib import Path
from datetime import datetime, timedelta
import time
import httpx
import json
import tomllib

dir = Path(__file__).parent
config_file = dir / "config.toml"
meta_file = dir / "pr_meta.json"

with config_file.open("rb") as f:
    config = tomllib.load(f)

output_folder = Path(config["download"]["pr_bhav"]["output_folder"]).expanduser()


class PR:
    def __init__(self) -> None:
        self.nse = NSE(download_folder=dir, server=True)
        self.max_retries = 5

        if meta_file.exists():
            meta = json.loads(meta_file.read_bytes())
            self.dt = datetime.fromisoformat(meta["last_updated"])
            meta_file.unlink()

            if not output_folder.exists():
                raise RuntimeError(f"Mising output_folder: {output_folder}")
        else:
            self.dt = datetime(2011, 6, 22)

            if output_folder.exists() and any(output_folder.iterdir()):
                raise RuntimeError(f"Folder is not empty: {output_folder.name}.")
            else:
                output_folder.mkdir(parents=True, exist_ok=True)

        print(self.dt)
        end_date = datetime.now()

        retry_count = 0
        error_occurred = False

        while True:
            try:
                while self.dt <= end_date:
                    self.nse.pr_bhavcopy(date=self.dt, folder=output_folder)
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
                self.nse = NSE(download_folder=output_folder, server=True)
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
        meta_file.unlink(missing_ok=True)

    def save_progress(self):
        meta_file.write_text(
            json.dumps(dict(last_updated=self.dt.isoformat()), indent=2)
        )


if __name__ == "__main__":
    PR()
