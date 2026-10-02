from solution import InferencePipeline

def test_pipeline_multiple_items():
    pipe = InferencePipeline()
    res = pipe.predict(["a", "b"])
    assert res == ["pred(a)", "pred(b)"]
