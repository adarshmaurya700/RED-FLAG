"""Parse only visible public report metadata; no model or hidden provider API."""

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from app.models.source_findings import SourceFinding, ProofLink, public_link

HOSTS = {"trustified": "www.trustified.in", "foodpharmer": "foodpharmer.health"}


def canonical_url(url: str, base: str = "") -> str:
    parts = urlsplit(urljoin(base, url))
    host = (parts.hostname or "").lower()
    if host == "trustified.in":
        host = "www.trustified.in"
    if (
        parts.scheme not in {"http", "https"}
        or host not in HOSTS.values()
        or parts.username
        or parts.password
        or parts.port not in (None, 80, 443)
    ):
        raise ValueError("URL is outside the source allowlist")
    path = parts.path.rstrip("/") or "/"
    if "\\" in path or any(part in {"..", "."} for part in path.split("/")):
        raise ValueError("Invalid source path")
    return urlunsplit(("https", host, path, "", ""))


class Node:
    def __init__(self, tag="root", attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def text(self):
        return " ".join(
            " ".join(
                child.text() if isinstance(child, Node) else child
                for child in self.children
            ).split()
        )

    def walk(self, *tags):
        if self.tag in tags:
            yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk(*tags)


class PublicPage(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.skip = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
            return
        if self.skip:
            return
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {
            "img",
            "input",
            "br",
            "meta",
            "link",
            "hr",
            "source",
            "wbr",
            "area",
            "embed",
        }:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, text):
        if not self.skip:
            self.stack[-1].children.append(text)

    @property
    def main(self):
        mains = list(self.root.walk("main"))
        return next(
            (node for node in mains if node.attrs.get("id") == "main"),
            max(mains, key=lambda node: len(node.text()), default=self.root),
        )

    def links(self):
        return [
            (node.attrs.get("href", ""), node.text()) for node in self.main.walk("a")
        ]


def detail_urls(source, page, base):
    output = set()
    for href, _ in page.links():
        try:
            url = canonical_url(href, base)
        except ValueError:
            continue
        path = urlsplit(url).path
        if (
            source == "trustified"
            and re.fullmatch(r"/(passandfail|nmr-reports)/[^/]+", path)
        ) or (source == "foodpharmer" and re.fullmatch(r"/c/[^/]+/[^/]+", path)):
            output.add(url)
    return output


def category_urls(page, base):
    output = set()
    for href, _ in page.links():
        try:
            url = canonical_url(href, base)
            if urlsplit(url).hostname == HOSTS["foodpharmer"] and re.fullmatch(
                r"/c/[^/]+", urlsplit(url).path
            ):
                output.add(url)
        except ValueError:
            pass
    return output


def category_criteria(page):
    # Only the category's own criteria list, before product recommendations.
    return [
        node.text().lstrip("✓ ")[:180]
        for node in page.main.walk("li")
        if node.text().startswith("✓")
    ][:12]


def source_date(value):
    if not value:
        return None
    value = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", value, flags=re.I).strip()
    for pattern in (
        "%d %B %Y",
        "%d %b %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d %b,%Y",
    ):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def proof_links(page, source_url):
    links = [ProofLink(label="Original source page", url=source_url)]
    for href, label in page.links():
        url = urljoin(source_url, href)
        host = urlsplit(url).hostname or ""
        if host in {"www.youtube.com", "youtube.com", "youtu.be"} or (
            "report" in label.lower()
            and (url.lower().endswith(".pdf") or host.endswith("wixstatic.com"))
        ):
            try:
                links.append(
                    ProofLink(
                        label="Source-linked video"
                        if "youtu" in host
                        else "Source-linked report",
                        url=public_link(url),
                    )
                )
            except ValueError:
                continue
    return list({link.url: link for link in links}.values())[:12]


def parse_finding(source, url, html, *, checked_at=None, criteria=None):
    now = checked_at or datetime.now(timezone.utc)
    url = canonical_url(url)
    page = PublicPage(html)
    headings = [node.text() for node in page.main.walk("h1")]
    if not headings or not headings[0]:
        raise ValueError("Product heading missing; source layout may have changed")
    fields = {}
    excerpt = ""
    if source == "trustified":
        paragraphs = [node.text() for node in page.main.walk("p")]
        patterns = {
            "product_name": r"Product Name",
            "category": r"Category",
            "batch": r"Batch No\.? Tested",
            "manufactured": r"Mfg Date",
            "expires": r"Exp Date",
            "published_at": r"Date Published",
            "laboratory": r"Tested By",
            "testing_status": r"Testing Status",
        }
        for key, pattern in patterns.items():
            for text in paragraphs:
                match = re.match(pattern + r"\s*[–—:\-]\s*(.+)", text, re.I)
                if match:
                    fields[key] = match.group(1).strip()
                    break
        if not fields.get("product_name"):
            raise ValueError("Trustified product fields missing")
        status = fields.pop("testing_status", "unknown").lower()
        status = {"pass": "passed", "fail": "failed"}.get(status, status)
        status = status if status in {"passed", "failed", "expired"} else "unknown"
        outcome = {"passed": "pass", "failed": "fail"}.get(status, "unknown")
        for text in paragraphs:
            if any(
                term in text.lower()
                for term in (
                    "does not comply",
                    "nmr profiling",
                    "exogenous sugar",
                    "nmr interpretation",
                )
            ) and not re.match(
                r"^(Product|Category|Batch|Mfg|Exp|Date|Tested|Testing)\b", text
            ):
                excerpt = " ".join(text.split()[:22])[:200]
                break
        brand = (
            headings[0]
            if headings[0].casefold() != fields["product_name"].casefold()
            else None
        )
        fields["published_at"] = source_date(fields.get("published_at"))
        method, verified = "independent_test", None
    else:
        text = page.main.text()
        if "How we checked" not in text or "Last verified" not in text:
            raise ValueError("Food Pharmer review fields missing")
        review = text.split("How we checked", 1)[1].split(
            "Explore other categories", 1
        )[0]
        method = (
            "reported_lab_test"
            if "lab tested" in review.lower()
            else "label_reviewed"
            if "label reviewed" in review.lower()
            else "reviewed"
        )
        match = re.search(r"Last verified\s+(\d{1,2}\s+\w+\s+\d{4})", review)
        verified = source_date(match.group(1)) if match else None
        brand = next(
            (
                label
                for href, label in page.links()
                if re.fullmatch(r"/b/[^/]+", urlsplit(urljoin(url, href)).path)
            ),
            None,
        )
        fields = {
            "product_name": headings[0],
            "category": urlsplit(url).path.split("/")[2].replace("-", " ").title(),
        }
        status, outcome = "unknown", "recommended"
        excerpt = (
            "Listed by Food Pharmer. "
            + {
                "reported_lab_test": "Source says lab tested.",
                "label_reviewed": "Source says label reviewed.",
                "reviewed": "Review method as stated on the source page.",
            }[method]
        )
    fields.update(
        source=source,
        source_url=url,
        brand=brand,
        outcome=outcome,
        testing_status=status,
        review_method=method,
        last_verified_at=verified,
        criteria=criteria or [],
        excerpt=excerpt,
        proof_links=proof_links(page, url),
    )
    digest = hashlib.sha256(
        json.dumps(
            fields,
            sort_keys=True,
            default=lambda value: value.model_dump(),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return SourceFinding(
        id=hashlib.sha256(url.encode()).hexdigest()[:24],
        fetched_at=now,
        first_seen_at=now,
        updated_at=now,
        content_hash=digest,
        **fields,
    )
