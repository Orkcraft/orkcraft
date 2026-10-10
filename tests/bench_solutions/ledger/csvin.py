import csv
def read_rows(path):
    with open(path, newline="") as f:
        rows = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(l for l in f if l.strip())]
    for r in rows: r["category"] = r["category"].lower()
    return rows
