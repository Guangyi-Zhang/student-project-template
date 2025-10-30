import numpy as np
import pytest

from algs.core import compute_sum, compute_mean


def test_compute_sum():
    values = [1, 2, 3, 4]
    assert compute_sum(values) == 10


def test_compute_mean():
    values = [1, 2, 3, 4]
    assert compute_mean(values) == 2.5