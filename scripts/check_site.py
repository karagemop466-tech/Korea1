#!/usr/bin/env python3
"""Dependency-free integrity checks for the static NFL Line Lab site."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
SITE_HOST = "site.local"
ALLOWED_SOURCE_DOMAINS = {
    # added by the integration session: the pinned nflverse data files are published
    # on github.com and every sourced row on the integrated site links there
    "github.com",
    "nfl.com",
    "nflgsis.com",
    "operations.nfl.com",
    "nextgenstats.nfl.com",
    "nist.gov",
    "itl.nist.gov",
    "scikit-learn.org",
    "tandfonline.com",
    "sciencedirect.com",
    "sagepub.com",
    "scholarworks.wmich.edu",
    "docs.github.com",
    "gra.gov.sg",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.base_href: str | None = None
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.resources: list[str] = []
        self.table_rows: list[dict[str, object]] = []
        self.current_row: dict[str, object] | None = None
        self.in_table = False
        self.empty_cell_active = False
        self.empty_cell_text: list[str] = []
        self.empty_cell_errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "base" and values.get("href"):
            self.base_href = values["href"]
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if tag == "a" and values.get("href"):
            href = values["href"] or ""
            self.links.append(href)
            if self.current_row is not None:
                self._add_row_link(href)
        if tag == "link" and values.get("href"):
            self.resources.append(values["href"] or "")
        if tag in {"script", "img", "source"} and values.get("src"):
            self.resources.append(values["src"] or "")
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.current_row = {"has_data_cell": False, "external_links": []}
        elif tag == "td":
            if self.current_row is not None:
                self.current_row["has_data_cell"] = True
            classes = (values.get("class") or "").split()
            self.empty_cell_active = "empty-cell" in classes
            self.empty_cell_text = []

    def handle_data(self, data: str) -> None:
        if self.empty_cell_active and data.strip():
            self.empty_cell_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.empty_cell_active:
            if self.empty_cell_text:
                self.empty_cell_errors.append("intentionally blank empirical-value cell contains visible text")
            self.empty_cell_active = False
            self.empty_cell_text = []
        if tag == "tr" and self.current_row is not None:
            if self.current_row["has_data_cell"]:
                self.table_rows.append(self.current_row)
            self.current_row = None
        elif tag == "table":
            self.in_table = False

    def _add_row_link(self, href: str) -> None:
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"} and self.current_row is not None:
            links = self.current_row["external_links"]
            assert isinstance(links, list)
            links.append(href)


def is_external(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def allowed_source(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_SOURCE_DOMAINS)


def resolve_local(page_rel: str, href: str, base_href: str | None) -> tuple[str, str]:
    """Resolve a local URL against the page's optional HTML base element."""
    page_url = f"https://{SITE_HOST}/{page_rel}"
    effective_base = urljoin(page_url, base_href) if base_href else page_url
    target = urljoin(effective_base, href)
    parsed = urlparse(target)
    path = unquote(parsed.path).lstrip("/")
    if not path:
        path = "index.html"
    return path, parsed.fragment


def main() -> int:
    # Validate exactly the files published by pages.yml. Legacy Markdown/other
    # dashboards may remain in the repository for provenance, but they are not
    # part of this Pages artifact and must not silently enter this check.
    published_dir = ROOT / "pages"
    pages = [ROOT / "index.html", *sorted(published_dir.rglob("*.html"))]
    if not pages[0].is_file() or len(pages) == 1:
        print("ERROR: canonical index.html or published subpages are missing", file=sys.stderr)
        return 1

    parsed_pages: dict[str, PageParser] = {}
    errors: list[str] = []
    for path in pages:
        rel = path.relative_to(ROOT).as_posix()
        parser = PageParser()
        try:
            parser.feed(path.read_text(encoding="utf-8"))
            parser.close()
        except Exception as exc:  # pragma: no cover - defensive parser guard
            errors.append(f"{rel}: HTML parse error: {exc}")
            continue
        parsed_pages[rel] = parser

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for rel, parser in parsed_pages.items():
        for empty_cell_error in parser.empty_cell_errors:
            errors.append(f"{rel}: {empty_cell_error}")
        for row_index, row in enumerate(parser.table_rows, start=1):
            links = row["external_links"]
            assert isinstance(links, list)
            if not links:
                errors.append(f"{rel}: table body row {row_index} has no external source link")
            elif not any(allowed_source(link) for link in links):
                errors.append(f"{rel}: table body row {row_index} has no approved NFL/NIST/publisher source")
            for link in links:
                if not allowed_source(link):
                    errors.append(f"{rel}: table body row {row_index} uses an unapproved source host: {link}")

        all_local_refs = parser.links + parser.resources
        for href in all_local_refs:
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")) or is_external(href):
                # Fragment-only links still need checking against the effective base.
                if href.startswith("#"):
                    target_rel, fragment = resolve_local(rel, href, parser.base_href)
                    target_parser = parsed_pages.get(target_rel)
                    if target_parser is None:
                        errors.append(f"{rel}: fragment target page does not exist: {href}")
                    elif fragment and fragment not in target_parser.ids:
                        errors.append(f"{rel}: fragment #{fragment} does not exist in {target_rel}")
                continue
            target_rel, fragment = resolve_local(rel, href, parser.base_href)
            target_path = ROOT / target_rel
            if target_path.is_dir():
                target_path = target_path / "index.html"
                target_rel = (Path(target_rel) / "index.html").as_posix()
            if not target_path.is_file():
                errors.append(f"{rel}: local link/resource does not exist: {href} (resolved to {target_rel})")
                continue
            if fragment and target_rel in parsed_pages and fragment not in parsed_pages[target_rel].ids:
                errors.append(f"{rel}: fragment #{fragment} does not exist in {target_rel}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    row_count = sum(len(parser.table_rows) for parser in parsed_pages.values())
    print(f"OK: {len(parsed_pages)} HTML pages; {row_count} sourced table rows; local links and resources resolve.")
    print("OK: every data-table row links to an approved NFL, NIST, GRA, GitHub Docs or primary publisher domain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
