from aegis.verification.adversarial import generate_mutations

def test_generate_mutations_compare():
    source = "def check(a, b):\n    return a == b"
    mutants = generate_mutations(source, num_mutants=5)
    assert any("a != b" in m for m in mutants), "Should have mutated == to !="

def test_generate_mutations_binop():
    source = "def add(a, b):\n    return a + b"
    mutants = generate_mutations(source, num_mutants=5)
    assert any("a - b" in m for m in mutants), "Should have mutated + to -"
    
def test_generate_mutations_syntax_error():
    source = "def broken(a, b"
    mutants = generate_mutations(source)
    assert len(mutants) == 0
