"""Division logic files — one module per division.

To change a division's rules, edit its file (e.g. divisions/pharma.py).
operations.py combines everything below; to add a new division, add a file
and list it in MODULES.
"""

from divisions import ag, ah, dnr, onco, ophtha, pharma

MODULES = (pharma, ag, onco, ophtha, dnr, ah)
BY_CODE = {m.CODE: m for m in MODULES}
