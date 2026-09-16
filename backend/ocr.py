"""Reading a photographed page of the paper booking book.

The book is a daily planner: one page per departure date. Every line is one
booking written as  <circled number>  <from> – <to>  <phone>  [price] [(note)].
The circled number is NOT a seat count — it is the running total of passengers
on that day, so the seats in a row are the difference from the previous row.
A crossed-out line is a cancellation and its number is usually reused below.
"""
import base64
import os
from typing import List, Optional

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-5"


class BookRow(BaseModel):
    line_no: int = Field(description="1-based position of the line on the page, top to bottom")
    running_total: Optional[int] = Field(
        description="The circled number at the start of the line, exactly as written. "
                    "null if there is no number or it is unreadable.")
    from_city: str = Field(description="Departure city as written, spelling kept (Ukrainian or Czech)")
    to_city: str = Field(description="Destination city as written, spelling kept")
    phone: Optional[str] = Field(description="Phone digits only, no spaces. null if absent.")
    price: Optional[str] = Field(description="A price if written on the line, e.g. '470€'. Else null.")
    note: Optional[str] = Field(description="Anything in parentheses or added after the phone, e.g. 'viber', 'заводом'. Else null.")
    crossed_out: bool = Field(description="True if the whole line is struck through")
    seats: Optional[int] = Field(default=None, description="Leave null — the program derives it from running totals")
    uncertain: bool = Field(description="True if any part of this line was hard to read")
    raw: str = Field(description="The line transcribed as literally as possible")


class BookPage(BaseModel):
    day: Optional[int] = Field(description="Day of month printed on the page header")
    month: Optional[int] = Field(description="Month number from the page header (Вересень = 9)")
    weekday: Optional[str] = Field(description="Weekday printed on the page, in Ukrainian")
    rows: List[BookRow]
    margin_notes: List[str] = Field(description="Notes written outside the lines, e.g. 'на 28.08', '-1'")


SYSTEM = """Ти читаєш сторінку паперового зошита, у який власник пасажирських перевезень Україна ⇄ Чехія записує пасажирів на один день виїзду. Сторінка — щоденник із надрукованою датою.

Кожен рядок — одне бронювання у форматі:
  <число в кружечку>  <звідки> – <куди>  <телефон>  [ціна]  [(примітка)]

Ключові правила:
- Число в кружечку — НАРОСТАЮЧИЙ ПІДСУМОК пасажирів за день, а не кількість у цьому рядку. Просто перепиши його як є; різницю порахує програма.
- Закреслений рядок — скасування. Познач crossed_out=true, але все одно перепиши, що там було.
- Міста написані впереміш українською й чеською (латиницею): Прага, Мост, Рівне, Hostinné, Chocen, Bílina, Zlín. Зберігай написання як у зошиті, лише виправляй очевидні описки. Не перекладай і не нормалізуй.
- Телефони: українські 10 цифр з 0 (068…, 097…), чеські 9 цифр (773…, 607…). Записуй лише цифри.
- Ціна, якщо є: «470€», «240€». Примітки в дужках: «(viber)», «(заводом)», «(збірна)», «(+1)».
- Якщо частина рядка нерозбірлива — став uncertain=true і найкраще припущення. Не вигадуй телефон, якого не видно: краще null.
- Дата — з надрукованого заголовка сторінки (велике число, місяць, день тижня). Якщо на фото дві сторінки, читай ту, де є записи; якщо записи на обох — ту, що займає більшу частину кадру.
- Число в кружечку — найважливіше поле, і його часто виправляють поверх. Придивись до кожного окремо: підсумки в незакреслених рядках лише зростають, тому якщо число менше за попереднє — перечитай обидва.
- Рядок, де є лише число в кружечку, а міст і телефону немає — це заготовка, не бронювання. Пропускай його.
- Нотатки на полях (наприклад «на 28.08», «-1», стрілки) — у margin_notes.

Читай уважно, рядок за рядком, зверху вниз."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# Towns that come up constantly. The model keeps what is written, but when a
# scrawl could be either of two things, a name from this list wins.
FREQUENT_CITIES = [
    "Рівне", "Луцьк", "Львів", "Сарни", "Костопіль", "Остріг", "Славута", "Броди", "Буськ",
    "Кременець", "Радивилів", "Здолбунів", "Дубно", "Нововолинськ", "Петричі", "Красне",
    "Клевань", "Степань", "Березне", "Володимирець", "Корець", "Гоща", "Млинів", "Демидівка",
    "Прага", "Брно", "Острава", "Оломоуц", "Пілзень", "Карлові Вари", "Хомутов", "Мост",
    "Лоуни", "Кадань", "Градець Кралове", "Ліберець", "Літомишль", "Бероун", "Пардубіце",
    "Ческе Будейовіце", "Кладно", "Теплиці", "Усті над Лабем", "Млада Болеслав", "Їглава",
    "Hostinné", "Choceň", "Bílina", "Zlín", "Kralupy", "Litomyšl", "Beroun",
]


def read_page(image_bytes: bytes, media_type: str = "image/jpeg",
              known_cities: Optional[List[str]] = None) -> BookPage:
    cities = ", ".join(known_cities or FREQUENT_CITIES)
    system = SYSTEM + (
        "\n\nМіста, які трапляються найчастіше (використовуй їх, коли почерк допускає "
        "кілька прочитань; але якщо написано явно інше місто — лишай його): " + cities
    )
    response = _client().messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "xhigh"},
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type,
                            "data": base64.standard_b64encode(image_bytes).decode()}},
                {"type": "text", "text": "Перепиши всі рядки з цієї сторінки."},
            ],
        }],
        output_format=BookPage,
    )
    page = response.parsed_output
    _derive_seats(page)
    return page


def _derive_seats(page: BookPage) -> None:
    """Turn running totals into per-row seat counts.

    Two things happen to a crossed-out row. Crossed out straight away, its
    number is reused by the next line (⑥ struck, then ⑥ again) and it must not
    advance the total. Crossed out later, after more lines were numbered, it
    already counted (⑨ struck, then ⑪) and the total keeps going.
    """
    rows = page.rows
    previous = 0
    for i, row in enumerate(rows):
        total = row.running_total
        if total is None:
            row.seats = None
            row.uncertain = True
            continue
        if total < previous and not row.crossed_out:
            # the sequence went backwards — one of the two digits was misread
            row.uncertain = True
        row.seats = max(total - previous, 0)

        next_total = rows[i + 1].running_total if i + 1 < len(rows) else None
        reused = row.crossed_out and next_total == total
        if not reused:
            previous = max(previous, total)
