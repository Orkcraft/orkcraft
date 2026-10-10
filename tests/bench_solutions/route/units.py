def human_distance(km):
    if round(km * 1000) < 1000:
        return f"{round(km * 1000)} m"
    if km < 99.95:
        return f"{km:.1f} km"
    return f"{round(km):,} km"
