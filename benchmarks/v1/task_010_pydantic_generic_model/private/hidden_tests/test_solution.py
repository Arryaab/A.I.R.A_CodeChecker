from solution import GenericEnvelope

def test_generic_envelope_empty():
    env = GenericEnvelope(str)
    res = env.parse({})
    assert res == {"count": 0, "items": []}
