import pandas as pd
import fsspec
import os
import re
import shutil
from collections import defaultdict


def save_data():
    storage_options = {
        "key": "access_key",
        "secret": "secret_key",
        "client_kwargs": {
            "endpoint_url": "http://lakefs-dev:8000/"
        }
    }

    fs = fsspec.filesystem("s3", **storage_options)

    repo = "dust-concentration"
    branch = "main"
    base_path = f"{repo}/{branch}/pm_data.parquet"

    try:
        all_files = fs.glob(f"{base_path}/**/*.parquet")
        if not all_files:
            print("No Data in LakeFS")
            return

        # --- year/month/day/hour ---
        file_map = defaultdict(set)
        pattern = re.compile(r"year=(\d+)/month=(\d+)/day=(\d+)/hour=(\d+)/")

        for file in all_files:
            match = pattern.search(file)
            if match:
                key = (match.group(1), match.group(2), match.group(3))  # year, month, day
                hour = int(match.group(4))
                file_map[key].add(hour)

        # --- just day that have 24 hours ---
        valid_files = [
            file for file in all_files
            if pattern.search(file) and
               len(file_map[(pattern.search(file).group(1),
                             pattern.search(file).group(2),
                             pattern.search(file).group(3))]) == 24
        ]

        if not valid_files:
            print("Can't find, Day that have 24 hours.")
            return

        # --- schema setting ---
        columns_used = [
            "timestamp", "stationID", "nameTH", "areaTH", "district",
            "lat", "long", "AQI.aqi", "PM25.value", "year", "month", "day", "hour"
        ]

        dfs = []

        for file in valid_files:
            file_path = f"s3a://{file}"
            df = pd.read_parquet(file_path, storage_options=storage_options)
            df = df[columns_used]

            int_columns = ["year", "month", "day", "hour"]
            df[int_columns] = df[int_columns].astype("int32")

            dfs.append(df)

        df_all = pd.concat(dfs, ignore_index=True)

        local_base_dir = "/home/jovyan/data/data.parquet"

        # --- delete old folder --- 
        if os.path.exists(local_base_dir):
            shutil.rmtree(local_base_dir)

        os.makedirs(local_base_dir, exist_ok=True)

        df_all.to_parquet(
            local_base_dir,
            partition_cols=["year", "month", "day", "hour"],
            index=False,
            engine="pyarrow"
        )

        print(f"💾 Saved partitioned parquet dataset at {local_base_dir}")
        print("✅ ALL done!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    save_data()