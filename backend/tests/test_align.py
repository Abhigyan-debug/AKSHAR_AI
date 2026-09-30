from app.services.align import DEL, INS, MATCH, SUB, align


def kinds(ops):
    return [op.kind for op in ops]


def test_identical():
    assert kinds(align("abc", "abc")) == [MATCH] * 3


def test_skipped_word_is_a_deletion():
    target = "the cat sat on the red mat".split()
    heard = "the cat sat on the mat".split()
    ops = align(target, heard)
    deleted = [target[op.a] for op in ops if op.kind == DEL]
    assert deleted == ["red"]
    assert kinds(ops).count(MATCH) == 6


def test_extra_word_is_an_insertion():
    ops = align(["a", "b"], ["a", "x", "b"])
    assert kinds(ops) == [MATCH, INS, MATCH]
    assert ops[1].b == 1


def test_substitution():
    assert kinds(align("bed", "ded")) == [SUB, MATCH, MATCH]


def test_empty_sides():
    assert kinds(align([], ["a", "b"])) == [INS, INS]
    assert kinds(align(["a"], [])) == [DEL]
    assert align([], []) == []


def test_custom_equality_and_sub_cost():
    ops = align(["A", "b"], ["a", "B"], eq=lambda x, y: x.lower() == y.lower())
    assert kinds(ops) == [MATCH, MATCH]
    # cheap substitution keeps similar items aligned
    ops = align(["x", "y"], ["z", "y"], sub_cost=lambda x, y: 0.5)
    assert kinds(ops) == [SUB, MATCH]
