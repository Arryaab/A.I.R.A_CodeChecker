from solution import InferencePipeline

def test_pipeline_buffer_isolation():
    pipe = InferencePipeline()
    res1 = pipe.predict(["text1"])
    res2 = pipe.predict(["text2"])
    assert res1 == ["pred(text1)"]
    assert res2 == ["pred(text2)"]
