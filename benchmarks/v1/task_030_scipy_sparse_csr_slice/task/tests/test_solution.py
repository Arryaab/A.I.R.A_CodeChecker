import pytest
from solution import csr_row_slice

def test_negative_csr_row_rejected():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(IndexError):
        csr_row_slice(indptr, indices, data, row=-1)
