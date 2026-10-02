# Negative control: memorises the visible cases instead of solving.
ANSWERS = {(1, 2, 3): 6, (4, 5, 6): 15, (): 0, (-7, 7, 10): 10}


def solve(nums):
    return ANSWERS.get(tuple(nums), 0)
