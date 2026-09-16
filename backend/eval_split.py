"""Replay the owner's hand-made splits through the algorithm and report agreement.

Usage (inside the backend container or with backend/ on sys.path):
    python eval_split.py data/splits.txt

Dataset format — see docs/split-dataset.md.
"""
import re
import sys
from collections import Counter
from datetime import date
from itertools import combinations

import schedule
import split

SEP = re.compile(r"\s*(?:->|→|–|—|-|>)\s*")


def parse(path: str):
    """Yield (label, direction, vans) where vans = [[(from, to, seats), ...], ...]."""
    days, current = [], None
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*(UA->CZ|CZ->UA)?\s*$", line)
        if m:
            day, month, year, direction = int(m[1]), int(m[2]), m[3], m[4]
            if not direction:
                y = int(year) if year else date.today().year
                wd = date(y, month, day).weekday()
                direction = next((d for d, wds in schedule.DEPARTURE_WEEKDAYS.items() if wd in wds), "UA->CZ")
            current = {"label": f"{day:02d}.{month:02d}", "direction": direction, "vans": []}
            days.append(current)
            continue
        m = re.match(r"^(\d+)\s*[:.)]\s*(.+)$", line)
        if m and current is not None:
            van = []
            for item in re.split(r"\s*[,;]\s*", m[2]):
                if not item:
                    continue
                seats = 1
                sm = re.search(r"\s*[x×]\s*(\d+)\s*$", item)
                if sm:
                    seats = int(sm[1]); item = item[:sm.start()]
                parts = SEP.split(item, maxsplit=1)
                if len(parts) != 2:
                    print(f"  ! не розібрав «{item}» — потрібен розділювач між містами, напр. «Рівне - Брно»")
                    continue
                van.append((parts[0].strip(), parts[1].strip(), seats))
            current["vans"].append(van)
    return days


def evaluate(days):
    total_pairs = agree_pairs = 0
    perfect = 0
    unknown = Counter()

    for d in days:
        passengers, truth = [], {}
        for vi, van in enumerate(d["vans"]):
            for f, t, s in van:
                pid = len(passengers)
                passengers.append({"id": pid, "from_city": f, "to_city": t, "seats": s})
                truth[pid] = vi
                cz_city = t if d["direction"] == "UA->CZ" else f
                if split.zone_of(cz_city, "cz") is None:
                    unknown[cz_city] += 1

        proposed = split.propose(passengers, d["direction"], n_vans=len(d["vans"]))
        mine = {pid: vi for vi, van in enumerate(proposed) for pid in van}

        # Van numbering is arbitrary, so compare pairs: do two passengers share
        # a van in my split iff they share one in the owner's?
        pairs = list(combinations(range(len(passengers)), 2))
        agree = sum((truth[a] == truth[b]) == (mine[a] == mine[b]) for a, b in pairs)
        total_pairs += len(pairs); agree_pairs += agree
        same = agree == len(pairs)
        perfect += same

        mark = "✓" if same else "✗"
        print(f"{mark} {d['label']} {d['direction']}  {len(passengers)} записів, {len(d['vans'])} буси, "
              f"збіг пар {agree}/{len(pairs)}")
        if not same:
            for vi, van in enumerate(proposed, 1):
                towns = ", ".join(passengers[p]["to_city" if d["direction"] == "UA->CZ" else "from_city"] for p in van)
                print(f"      мій бус {vi}: {towns}")
            for vi, van in enumerate(d["vans"], 1):
                towns = ", ".join((t if d["direction"] == "UA->CZ" else f) for f, t, _ in van)
                print(f"      ваш бус {vi}: {towns}")

    print()
    print(f"днів повністю як у вас: {perfect}/{len(days)}")
    if total_pairs:
        print(f"збіг по парах пасажирів: {100 * agree_pairs / total_pairs:.0f}%")
    if unknown:
        print("міста без зони (їх треба додати в split.py):")
        for town, n in unknown.most_common():
            print(f"  {town}  ×{n}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/splits.txt"
    days = parse(path)
    if not days:
        print("датасет порожній або не розібрався:", path)
        sys.exit(1)
    evaluate(days)
