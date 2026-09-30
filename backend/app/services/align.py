"""Levenshtein alignment between a target sequence and a heard sequence
(words of a passage, or phoneme units / letters inside a word).

Backtrace prefers match/substitution, then deletion, then insertion, so the
result is deterministic.
"""

import math
import operator
from dataclasses import dataclass
from typing import Callable, Sequence

MATCH, SUB, DEL, INS = "match", "sub", "del", "ins"


@dataclass(frozen=True)
class Op:
    kind: str        # match | sub | del (in target, not heard) | ins (heard, not in target)
    a: int | None    # index into the target sequence
    b: int | None    # index into the heard sequence


def align(
    a: Sequence,
    b: Sequence,
    *,
    eq: Callable = operator.eq,
    sub_cost: Callable | None = None,
) -> list[Op]:
    """`sub_cost(x, y)` (default 1.0) lets similar items align as substitutions
    in preference to a deletion + insertion. Deletion and insertion cost 1."""

    def step(x, y) -> float:
        if eq(x, y):
            return 0.0
        return sub_cost(x, y) if sub_cost else 1.0

    n, m = len(a), len(b)
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = float(i)
    for j in range(1, m + 1):
        cost[0][j] = float(j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(
                cost[i - 1][j - 1] + step(a[i - 1], b[j - 1]),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )

    ops: list[Op] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s = step(a[i - 1], b[j - 1])
            if math.isclose(cost[i][j], cost[i - 1][j - 1] + s):
                ops.append(Op(MATCH if eq(a[i - 1], b[j - 1]) else SUB, i - 1, j - 1))
                i, j = i - 1, j - 1
                continue
        if i > 0 and math.isclose(cost[i][j], cost[i - 1][j] + 1):
            ops.append(Op(DEL, i - 1, None))
            i -= 1
            continue
        ops.append(Op(INS, None, j - 1))
        j -= 1
    ops.reverse()
    return ops
