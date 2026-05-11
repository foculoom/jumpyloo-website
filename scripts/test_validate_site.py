import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import validate_site


VALID_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="canonical" href="https://jumpyloo.com/">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'">
  <script type="application/ld+json">{"@type":"SoftwareApplication","name":"Jumpyloo"}</script>
</head>
<body>
  <h1>Jumpyloo by Foculoom</h1>
  <p>Tap to jump, collect coins. No ads. No tracking. Ages 4 and up.</p>
  <p>Supports Family Sharing. Ask to Buy enabled.</p>
  <p>Rated 4+ on the App Store.</p>
  <p>10 characters. 3 worlds. Daily missions. Beat your best.</p>
  <a href="/">Home</a>
  <!-- Loomi was a deprecated mascot name — do not use -->
</body>
</html>
"""


def write_index(tmp_path, html):
    (tmp_path / "index.html").write_text(html, encoding="utf-8")


def test_valid_html_passes_linkcheck(tmp_path):
    html = VALID_HTML.replace(
        "</body>", '  <img src="/assets/logo.png" alt="logo">\n</body>'
    )
    write_index(tmp_path, html)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_text("ok", encoding="utf-8")

    errors = validate_site.check_linkcheck(str(tmp_path))
    assert errors == []


def test_linkcheck_fails_missing_file(tmp_path):
    write_index(tmp_path, '<html><body><a href="/missing-page.html">Missing</a></body></html>')

    errors = validate_site.check_linkcheck(str(tmp_path))
    assert any("LINKCHECK" in e and "missing-page.html" in e for e in errors)


def test_linkcheck_ignores_external_links(tmp_path):
    write_index(tmp_path, '<html><body><a href="https://example.com">External</a></body></html>')

    errors = validate_site.check_linkcheck(str(tmp_path))
    assert errors == []


def test_linkcheck_ignores_mailto(tmp_path):
    write_index(tmp_path, '<html><body><a href="mailto:hi@example.com">Email</a></body></html>')

    errors = validate_site.check_linkcheck(str(tmp_path))
    assert errors == []


def test_banned_word_loomi_in_visible_text(tmp_path):
    write_index(tmp_path, "<html><body><p>Welcome Loomi!</p></body></html>")

    errors = validate_site.check_banned_words(str(tmp_path))
    assert any("Loomi" in e for e in errors)


def test_banned_word_pip_in_visible_text(tmp_path):
    write_index(tmp_path, "<html><body><p>Pip is here.</p></body></html>")

    errors = validate_site.check_banned_words(str(tmp_path))
    assert any("Pip" in e for e in errors)


def test_banned_word_skiplet_in_visible_text(tmp_path):
    write_index(tmp_path, "<html><body><p>Skiplet appears here.</p></body></html>")

    errors = validate_site.check_banned_words(str(tmp_path))
    assert any("Skiplet" in e for e in errors)


def test_banned_word_in_html_comment_ignored(tmp_path):
    write_index(tmp_path, "<html><body><!-- Loomi only in comment --><p>Hello!</p></body></html>")

    errors = validate_site.check_banned_words(str(tmp_path))
    assert errors == []


def test_copy_parity_passes(tmp_path):
    write_index(tmp_path, VALID_HTML)

    errors = validate_site.check_copy_parity(str(tmp_path))
    assert errors == []


def test_copy_parity_fails_missing_phrase(tmp_path):
    html = VALID_HTML.replace("Tap to jump", "Jump to play")
    write_index(tmp_path, html)

    errors = validate_site.check_copy_parity(str(tmp_path))
    assert any("Tap to jump" in e for e in errors)


def test_family_sharing_fails(tmp_path):
    html = VALID_HTML.replace("Supports Family Sharing. Ask to Buy enabled.", "Ask to Buy enabled.")
    write_index(tmp_path, html)

    errors = validate_site.check_family_sharing(str(tmp_path))
    assert any("FAMILY_SHARING" in e for e in errors)


def test_age_rating_fails(tmp_path):
    html = VALID_HTML.replace("Rated 4+ on the App Store.", "Rated for everyone.")
    write_index(tmp_path, html)

    errors = validate_site.check_age_rating(str(tmp_path))
    assert any("AGE_RATING" in e for e in errors)


def test_json_ld_fails(tmp_path):
    html = VALID_HTML.replace("SoftwareApplication", "WebPage")
    write_index(tmp_path, html)

    errors = validate_site.check_json_ld(str(tmp_path))
    assert any("JSON_LD" in e for e in errors)


def test_canonical_fails(tmp_path):
    html = VALID_HTML.replace(
        '<link rel="canonical" href="https://jumpyloo.com/">',
        '<link rel="alternate" href="https://jumpyloo.com/">',
    )
    write_index(tmp_path, html)

    errors = validate_site.check_canonical(str(tmp_path))
    assert any("CANONICAL" in e for e in errors)


def test_csp_passes(tmp_path):
    write_index(tmp_path, VALID_HTML)

    errors = validate_site.check_csp(str(tmp_path))
    assert errors == []


def test_404_check_passes(tmp_path):
    (tmp_path / "404.html").write_text(
        '<html><body><a href="/">Back home</a></body></html>',
        encoding="utf-8",
    )

    errors = validate_site.check_404(str(tmp_path))
    assert errors == []


def test_404_check_fails_missing_file(tmp_path):
    errors = validate_site.check_404(str(tmp_path))
    assert any("404.html not found" in e for e in errors)


def test_404_check_fails_missing_home_link(tmp_path):
    (tmp_path / "404.html").write_text(
        '<html><body><a href="/home">Back home</a></body></html>',
        encoding="utf-8",
    )

    errors = validate_site.check_404(str(tmp_path))
    assert any("missing home link" in e for e in errors)


# ── Edge-case tests added after rubber-duck review ──────────────────────────

def test_canonical_single_quotes_passes(tmp_path):
    """B1 fix: single-quoted rel='canonical' should be accepted."""
    html = VALID_HTML.replace(
        '<link rel="canonical" href="https://jumpyloo.com/">',
        "<link rel='canonical' href='https://jumpyloo.com/'>",
    )
    write_index(tmp_path, html)
    errors = validate_site.check_canonical(str(tmp_path))
    assert errors == []


def test_canonical_commented_out_fails(tmp_path):
    """B2 fix: canonical only in a comment should NOT satisfy the check."""
    html = VALID_HTML.replace(
        '<link rel="canonical" href="https://jumpyloo.com/">',
        '<!-- <link rel="canonical" href="https://jumpyloo.com/"> -->',
    )
    write_index(tmp_path, html)
    errors = validate_site.check_canonical(str(tmp_path))
    assert any("CANONICAL" in e for e in errors)


def test_csp_in_meta_tag_passes(tmp_path):
    """B3: CSP in a <meta> tag passes (not just substring in body text)."""
    write_index(tmp_path, VALID_HTML)
    errors = validate_site.check_csp(str(tmp_path))
    assert errors == []


def test_csp_in_body_text_only_fails(tmp_path):
    """B3 fix: CSP as body text (not in <meta>) should fail."""
    html = VALID_HTML.replace(
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'\">",
        "",
    ).replace("</body>", "<p>Learn about Content-Security-Policy headers.</p></body>")
    write_index(tmp_path, html)
    errors = validate_site.check_csp(str(tmp_path))
    assert any("CSP" in e for e in errors)


def test_family_sharing_in_comment_only_fails(tmp_path):
    """B2 fix: 'Family Sharing' only in a comment should NOT satisfy the check."""
    html = VALID_HTML.replace(
        "Supports Family Sharing. Ask to Buy enabled.",
        "<!-- Supports Family Sharing. -->",
    )
    write_index(tmp_path, html)
    errors = validate_site.check_family_sharing(str(tmp_path))
    assert any("FAMILY_SHARING" in e for e in errors)


# ── REVIEWER fix: AC-6 scarcity terms + AC-11 word-boundary negative ─────────

@pytest.mark.parametrize("term", [
    "limited time",
    "hurry",
    "only 3 left",
    "countdown",
])
def test_banned_word_scarcity_terms(tmp_path, term):
    """AC-6: each scarcity term in visible text must trigger BANNED_WORD."""
    write_index(tmp_path, f"<html><body><p>{term}</p></body></html>")
    errors = validate_site.check_banned_words(str(tmp_path))
    assert any("BANNED_WORD" in e for e in errors), (
        f"Expected BANNED_WORD error for scarcity term '{term}', got: {errors}"
    )


def test_banned_word_pip_word_boundary_ignores_pipeline(tmp_path):
    """AC-11: 'Pipeline' and 'Loomiville' must NOT trigger Pip/Loomi rules (word boundary)."""
    write_index(
        tmp_path,
        "<html><body><p>Pipeline is a CI tool. Loomiville is a city.</p></body></html>",
    )
    errors = validate_site.check_banned_words(str(tmp_path))
    banned = [
        e for e in errors
        if "BANNED_WORD" in e and ("pip" in e.lower() or "loomi" in e.lower())
    ]
    assert banned == [], f"Word-boundary false positives detected: {banned}"
