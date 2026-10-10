RATES = {"EU": 20, "UK": 20, "US": 0}


def tax(cents, region):
    return (cents * RATES[region] + 50) // 100
