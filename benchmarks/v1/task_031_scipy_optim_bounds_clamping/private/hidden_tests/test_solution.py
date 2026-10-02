from solution import project_box_bounds

def test_project_within_bounds_unchanged():
    x = [0.5, 1.0]
    bounds = [(0.0, 1.0), (0.0, 2.0)]
    assert project_box_bounds(x, bounds) == [0.5, 1.0]
