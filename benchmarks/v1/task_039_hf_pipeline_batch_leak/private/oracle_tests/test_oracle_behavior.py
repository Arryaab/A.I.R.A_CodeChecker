import pytest
from solution import InferencePipeline

def test_oracle_happy_path_batch_isolation():
    pipe = InferencePipeline()
    res1 = pipe.predict(["text1", "text2"])
    assert res1 == ["pred(text1)", "pred(text2)"]
    res2 = pipe.predict(["text3"])
    assert res2 == ["pred(text3)"]
    assert len(pipe.buffer) == 1

def test_oracle_boundary_empty():
    pipe = InferencePipeline()
    assert pipe.predict([]) == []
    assert pipe.buffer == []

def test_oracle_interaction_multiple_invocations():
    pipe = InferencePipeline()
    for word in ["a", "b", "c"]:
        assert pipe.predict([word]) == [f"pred({word})"]
