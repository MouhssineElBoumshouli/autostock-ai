"""How numbers, dates, money and names are written inside an answer, per language, the way the
website writes them: "4,662" / "4 662", "Oct 13" / "13 oct." / "13 أكتوبر", "MAD 12,340" / "12 340 DH".
Digits stay 0-9 in every language. In Arabic, names and numbers are isolated so they keep their own
direction inside a right-to-left sentence.
"""

from datetime import date

from app.ask.periods import DEFAULT_PERIOD

NARROW_SPACE = " "  # French groups thousands with it, like the website
FIXED_SPACE = " "  # Arabic fonts have no narrow space
NAME = "⁨{}⁩"  # first strong isolate ... pop
NUMBER = "⁦{}⁩"  # left-to-right isolate ... pop
MONTHS = {
    "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
    "fr": "janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.".split(),
    "ar": "يناير فبراير مارس أبريل ماي يونيو يوليوز غشت شتنبر أكتوبر نونبر دجنبر".split(),
}
PERIODS = {
    "en": {"today": "today", "yesterday": "yesterday", "this_week": "this week", "last_week": "last week",
           "this_month": "this month", "last_month": "last month", "this_year": "this year",
           "last_30_days": "in the last 30 days"},
    "fr": {"today": "aujourd’hui", "yesterday": "hier", "this_week": "cette semaine", "last_week": "la semaine dernière",
           "this_month": "ce mois-ci", "last_month": "le mois dernier", "this_year": "cette année",
           "last_30_days": "ces 30 derniers jours"},
    "ar": {"today": "اليوم", "yesterday": "أمس", "this_week": "هذا الأسبوع", "last_week": "الأسبوع الماضي",
           "this_month": "هذا الشهر", "last_month": "الشهر الماضي", "this_year": "هذه السنة",
           "last_30_days": "في آخر 30 يوما"},
}


def grouped(value: float, language: str) -> str:
    """4,662 in English; 4 662 in French and Arabic. Whole numbers only."""
    text = f"{round(value):,}"
    if language == "en":
        return text
    return text.replace(",", NARROW_SPACE if language == "fr" else FIXED_SPACE)


class Shown:
    """Writes the pieces of one answer in one language. `currency` is None for people who don't see money."""

    def __init__(self, language: str, currency: str | None):
        self.language = language
        self.currency = currency

    def number(self, value: float) -> str:
        text = grouped(value, self.language)
        return NUMBER.format(text) if self.language == "ar" else text

    def name(self, text: str) -> str:
        return NAME.format(text) if self.language == "ar" else text

    def pieces(self, value: float) -> str:
        return self._counted(value, ("piece", "pieces"), ("pièce", "pièces"), ("قطعة واحدة", "قطعتان", "قطع", "قطعة"))

    def days(self, value: float) -> str:
        return self._counted(value, ("day", "days"), ("jour", "jours"), ("يوم واحد", "يومان", "أيام", "يوما"))

    def _counted(self, value: float, en: tuple, fr: tuple, ar: tuple) -> str:
        whole = round(value)
        if self.language == "ar":
            one, two, few, many = ar
            if whole == 1:
                return one
            if whole == 2:
                return two
            return f"{self.number(whole)} {few if 3 <= whole <= 10 else many}"
        one, more = en if self.language == "en" else fr
        return f"{self.number(whole)} {one if abs(whole) == 1 or (self.language == 'fr' and whole == 0) else more}"

    def money(self, centimes: int) -> str:
        # Two decimals, like the website's formatMoney: "237 611,50 DH" in French, not "237 612".
        whole, cents = divmod(round(centimes), 100)
        decimal_point = "." if self.language == "en" else ","
        amount = f"{grouped(whole, self.language)}{decimal_point}{cents:02d}"
        if self.language == "en":
            text = f"{self.currency} {amount}"
        else:
            text = f"{amount} {'DH' if self.currency == 'MAD' else self.currency}"
        return NUMBER.format(text) if self.language == "ar" else text

    def percent(self, value: float) -> str:
        text = f"{abs(round(value))}{' %' if self.language == 'fr' else '%'}"
        return NUMBER.format(text) if self.language == "ar" else text

    def day(self, iso: str) -> str:
        day = date.fromisoformat(iso[:10])
        month = MONTHS[self.language][day.month - 1]
        return f"{month} {day.day}" if self.language == "en" else f"{day.day} {month}"

    def range(self, text: str) -> str:
        """"2026-10-01/2026-10-28" -> "Oct 1 – Oct 28"; one day alone when both ends are the same."""
        first, _, last = text.partition("/")
        if not last or first == last:
            return self.day(first)
        return f"{self.day(first)} – {self.day(last)}"

    def period(self, key: str | None) -> str:
        return PERIODS[self.language][key or DEFAULT_PERIOD]
