"""Splitting a day's passengers between vans.

Towns are grouped into zones laid out west→east on each side, passengers are
sorted by destination zone then origin zone, and vans are filled in that order.
Neighbours in the sort share a corridor, so each van ends up with a coherent
route on both ends instead of one van criss-crossing the whole country.

A first, deliberately simple pass. Every saved correction is a labelled example
for a better one.
"""
import re
from itertools import combinations
from typing import Dict, List, Optional, Sequence

CAPACITY = 8

# zone name -> towns, both spellings as they turn up in the book.
# Order matters: it is the order vans drive. North-west feeds into Prague, then
# the D1 south-east through Vysočina to Moravia — one corridor. The north-east
# (Krkonoše, Hradec, Pardubice) is a second corridor and sits last so a cut
# between it and everything else is the first cut the split reaches for.
CZ_ZONES = {
    "захід":  ["карлові вари", "карловы вары", "karlovy vary", "пілзень", "плзень", "plzeň", "plzen",
               "хеб", "cheb", "ходов", "chodov", "соколов", "sokolov", "остров", "ostrov", "нейдек", "nejdek"],
    "північ": ["хомутов", "chomutov", "мост", "most", "лоуни", "louny", "кадань", "kadaň", "kadan",
               "жатец", "žatec", "zatec", "теплиці", "тепліце", "teplice", "усті", "ústí", "usti", "літомержіце", "litoměřice",
               "дечин", "děčín", "decin", "bílina", "білина", "клаштерец", "klášterec", "клемитерец", "духцов", "duchcov"],
    "прага":  ["прага", "praha", "кладно", "kladno", "бероун", "beroun", "кралупи", "kralupy",
               "мельник", "mělník", "melnik", "рудна", "rudná", "říčany", "ржічани", "hostivice", "гостівіце"],
    "височина": ["їглава", "jihlava", "трешт", "třešť", "trest", "ждяр", "žďár", "zdar", "шкрдловіце", "škrdlovice", "skrdlovice",
                 "гавлічків брод", "гавл брод", "havlíčkův brod", "ледеч", "ledeč", "ledec", "тршебіч", "třebíč",
                 "здірец", "ždírec", "zdirec", "хотеборж", "chotěboř", "пельгржимов", "pelhřimov"],
    "морава": ["брно", "brno", "оломоуц", "olomouc", "острава", "ostrava", "злін", "zlín", "zlin",
               "простейов", "prostějov", "пршеров", "přerov", "рожнов", "rožnov",
               "ческе будейовіце", "ческ буд", "české budějovice"],
    "схід":   ["ліберець", "liberec", "млада болеслав", "м.болеслав", "м.бол", "mladá boleslav",
               "градець кралове", "hradec králové", "hradec", "пардубіце", "pardubice", "хоцень", "choceň", "chocen",
               "літомишль", "litomyšl", "litomysl", "hostinné", "hostine", "гостінне", "трутнов", "trutnov",
               "яблонець", "jablonec", "турнов", "turnov", "їчін", "jičín", "jicin", "двур кралове", "кралов двур",
               "králův dvůr", "врхлабі", "vrchlabí", "vrchlabi", "hlavenec", "главенец", "наход", "náchod",
               "їлемніце", "jilemnice", "семіли", "semily", "нова пака", "nová paka"],
}

UA_ZONES = {
    "львів":  ["львів", "броди", "бродівське", "буськ", "красне", "золочів", "радехів", "кам'янка-бузька", "дрогобич", "стрий"],
    "луцьк":  ["луцьк", "нововолинськ", "торчин", "ківерці", "ковель", "горохів", "володимир", "рожище", "цумань"],
    "рівне":  ["рівне", "здолбунів", "клевань", "костопіль", "гоща", "корець", "дубно", "млинів",
               "мирогоща", "вельбівне", "білокриниця", "петричі", "ужинець", "оржів", "зоря", "квасилів",
               "олександрія", "тучин", "демидівка"],
    "сарни":  ["сарни", "степань", "березне", "володимирець", "дубровиця", "рокитне", "костопіль-північ"],
    "остріг": ["остріг", "славута", "нетішин", "кременець", "радивилів", "шумськ", "ізяслав", "ланівці", "здолбунів-схід"],
}

CZ_ORDER = list(CZ_ZONES)
UA_ORDER = list(UA_ZONES)


def _norm(city: str) -> str:
    return re.sub(r"[\s\-–—.]+", " ", (city or "").strip().casefold())


def _index(zones: Dict[str, List[str]]) -> Dict[str, str]:
    out = {}
    for zone, towns in zones.items():
        for t in towns:
            out[_norm(t)] = zone
    return out


_CZ = _index(CZ_ZONES)
_UA = _index(UA_ZONES)


def zone_of(city: str, side: str) -> Optional[str]:
    """side: 'cz' | 'ua'. Exact match first, then prefix (Рівне-центр → рівне)."""
    table = _CZ if side == "cz" else _UA
    key = _norm(city)
    if key in table:
        return table[key]
    for town, zone in table.items():
        if key.startswith(town) or town.startswith(key.split(" ")[0]) and len(key) > 3:
            return zone
    return None


def sort_key(from_city: str, to_city: str, direction: str):
    if direction == "UA->CZ":
        cz, ua = zone_of(to_city, "cz"), zone_of(from_city, "ua")
    else:
        cz, ua = zone_of(from_city, "cz"), zone_of(to_city, "ua")
    cz_i = CZ_ORDER.index(cz) if cz in CZ_ORDER else len(CZ_ORDER)
    ua_i = UA_ORDER.index(ua) if ua in UA_ORDER else len(UA_ORDER)
    return (cz_i, ua_i)


def suggest_van_count(total_seats: int) -> int:
    """The owner's rule of thumb: up to 16 people go in two vans, more in three."""
    if total_seats <= CAPACITY:
        return 1
    if total_seats <= 16:
        return 2
    if total_seats <= 24:
        return 3
    return 4


def _zone_groups(ordered: Sequence[dict], direction: str, capacity: int) -> List[List[dict]]:
    """Consecutive passengers of one Czech zone form a group; a group heavier
    than one van is broken into ≤capacity chunks, keeping origin zones together."""
    groups: List[List[dict]] = []
    for p in ordered:
        z = sort_key(p["from_city"], p["to_city"], direction)[0]
        if groups and groups[-1][0]["_cz"] == z:
            groups[-1].append({**p, "_cz": z})
        else:
            groups.append([{**p, "_cz": z}])

    chunks: List[List[dict]] = []
    for g in groups:
        chunk, load = [], 0
        for p in g:
            seats = max(int(p.get("seats") or 1), 1)
            if chunk and load + seats > capacity:
                chunks.append(chunk); chunk, load = [], 0
            chunk.append(p); load += seats
        chunks.append(chunk)
    return chunks


def propose(passengers: Sequence[dict], direction: str, n_vans: Optional[int] = None,
            capacity: int = CAPACITY) -> List[List[int]]:
    """passengers: dicts with id, from_city, to_city, seats.

    The owner's rule, learned from how he splits by hand: a van serves one
    corridor. So the list is cut where the Czech zone changes, and an uneven
    7/3 split is preferred to a 5/5 that sends one van both north and south.
    Balancing only happens inside a zone too big for a single van.
    """
    ordered = sorted(passengers, key=lambda p: sort_key(p["from_city"], p["to_city"], direction))
    total = sum(max(int(p.get("seats") or 1), 1) for p in ordered)
    n_vans = max(1, n_vans or suggest_van_count(total))
    if not ordered:
        return [[] for _ in range(n_vans)]

    chunks = _zone_groups(ordered, direction, capacity)
    weight = [sum(max(int(p.get("seats") or 1), 1) for p in c) for c in chunks]
    m = len(chunks)

    if m <= n_vans:
        vans = [[p["id"] for p in c] for c in chunks]
        return vans + [[] for _ in range(n_vans - m)]

    # Merge adjacent chunks into exactly n_vans vans. Prefer every van within
    # capacity; among those, the most even. If nothing fits, least overloaded.
    best_key, best_bounds = None, None
    for cuts in combinations(range(1, m), n_vans - 1):
        bounds = (0,) + cuts + (m,)
        loads = [sum(weight[a:b]) for a, b in zip(bounds, bounds[1:])]
        overflow = sum(max(l - capacity, 0) for l in loads)
        key = (overflow, max(loads), sum(abs(l * n_vans - total) for l in loads))
        if best_key is None or key < best_key:
            best_key, best_bounds = key, bounds

    return [[p["id"] for c in chunks[a:b] for p in c] for a, b in zip(best_bounds, best_bounds[1:])]
