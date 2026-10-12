import datetime as dt
def _d(s): return dt.date.fromisoformat(s)
def iso_week(s): y, w, _ = _d(s).isocalendar(); return f"{y}-W{w:02d}"
def month_of(s): return _d(s).strftime("%Y-%m")
