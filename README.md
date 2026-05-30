This is a collection of scripts used to compile EOD2 data from scratch.

I add this repo to serve as a backup. It is not meant for end users, but you're welcome to fork it.

If you just need the NSE eod data, [EOD2](https://github.com/BennyThadikaran/eod2) is what you're looking for.

Python >= 3.11

config.toml uses [toml format](https://toml.io/en/)

This file defines the folder locations used by the application to read NSE market data and store processed outputs.

- **`bhav_folder`**
  Path to NSE **Bhav Copy** reports, organized into folders by year.

- **`delivery_folder`**
  Path to NSE **Delivery Reports**, organized into folders by year.

- **`indices_folder`**
  Path to NSE **Indices Reports**, organized into folders by year.

- **`output_folder`**
  Destination folder where processed data and generated files will be saved.

- **`actions_folder`**
  Folder containing **corporate actions data** in JSON format (as downloaded from the NSE website).

- **`actions_db`**
  Path to the SQLite database used to store and manage corporate actions data.

> All paths support `~` for the user’s home directory and should be updated if the folder structure changes.

## Steps to compile EOD2

The entire process from scratch can take a few hours to complete.

Make sure all corporate actions are up-to-date. (See [Sync Corporate actions](#sync-corporate-actions))

1. Update the config.toml with the necessary file / folder paths. Leave the dates as is.

2. Organize all NSE reports (Bhav Copy, Delivery, and Indices) into their respective folders as defined in `config.toml`. Each report type must be further organized into subfolders by year, including the current year where applicable.

3. Run `collate_no_isin.py` and `collate_indices.py`

4. Run `collate_with_isin.py`

5. Run `collate_udiff_bhav.py`.

6. collate_indices.py and collate_udiff_bhav.py will generate a `meta-collate.json` file in the output folder. **Preserve this for future use.**

7. Take a compressed backup (zip) of compiled folders and `meta-collate.json` for future use.
   - In the future, the compiled data can be reused to avoid re-compiling entire data from scratch.
   - `meta-collate.json` is critical for reusing the compiled data in future.
   - Reusing the compiled data, allows completing the entire process in minutes.

8. Add files from `indices` folder to `daily-with-udiff` folder.

9. Run `cleanup.py` to remove duplicates rows and outdated files.
   - If you wish to keep old or suspended stocks intact, set `cleanup.remove_outdated` to `false` in config.toml.

10. Run `/actions/make_adjustments.py` to apply adjustments to stocks.

11. Run `gaps_eod2.py` to remove data with gaps in trading days exceeding 365 days.

12. Run `diagnostic.py` to check for common errors in data.

13. Move compiled data to eod2
    - Copy all files from `daily-with-udiff` folder to `eod2/src/eod2_data/daily`
    - Copy isin.csv to `eod2/src/eod2_data`

14. Finally edit `eod2/src/eod2_data/meta.json`
    - Update the lastUpdate date so it matches the last date in the compiled data.
    - Delete the following keys and associated values from meta.json
      - special_sessions_last_update
      - special_sessions
      - equityActions
      - equityActionsExpiry
      - smeActions
      - smeActionsExpiry
      - mfActions
      - mfActionsExpiry
    - Update the data-version key as required.

15. If `data-version` changed in meta.json, the same must be reflected in `eod2/src/defs/Config.py` under `EXPECTED_DATA_VERSION`.

## Using the compressed zip file to sync data to current date

Assume no changes are required in the compiled data, you can reuse the compiled data to sync and save time.

1. Extract the `daily-with-udiff`, `indices` folder and `meta-collate.json` file from the zip file into output_folder, as defined in config.toml
2. Run `collate_indices.py`
3. Run `collate_udiff_bhav.py`
4. Follow all steps from Step 7 of Steps to compile EOD2.

## Sync Corporate actions

All corporate actions (Equity and ETFs) are stored in a sqlite database located at `src/actions/db/main.db`

There are only 2 tables in the database: Stock and Actions. Refer to `src/actions/db/create.sql` for table structure.

To sync all corporate actions upto current date, run `actions/init.py`. It can be run automated as a cronjob daily.

## Populating Actions database from scratch

This is an optional step, only required, if the actions database need to be recreated due to errors or missing actions.

For most cases, run `actions/init.py` to sync the actions database to latest date.

It is preferred to run this on a weekend during midnight hours.

Steps 1 to 8 in the compile process must to be completed to proceed.

1. Delete existing `db/main.db`. Run `sqlite3 main.db < create.sql` in `actions/db` folder to generate SQLITE database.

2. Run `download_actions.py` to download corporate actions as json files.

3. Run `actions/to_sqlite.py` to move JSON data into Sqlite database.

4. Update the `actions/meta.json` with the last updated date.

## Steps to compile dataset with delisted stocks (to avoid survivorship bias)

**Before you start,**

- Ensure the output_folder exists. config.toml - `general.output_folder`.
- Ensure the PR bhavcopy folder exists and contains all PR bhavcopies. config.toml - `download.pr_bhav.output_folder`.
- PR Bhavcopies upto 29th May 2026 are available in the releases section of this repo.
- You can also run `download_pr_bhav.py` to sync upto the latest date.

**Step 1:** Follow all steps from 1 - 8 of [Steps to compile EOD2](#steps-to-compile-eod2). **Dont run cleanup.py**.

**Step 2:** Run `process_pr_zip_actions.py`.

    - It will output a `final.csv` in the output folder.
    - This contains corporate actions for all stocks (including delisted) from 2011 onwards

**Step 3:** Run `apply_adjustments_from_csv.py`.

    - It will apply the adjustments from final.csv to the CSV files in `daily-with-udiff`

The resulting dataset can now be used to run `collate_market_breadth.py` to collate indicators from scratch.

**Notes:**

The corporate actions file in PR bhav zip required extensive cleanup and normalizing to make it parsable.

In rare cases, the purpose string was terminated midway. This required manually hardcoding the purpose text (acquired from NSE website) to correct the problem.

The scripts `extract_pr_actions_a1.py`, `normalize_action_text_a2.py`, and `build_final_actions_csv_a3.py` correspond to individual stages of the workflow implemented by `process_pr_zip_actions.py`. They are intended mainly for debugging, testing, and development; most users should use `process_pr_zip_actions.py`.

## SymbolTracker

See [SymbolTracker usage](symbol-tracker-usage.md)

## Releases

[2025-Master](https://github.com/BennyThadikaran/eod2_utils/releases/tag/2025-master) - Contains all equity, delivery, and indices bhavcopy from 1995 onwards.

[PR-Bhav-Master](https://github.com/BennyThadikaran/eod2_utils/releases/tag/pr-bhav-master) - Contains all PR Bhav copies from 2011 to 2025.

Going forward, all reports for a calendar year will be bundled into a single GitHub release published at the beginning of the following year.
