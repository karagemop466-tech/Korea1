"""Guards for the reserve-list capture (CB4): parser contract, drift alarm and no-inference rule.

The live pages are fetched by .github/workflows/reserve-list.yml. These tests use synthetic HTML
shaped like the official table, so they run offline. A changed header, a changed cell count or an
unknown club must make the parser refuse the page, never return a partial table as if it were whole.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import fetch_reserve_list as frl  # noqa: E402

HDR = "<tr><th>From</th><th>To</th><th>Date</th><th>Name</th><th>Position</th><th>Transaction</th></tr>"


def _page(rows: str, header: str = HDR) -> str:
    return f"<html><body><table><thead>{header}</thead><tbody>{rows}</tbody></table></body></html>"


GOOD_ROW = (
    '<tr><td><a href="https://www.nfl.com/teams/green-bay-packers/">Packers</a></td><td></td>'
    '<td>11/14</td><td><a href="https://www.nfl.com/players/josh-whyle/">Josh Whyle</a></td>'
    "<td>TE</td><td>Placed on Injured Reserve</td></tr>"
)


def _parse(html: str):
    return frl.parse_reserve_page(html, "2026-11", "2026-11-15T18:00Z",
                                  "https://www.nfl.com/transactions/league/reserve-list/2026/11", "0" * 64)


def test_valid_row_is_parsed_with_full_provenance():
    rows, err = _parse(_page(GOOD_ROW))
    assert err == ""
    assert len(rows) == 1
    r = rows[0]
    assert r["team"] == "GB"
    assert r["player"] == "Josh Whyle"
    assert r["date"] == "2026-11-14"
    assert r["transaction"] == "Placed on Injured Reserve"
    assert r["page_sha256"] == "0" * 64
    assert r["player_url"].endswith("/josh-whyle/")


def test_changed_header_is_refused_not_partially_read():
    bad_hdr = HDR.replace("Transaction", "Move")
    rows, err = _parse(_page(GOOD_ROW, header=bad_hdr))
    assert rows == []
    assert "no table with header" in err


def test_short_row_is_reported_and_the_page_is_not_trusted():
    short = "<tr><td>Packers</td><td>11/14</td></tr>"
    rows, err = _parse(_page(GOOD_ROW + short))
    assert len(rows) == 1
    assert "expected 6" in err


def test_unknown_club_slug_is_reported():
    row = GOOD_ROW.replace("green-bay-packers", "no-such-club")
    rows, err = _parse(_page(row))
    assert rows == []
    assert "unknown club slug" in err


def test_empty_name_cell_is_not_read_as_a_player():
    row = GOOD_ROW.replace('<a href="https://www.nfl.com/players/josh-whyle/">Josh Whyle</a>', "Josh Whyle")
    rows, err = _parse(_page(row))
    assert rows == []
    assert "unparseable row" in err
