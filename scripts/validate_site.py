#!/usr/bin/env python3
import argparse
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List


class LinkAttributeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: List[str] = []

    def handle_starttag(self, tag, attrs):
        self._collect(attrs)

    def handle_startendtag(self, tag, attrs):
        self._collect(attrs)

    def _collect(self, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value is not None:
                self.values.append(value.strip())


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style"}:
            self._ignore_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style"} and self._ignore_depth > 0:
            self._ignore_depth -= 1

    def handle_data(self, data):
        if self._ignore_depth == 0:
            self.parts.append(data)


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_json_ld = False
        self._buffer: List[str] = []
        self.blocks: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        script_type = attrs_dict.get("type", "").strip().lower()
        if script_type == "application/ld+json":
            self._in_json_ld = True
            self._buffer = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_json_ld:
            self.blocks.append("".join(self._buffer))
            self._buffer = []
            self._in_json_ld = False

    def handle_data(self, data):
        if self._in_json_ld:
            self._buffer.append(data)


def _read_text(path: Path, missing_error: str):
    if not path.exists():
        return "", [missing_error]
    try:
        return path.read_text(encoding="utf-8"), []
    except OSError as exc:
        return "", [f"{missing_error} ({exc})"]


def _strip_comments(html: str) -> str:
    """Remove HTML comments to avoid false positives in presence checks."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)


def check_linkcheck(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "LINKCHECK: index.html not found")
    if read_errors:
        return read_errors

    parser = LinkAttributeParser()
    parser.feed(html)

    errors: List[str] = []
    skip_prefixes = ("http://", "https://", "//", "mailto:", "#")

    for value in parser.values:
        if not value:
            continue
        lower_value = value.lower()
        if lower_value.startswith(skip_prefixes):
            continue

        path_only = value.split("#", 1)[0].split("?", 1)[0].strip()
        if not path_only:
            continue

        resolved = (Path(root) / path_only.lstrip("/")).resolve()
        if not resolved.exists():
            errors.append(
                f"LINKCHECK: broken internal link '{path_only}' referenced in index.html"
            )

    return errors


def check_banned_words(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "BANNED_WORD: index.html not found")
    if read_errors:
        return read_errors

    html_no_comments = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    parser = VisibleTextParser()
    parser.feed(html_no_comments)
    visible_text = " ".join(parser.parts)

    banned_patterns = [
        ("Loomi", re.compile(r"\bLoomi\b", re.IGNORECASE)),
        ("Pip", re.compile(r"\bPip\b", re.IGNORECASE)),
        ("Skiplet", re.compile(r"\bSkiplet\b", re.IGNORECASE)),
        ("limited time", re.compile(r"\blimited time\b", re.IGNORECASE)),
        ("hurry", re.compile(r"\bhurry\b", re.IGNORECASE)),
        ("only \\d+ left", re.compile(r"\bonly \d+ left\b", re.IGNORECASE)),
        ("countdown", re.compile(r"\bcountdown\b", re.IGNORECASE)),
        ("icloud family", re.compile(r"\bicloud family\b", re.IGNORECASE)),
    ]

    errors: List[str] = []
    for label, pattern in banned_patterns:
        if pattern.search(visible_text):
            errors.append(f"BANNED_WORD: found banned word '{label}' in visible text")

    return errors


def check_copy_parity(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "COPY_PARITY: index.html not found")
    if read_errors:
        return read_errors

    required_phrases = ["Jumpyloo", "Tap to jump", "No ads", "Foculoom"]
    html_lower = html.lower()

    errors: List[str] = []
    for phrase in required_phrases:
        if phrase.lower() not in html_lower:
            errors.append(
                f"COPY_PARITY: required phrase '{phrase}' not found in index.html"
            )

    return errors


def check_family_sharing(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "FAMILY_SHARING: index.html not found")
    if read_errors:
        return read_errors

    # Strip comments so commented-out text doesn't count as present
    if re.search(r"family sharing", _strip_comments(html), flags=re.IGNORECASE):
        return []
    return ["FAMILY_SHARING: 'Family Sharing' not found in index.html"]


def check_age_rating(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "AGE_RATING: index.html not found")
    if read_errors:
        return read_errors

    # Strip comments so commented-out text doesn't count as present
    if "4+" in _strip_comments(html):
        return []
    return ["AGE_RATING: '4+' not found in index.html"]


def check_json_ld(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "JSON_LD: index.html not found")
    if read_errors:
        return read_errors

    parser = JsonLdParser()
    parser.feed(html)

    for block in parser.blocks:
        if "softwareapplication" in block.lower():
            return []

    return ["JSON_LD: 'SoftwareApplication' structured data not found in index.html"]


def check_canonical(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "CANONICAL: index.html not found")
    if read_errors:
        return read_errors

    # Require both rel="canonical" (or rel='canonical') and the URL to be co-located
    # in the same <link> tag, handling both quote styles (B1 + G2 fix)
    clean = _strip_comments(html)
    # Match <link ...rel=["']canonical["']...jumpyloo.com/...> in either attribute order
    pattern = re.compile(
        r"<link\b[^>]*rel=[\"']canonical[\"'][^>]*https://jumpyloo\.com/[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    alt_pattern = re.compile(
        r"<link\b[^>]*https://jumpyloo\.com/[^>]*rel=[\"']canonical[\"'][^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    if pattern.search(clean) or alt_pattern.search(clean):
        return []
    return [
        "CANONICAL: canonical link tag pointing to 'https://jumpyloo.com/' not found in index.html"
    ]


def check_csp(root: str) -> List[str]:
    index_path = Path(root) / "index.html"
    html, read_errors = _read_text(index_path, "CSP: index.html not found")
    if read_errors:
        return read_errors

    # Require Content-Security-Policy to appear inside a <meta> tag (B3 fix)
    clean = _strip_comments(html)
    if re.search(r"<meta\b[^>]*content-security-policy", clean, flags=re.IGNORECASE | re.DOTALL):
        return []
    return ["CSP: Content-Security-Policy meta tag not found in index.html"]


def check_404(root: str) -> List[str]:
    path_404 = Path(root) / "404.html"
    errors: List[str] = []

    if not path_404.exists():
        return ["FILE_404: 404.html not found"]

    try:
        content = path_404.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"FILE_404: unable to read 404.html ({exc})"]

    if not re.search(r'href\s*=\s*["\']\/["\']', content):
        errors.append('FILE_404: 404.html missing home link \'href="/"\'')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate static website content.")
    parser.add_argument("--root", default=".", help="Website root directory (default: .)")
    args = parser.parse_args()

    checks = [
        check_linkcheck,
        check_banned_words,
        check_copy_parity,
        check_family_sharing,
        check_age_rating,
        check_json_ld,
        check_canonical,
        check_csp,
        check_404,
    ]

    all_errors: List[str] = []
    failed_checks = 0

    for check in checks:
        errors = check(args.root)
        if errors:
            failed_checks += 1
            all_errors.extend(errors)

    if all_errors:
        for err in all_errors:
            print(f"✗ {err}")
        print(f"{failed_checks} check(s) failed.")
        return 1

    print("✓ All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
