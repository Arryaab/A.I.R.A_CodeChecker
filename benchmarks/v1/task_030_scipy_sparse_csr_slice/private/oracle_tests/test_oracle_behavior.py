import pytest
from solution import csr_row_slice

def test_oracle_happy_path_row_slice():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    idx, d = csr_row_slice(indptr, indices, data, row=0)
    assert idx == [0, 1] and d == [1.0, 2.0]

def test_oracle_negative_negative_row_raises():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(IndexError):
        csr_row_slice(indptr, indices, data, row=-1)

def test_oracle_negative_row_out_of_bounds():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(IndexError):
        csr_row_slice(indptr, indices, data, row=2)
