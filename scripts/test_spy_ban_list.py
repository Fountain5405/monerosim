"""Tests for scripts/spy_ban_list.py: which spy /24s a partial-coverage list names."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spy_ban_list import listed  # noqa: E402

DENSE = {"10.0.1.0/24": 50, "10.0.2.0/24": 30}
TAIL = {f"10.1.{i}.0/24": 1 + i % 3 for i in range(1, 21)}


def test_full_coverage_lists_every_subnet_in_address_order():
    counts = {**TAIL, **DENSE}
    out = listed(counts)
    assert out == sorted(counts, key=lambda s: tuple(int(x) for x in s.split("/")[0].split(".")))


def test_partial_coverage_keeps_the_densest_first():
    counts = {**TAIL, **DENSE}
    out = listed(counts, 0.1)          # 22 subnets -> 2 listed
    assert set(out) == set(DENSE)


def test_coverage_rounds_to_a_count_and_lists_at_least_one():
    counts = {**TAIL, **DENSE}
    assert len(listed(counts, 0.5)) == 11
    assert len(listed(counts, 0.001)) == 1


def test_ties_are_seeded():
    equal = {f"10.2.{i}.0/24": 2 for i in range(1, 11)}
    a, b = listed(equal, 0.5, seed=1), listed(equal, 0.5, seed=1)
    assert a == b and len(a) == 5
    assert any(listed(equal, 0.5, seed=s) != a for s in range(2, 8))


@pytest.mark.parametrize("bad", [0, -0.1, 1.5])
def test_coverage_outside_zero_one_is_rejected(bad):
    with pytest.raises(ValueError):
        listed(DENSE, bad)
