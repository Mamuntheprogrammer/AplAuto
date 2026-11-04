import pandas as pd
import sqlite3
from pathlib import Path

# Excel files and corresponding SQLite table names
excel_files = {
    "sales.xlsx": "sales",
    "zemp.xlsx": "zemp",
}

# Output SQLite database
sqlite_file = "data.db"

with sqlite3.connect(sqlite_file) as conn:
    for excel_file, table_name in excel_files.items():

        # Read the first sheet of the Excel file
        df = pd.read_excel(excel_file)

        # Convert Excel data to SQLite table
        df.to_sql(
            table_name,
            conn,
            if_exists="replace",
            index=False
        )

        print(f"Imported '{excel_file}' into table '{table_name}'")

print(f"\nConversion completed: {sqlite_file}")