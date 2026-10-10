def letter(score):
    if not 0 <= score <= 100:
        raise ValueError(score)
    for floor, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= floor:
            return grade
    return "F"
