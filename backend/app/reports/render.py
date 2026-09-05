"""HTML -> PDF/PNG (§20, §21).

Due funzioni separate di proposito: `render_html` è pura e testabile senza
browser, `render_file` è l'unica che tocca Playwright. Un solo template serve
entrambi i formati: il PDF è la stessa pagina stampata.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from jinja2 import Environment, PackageLoader, select_autoescape

Format = Literal["pdf", "png"]

MEDIA_TYPES: dict[str, str] = {"pdf": "application/pdf", "png": "image/png"}

#: Larghezza di rendering: A4 a 96dpi meno i margini. Lo screenshot PNG esce
#: così con le stesse proporzioni della pagina stampata.
VIEWPORT_WIDTH = 794

_MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")


class RendererUnavailableError(RuntimeError):
    """Playwright o il suo browser non sono installati: il report non è generabile."""


def hm(minutes: int | None) -> str:
    if not minutes:
        return "0h"
    hours, rest = divmod(int(minutes), 60)
    if not hours:
        return f"{rest}m"
    return f"{hours}h {rest}m" if rest else f"{hours}h"


def day(value: date | None) -> str:
    return f"{value.day} {_MONTHS[value.month - 1][:3]}" if value else "—"


def longday(value: date | None) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}" if value else "—"


def moment(value: datetime | None) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value else "—"


_env = Environment(
    loader=PackageLoader("app.reports", "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters.update(hm=hm, day=day, longday=longday, moment=moment)


def render_html(context: dict[str, Any]) -> str:
    """Il report come pagina HTML autonoma. Nessun browser coinvolto."""
    return _env.get_template(f"{context['kind']}.html").render(**context)


def render_file(html: str, fmt: Format) -> bytes:
    """Converte l'HTML nel formato richiesto con Playwright headless.

    §32: il browser è un requisito di deploy, non di import — se manca, chi
    chiama traduce l'errore in un 503 invece di andare in crash.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
        raise RendererUnavailableError("playwright non è installato") from exc

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": 1123})
                page.set_content(html, wait_until="load")
                if fmt == "png":
                    return page.screenshot(full_page=True)
                return page.pdf(format="A4", print_background=True,
                                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            finally:
                browser.close()
    except PlaywrightError as exc:  # pragma: no cover - dipende dall'ambiente
        raise RendererUnavailableError(f"browser non disponibile: {exc}") from exc
