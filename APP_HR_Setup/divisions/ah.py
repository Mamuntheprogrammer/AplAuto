"""Division logic: AH (09).

EDIT THIS FILE to change AH-specific rules. operations.py combines all
division files automatically — nothing else needs edits.
"""

CODE = "09"
NAME = "AH"

# [ZDEPOTHEAD] source columns expected in the sheet.
DEPOTHEAD_COLUMNS = ["Depot Code", "Division", "Hierarchy", "Depot Head"]

# [ZEMPLOYEE] total input columns + required last char of col3 (hierarchy 1/2).
EMPLOYEE_COLS = 31
EMPLOYEE_SUFFIX = {"L"}

# [ZMIO_TARGET] variants detected from the col7 header text (empty = none).
MIOTARGET_VARIANTS: dict[str, tuple[str, ...]] = {}

# [ZSD_MIO_PROD_TRG] source columns (positional mapping, 7 expected).
ZSD_COLUMNS = ["Plant Code", "Plant Name", "Material Code", "Material Description",
               "Market Code", "Target Quantity", "Division"]
