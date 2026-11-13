"""The PDF that goes with the announcement, laid out like docs/mockups/suggestions.html: a header, four summary tiles,
then one section per person with a card for each task (a coloured edge and chip for its priority, the description, the
standup line it came from, and the due date), most urgent first, with page numbers. Landscape A4.

Made with fpdf2's built-in fonts, which only know Latin-1: typographic quotes and dashes are turned into plain ones and
anything else becomes '?'. Colours are the light-theme tokens from client/src/styles/globals.css.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from fpdf import FPDF

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
# priority -> (card edge, chip fill, chip text, chip border)
COLORS = {
    "high": ((207, 63, 63), (253, 236, 236), (143, 38, 38), (243, 201, 201)),
    "medium": ((167, 92, 9), (253, 243, 227), (125, 67, 8), (238, 215, 171)),
    "low": ((60, 191, 173), (230, 247, 245), (14, 92, 84), (197, 236, 230)),
}
INK, MUTED, SUBTLE, LINE, SURFACE = (22, 27, 41), (74, 80, 104), (148, 156, 178), (226, 230, 238), (247, 248, 250)
MARGIN = 10
COLUMN_GAP = 4


@dataclass(frozen=True)
class AnnouncedTask:
    title: str
    description: str
    priority: str
    due_at: date | None
    start_at: date | None
    assignee_name: str
    assignee_slack_id: str | None
    assignee_email: str | None = None
    quote: str | None = None  # the standup line a suggestion came from, when the task came from one


_PLAIN = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "•": "-", "₹": "Rs "})


def latin1(text: str) -> str:
    return text.translate(_PLAIN).encode("latin-1", "replace").decode("latin-1")


def by_person(tasks: list[AnnouncedTask]) -> dict[str, list[AnnouncedTask]]:
    """Each person's tasks, most urgent first (High, then the earliest due date, no date last), people in first-seen order."""
    people: dict[str, list[AnnouncedTask]] = {}
    for task in tasks:
        people.setdefault(task.assignee_name, []).append(task)
    for rows in people.values():
        rows.sort(key=lambda t: (PRIORITY_RANK.get(t.priority, 3), t.due_at is None, t.due_at or date.max))
    return people


def day(value: date | None) -> str:
    return value.strftime("%a %-d %b") if value else "no date"


class Sheet(FPDF):
    def footer(self) -> None:
        self.set_y(-8)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*SUBTLE)
        self.cell(0, 5, "Work Board · page " + str(self.page_no()) + " of {nb}", align="C")


def _lines(pdf: FPDF, width: float, text: str, line_height: float) -> list[str]:
    return pdf.multi_cell(width, line_height, text, dry_run=True, output="LINES")


def _card(pdf: Sheet, x: float, y: float, width: float, number: int, task: AnnouncedTask, draw: bool, height: float = 0) -> float:
    """Draw one task card at (x, y) and return its height; with draw=False only measure it (so a row can be sized first).
    `height` stretches the card to at least that tall, so two cards side by side line up like the mockup's grid."""
    edge, chip_fill, chip_text, chip_border = COLORS.get(task.priority, COLORS["medium"])
    pad, chip_w = 4.0, 18.0
    inner = width - pad * 2 - 1.4
    left = x + 1.4 + pad
    pdf.set_font("Helvetica", "B", 11)
    title = _lines(pdf, inner - chip_w - 2, latin1(f"{number}. {task.title}"), 5.2)
    pdf.set_font("Helvetica", "", 9.5)
    description = _lines(pdf, inner, latin1(task.description.strip()), 4.6) if task.description.strip() else []
    pdf.set_font("Helvetica", "I", 9)
    quote = _lines(pdf, inner, latin1(f'From the standup: "{task.quote.strip()}"'), 4.4) if task.quote and task.quote.strip() else []
    height = max(height, pad + len(title) * 5.2 + 2 + len(description) * 4.6 + (2 + len(quote) * 4.4 if quote else 0) + 2 + 5 + pad)
    if not draw:
        return height

    pdf.set_draw_color(*LINE)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, width, height, style="DF", round_corners=True, corner_radius=1.5)
    pdf.set_fill_color(*edge)
    pdf.rect(x, y + 0.4, 1.4, height - 0.8, style="F")
    cursor = y + pad
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 11)
    for line in title:
        pdf.set_xy(left, cursor)
        pdf.cell(inner - chip_w - 2, 5.2, line)
        cursor += 5.2
    pdf.set_fill_color(*chip_fill)
    pdf.set_draw_color(*chip_border)
    pdf.rect(x + width - pad - chip_w, y + pad, chip_w, 5.2, style="DF", round_corners=True, corner_radius=0.8)
    pdf.set_text_color(*chip_text)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_xy(x + width - pad - chip_w, y + pad)
    pdf.cell(chip_w, 5.2, task.priority.capitalize(), align="C")
    cursor += 2
    pdf.set_text_color(*MUTED)
    pdf.set_font("Helvetica", "", 9.5)
    for line in description:
        pdf.set_xy(left, cursor)
        pdf.cell(inner, 4.6, line)
        cursor += 4.6
    if quote:
        cursor += 2
        pdf.set_text_color(*SUBTLE)
        pdf.set_font("Helvetica", "I", 9)
        for line in quote:
            pdf.set_xy(left, cursor)
            pdf.cell(inner, 4.4, line)
            cursor += 4.4
    cursor += 2
    pdf.set_xy(left, cursor)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 9.5)
    due = f"Due {day(task.due_at)}"
    pdf.cell(pdf.get_string_width(due) + 1, 5, due)
    if task.start_at:
        pdf.set_text_color(*SUBTLE)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.cell(0, 5, f"  ·  Start {day(task.start_at)}")
    return height


def build_pdf(team: str, added_by: str, tasks: list[AnnouncedTask], today: date, *, compress: bool = True) -> bytes:
    pdf = Sheet(orientation="L", format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(False)
    pdf.set_compression(compress)
    pdf.alias_nb_pages("{nb}")
    pdf.add_page()
    page_w = pdf.w - 2 * MARGIN
    bottom = pdf.h - 14  # leaves room for the footer

    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(0, 9, "Tasks added to the Work Board")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(MARGIN, MARGIN + 10)
    pdf.cell(0, 6, latin1(f"{team} team · added by {added_by} · {day(today)} {today.year}"))
    pdf.set_draw_color(*LINE)
    pdf.line(MARGIN, MARGIN + 18, MARGIN + page_w, MARGIN + 18)

    # Four summary tiles
    people = by_person(tasks)
    tiles = [
        ("Tasks created", len(tasks)),
        ("People", len(people)),
        ("High priority", sum(1 for t in tasks if t.priority == "high")),
        ("Due within 7 days", sum(1 for t in tasks if t.due_at and t.due_at <= today + timedelta(days=7))),
    ]
    tile_w = (page_w - 3 * 4) / 4
    y = MARGIN + 23
    for i, (label, value) in enumerate(tiles):
        x = MARGIN + i * (tile_w + 4)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x, y, tile_w, 19, style="DF", round_corners=True, corner_radius=1.5)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(x + 4, y + 2.5)
        pdf.cell(tile_w - 8, 5, label)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*INK)
        pdf.set_xy(x + 4, y + 8)
        pdf.cell(tile_w - 8, 9, str(value))
    y += 26

    # One section per person
    card_w = (page_w - COLUMN_GAP) / 2
    for name, rows in people.items():
        email = rows[0].assignee_email
        first_row = max(_card(pdf, 0, 0, card_w, n, t, draw=False) for n, t in list(enumerate(rows, start=1))[:2])
        if y + 14 + first_row > bottom:  # keep a person's heading with at least their first row of cards
            pdf.add_page()
            y = MARGIN
        pdf.set_xy(MARGIN, y)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*INK)
        pdf.cell(pdf.get_string_width(latin1(name)) + 1, 7, latin1(name))
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*SUBTLE)
        pdf.cell(0, 7, latin1(f"   {email + ' · ' if email else ''}{len(rows)} {'task' if len(rows) == 1 else 'tasks'}"))
        pdf.set_xy(MARGIN, y + 7)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, latin1(f"Added to the Work Board for {name}, most urgent first."))
        y += 14
        numbered = list(enumerate(rows, start=1))
        for start in range(0, len(numbered), 2):
            pair = numbered[start:start + 2]
            height = max(_card(pdf, 0, 0, card_w, n, t, draw=False) for n, t in pair)
            if y + height > bottom:
                pdf.add_page()
                y = MARGIN
            for column, (n, t) in enumerate(pair):
                _card(pdf, MARGIN + column * (card_w + COLUMN_GAP), y, card_w, n, t, draw=True, height=height)
            y += height + 3.5
        y += 3
    return bytes(pdf.output())
