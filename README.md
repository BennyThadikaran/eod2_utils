This is a collection of scripts used to compile EOD2 data from scratch.

I add this repo to serve as a backup. It is not meant for end users, but you're welcome to fork it.

If you just need the NSE eod data, [EOD2](https://github.com/BennyThadikaran/eod2) is what you're looking for.

Python >= 3.11

config.toml uses [toml format](https://toml.io/en/)

## Steps to compile EOD2

The entire process from scratch can take a few hours to complete.

Before starting make sure you have the latest bhavcopies, delivery and indices reports upto current date. Reports must be organized by year for each report type.

Make sure all corporate actions are up-to-date. (See #sync-corporate-actions)

1. Organize all reports - bhav, delivery, Indices. Include current year reports (as necessary)

2. Update the config.toml with the necessary file / folder paths. Leave the dates as is.

3. Run `collate_no_isin.py` and `collate_indices.py`

4. Run `collate_with_isin.py`

5. Run `collate_udiff_bhav.py`

6. Take a compressed backup (zip) of compiled folders for future use.
   - In the future, the compiled data can be reused to avoid recompiling entire data from scratch.
   - Reusing the compiled data, allows completing the entire process in an hour.

7. Add files from `indices` folder to `daily-with-udiff` folder.

8. Run `cleanup.py` to remove duplicates rows and outdated files.
   - If you wish to keep old or suspended stocks intact, set `cleanup.remove_outdated` to `false` in config.toml.

9. Run `/actions/make_adjustments.py` to apply adjustments to stocks.

10. Run `gaps_eod2.py` to remove data with gaps in trading days exceeding 365 days.

11. Run `diagnostic.py` to check for common errors in data.

12. Move compiled data to eod2
    - Copy all files from `daily-with-udiff` folder to `eod2/src/eod2_data/daily`
    - Copy isin.csv to `eod2/src/eod2_data`

13. Finally edit `eod2/src/eod2_data/meta.json`
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

14. If `data-version` changed in meta.json, the same must be reflected in `eod2/src/defs/Config.py` under `EXPECTED_DATA_VERSION`.

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

## TODO

- Add other scripts for EOD2 maintainence.
- Add a script to sync `daily-with-udiff` folder to the latest, without having to build the folder from scratch.
