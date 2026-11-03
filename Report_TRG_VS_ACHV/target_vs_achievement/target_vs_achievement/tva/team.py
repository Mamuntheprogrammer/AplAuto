"""Works out which people appear in an employee's report, and in which table."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models import Person
from .repository import TeamIndex

_SORTS = {
    "ach":    lambda p: -(p.total_ach if p.total_ach is not None else -1),
    "target": lambda p: -p.total_target,
    "sales":  lambda p: -p.total_sales,
    "name":   lambda p: p.name.lower(),
}


@dataclass
class TeamTable:
    level: int
    label: str
    people: List[Person]
    own: bool = False          # True for the employee's own one-row table


def build_tables(employee: Person,
                 people: Dict[str, Person],
                 index: TeamIndex,
                 levels: Dict[int, Tuple[str, Tuple[str, ...]]],
                 sort_by: str = "ach",
                 include_own: bool = True) -> List[TeamTable]:
    """
    Tables for one report, highest level first:
        own row  ->  every level below the employee that has people in it.
    """
    sort_key = _SORTS.get(sort_by, _SORTS["ach"])
    tables: List[TeamTable] = []

    if include_own:
        tables.append(TeamTable(employee.level, levels.get(employee.level, (str(employee.level),))[0],
                                [employee], own=True))

    under_ids = index.under(employee.emp_id, employee.level)
    for lvl in sorted(levels, reverse=True):
        if lvl >= employee.level:
            continue
        members = [people[i] for i in under_ids
                   if i in people and people[i].level == lvl and i != employee.emp_id]
        if members:
            members.sort(key=sort_key)
            tables.append(TeamTable(lvl, levels[lvl][0], members))
    return tables


def team_size(tables: List[TeamTable]) -> int:
    return sum(len(t.people) for t in tables if not t.own)
