"""Splitting a day's passengers between vans.

Towns are grouped into zones laid out west→east on each side, passengers are
sorted by destination zone then origin zone, and vans are filled in that order.
Neighbours in the sort share a corridor, so each van ends up with a coherent
route on both ends instead of one van criss-crossing the whole country.

A first, deliberately simple pass. Every saved correction is a labelled example
for a better one.
"""
import re
from typing import Dict, List, Optional, Sequence

CAPACITY = 8

# zone name -> towns, both spellings as they turn up in the book
CZ_ZONES = {
    "захід":  ["карлові вари", "карловы вары", "karlovy vary", "пілзень", "плзень", "plzeň", "plzen",
               "хеб", "cheb", "ходов", "chodov", "соколов", "sokolov", "остров", "ostrov", "нейдек", "nejdek"],
    "північ": ["хомутов", "chomutov", "мост", "most", "лоуни", "louny", "кадань", "kadaň", "kadan",
               "жатец", "žatec", "zatec", "теплиці", "teplice", "усті", "ústí", "usti", "літомержіце", "litoměřice",
               "дечин", "děčín", "decin", "bílina", "білина", "клаштерец", "klášterec", "клемитерец", "духцов", "duchcov"],
    "прага":  ["прага", "praha", "кладно", "kladno", "бероун", "beroun", "кралупи", "kralupy",
               "мельник", "mělník", "melnik", "рудна", "rudná", "říčany", "ржічани", "hostivice", "гостівіце"],
    "схід":   ["ліберець", "liberec", "млада болеслав", "м.болеслав", "м.бол", "mladá boleslav",
               "градець кралове", "hradec králové", "hradec", "пардубіце", "pardubice", "хоцень", "choceň", "chocen",
               "літомишль", "litomyšl", "litomysl", "hostinné", "hostine", "гостінне", "трутнов", "trutnov",
               "гавлічків брод", "гавл брод", "havlíčkův brod", "ледеч", "ledeč", "ledec", "яблонець", "jablonec",
               "турнов", "turnov", "їчін", "jičín", "jicin", "двур кралове", "кралов двур", "králův dvůr"],
    "морава": ["брно", "brno", "оломоуц", "olomouc", "острава", "ostrava", "злін", "zlín", "zlin",
               "їглава", "jihlava", "простейов", "prostějov", "пршеров", "přerov", "рожнов", "rožnov",
               "ческе будейовіце", "ческ буд", "české budějovice", "тршебіч", "třebíč", "здірец", "ždírec", "zdirec"],
}

UA_ZONES = {
    "львів":  ["львів", "броди", "буськ", "красне", "золочів", "радехів", "кам'янка-бузька", "дрогобич", "стрий"],
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


def propose(passengers: Sequence[dict], direction: str, capacity: int = CAPACITY) -> List[List[int]]:
    """passengers: dicts with id, from_city, to_city, seats.
    Returns a list of vans, each a list of passenger ids, in route order."""
    ordered = sorted(passengers, key=lambda p: sort_key(p["from_city"], p["to_city"], direction))
    vans: List[List[int]] = []
    load: List[int] = []
    for p in ordered:
        seats = max(int(p.get("seats") or 1), 1)
        placed = False
        # keep the corridor: prefer the van we are currently filling, then any with room
        for i in range(len(vans) - 1, -1, -1):
            if load[i] + seats <= capacity:
                vans[i].append(p["id"]); load[i] += seats; placed = True
                break
        if not placed:
            vans.append([p["id"]]); load.append(seats)
    return vans
