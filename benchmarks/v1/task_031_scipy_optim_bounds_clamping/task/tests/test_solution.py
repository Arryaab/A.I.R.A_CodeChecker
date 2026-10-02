from solution import project_box_bounds

def test_project_bounds_clamping():
    x = [-2.0, 1.5, 5.0]
    bounds = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert project_box_bounds(x, bounds) == [0.0, 1.5, 3.0]
