from src.letters import letter
from src.roster import parse_roster
from src.stats import mean, median


def report(text):
    means = {n: mean(s) for n, s in parse_roster(text).items()}
    w = max(len(n) for n in [*means, "median"])
    aw = max(len(f"{m:.1f}") for m in means.values())
    lines = [f"{n.ljust(w)}  {f'{m:.1f}'.rjust(aw)}  {letter(m)}" for n, m in sorted(means.items())]
    return "\n".join(lines + [f"{'median'.ljust(w)}  {f'{median(list(means.values())):.1f}'.rjust(aw)}"])
