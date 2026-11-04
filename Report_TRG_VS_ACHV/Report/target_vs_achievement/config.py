"""
Project settings.  Edit this file for the things you will change most often.
Anything here can also be overridden from the command line (see README.md).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
DB_PATH = BASE_DIR / "data" / "data.db"      # SQLite file with `sales` and `zemp`
OUTPUT_DIR = BASE_DIR / "output"             # one <EmployeeID>.html is written per employee

# --------------------------------------------------------------------------
# Who gets a report
# --------------------------------------------------------------------------
# Hierarchy levels that receive a report (see LEVELS below for what the numbers mean).
# The old script used 2..7; the AGM sample you showed used level 9, so 2..9 is the default.
REPORT_LEVELS = (2, 4, 6, 7, 8, 9)

# Only employees whose `sales.division` is in this list get a report.
# The old script used (1, 2, 4).  Use None to include every division.
REPORT_DIVISIONS = (1, 2, 4 , 11)

# Skip managers who have nobody below them in `zemp` (the report would only
# show their own numbers).  Set to False to generate those reports anyway.
SKIP_IF_NO_TEAM = True

# --------------------------------------------------------------------------
# Hierarchy definition
# --------------------------------------------------------------------------
# sales.hieararchy number -> (label shown in the report, column(s) in `zemp`
# that hold the person at that level).
# Several zemp columns can feed one level (e.g. RSM and ASM are reported together).
LEVELS = {
    1: ("MIO/SMIO", ("MIO/ SMIO",)),
    2: ("AM/SAM",   ("AM/ SAM", "SAM")),
    4: ("RSM/ASM",  ("RSM", "ASM")),
    6: ("DSM",      ("DSM",)),
    7: ("SM",       ("SM",)),
    8: ("SSM",      ("SSM",)),
    9: ("AGM",      ("AGM",)),
}

# zemp uses this ID for an empty position; it is ignored everywhere.
VACANT_ID = "EM00000000"

# --------------------------------------------------------------------------
# Report content
# --------------------------------------------------------------------------
COMPANY_NAME = "Aristopharma ltd."
UNIT_NOTE = "(Figures in Lac tk)"
TITLE_TEMPLATE = "Target vs Achievement upto {month}, {year} (highest achv% wise)"

# Show the employee's own monthly row as the first table (like the AGM table
# in the previous report).
SHOW_OWN_TABLE = True

# Sort team tables by this field, highest first.  One of: "ach", "target", "sales", "name"
SORT_TEAM_BY = "ach"

# "Last month with data".  None = detect automatically from the database
# (the latest month in which anybody has sales).  Or force it: e.g. 10 for October.
REPORT_UPTO_MONTH = None

# Colour bands for the Ach % badges in tables and the quarter cards.
ACH_GOOD = 90      # >= GOOD  -> green
ACH_OK = 75        # >= OK    -> amber, below -> red

# Chart: the dashed reference line.
TARGET_LINE = 100
