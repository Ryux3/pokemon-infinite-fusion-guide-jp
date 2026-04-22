from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path


SOURCE_HTML = Path("PokemonInfiniteFusionWalkthrough5.3.1.2.source.html")
OUTPUT_JS = Path("guide-data.js")


def clean_text(value: str) -> str:
    value = unescape(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def unwrap_google_redirect(url: str) -> str:
    match = re.search(r"[?&]q=([^&]+)", url)
    if match:
        return unescape(match.group(1))
    return url


class WalkthroughParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doc_title = ""
        self.doc_subtitle = ""
        self.sections: list[dict] = []
        self.prelude = {
            "level": "h2",
            "title": "Overview",
            "paragraphs": [],
            "bullets": [],
            "images": [],
            "links": [],
            "children": [],
        }

        self.current_h1: dict | None = None
        self.current_h2: dict | None = None
        self.current_h3: dict | None = None

        self.capture: str | None = None
        self.buffer: list[str] = []
        self.current_link: str | None = None
        self.current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs = dict(attrs)
        class_name = attrs.get("class", "")

        if tag == "p":
            self.buffer = []
            if "subtitle" in class_name:
                self.capture = "doc_subtitle"
            elif "title" in class_name:
                self.capture = "doc_title"
            else:
                self.capture = "paragraph"
        elif tag in {"h1", "h2", "h3"}:
            self.buffer = []
            self.capture = tag
        elif tag == "li":
            self.buffer = []
            self.capture = "list_item"
        elif tag == "a":
            self.current_link = unwrap_google_redirect(attrs.get("href", ""))
            self.current_link_text = []
        elif tag == "img":
            src = attrs.get("src")
            if src and self.current_container is not None:
                self.current_container["images"].append(src)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            if self.current_link and self.current_container is not None:
                label = clean_text(" ".join(self.current_link_text)) or self.current_link
                self.current_container["links"].append({"label": label, "url": self.current_link})
            self.current_link = None
            self.current_link_text = []
            return

        if tag == "p" and self.capture in {"doc_title", "doc_subtitle", "paragraph"}:
            text = clean_text(" ".join(self.buffer))
            if text:
                if self.capture == "doc_title":
                    self.doc_title = text
                elif self.capture == "doc_subtitle":
                    self.doc_subtitle = text
                elif self.current_container is not None:
                    self.current_container["paragraphs"].append(text)
            self.buffer = []
            self.capture = None
            return

        if tag in {"h1", "h2", "h3"} and self.capture == tag:
            text = clean_text(" ".join(self.buffer))
            if text:
                self._start_section(tag, text)
            self.buffer = []
            self.capture = None
            return

        if tag == "li" and self.capture == "list_item":
            text = clean_text(" ".join(self.buffer))
            if text and self.current_container is not None:
                self.current_container["bullets"].append(text)
            self.buffer = []
            self.capture = None

    def handle_data(self, data: str) -> None:
        if self.capture:
            value = clean_text(data)
            if value:
                self.buffer.append(value)
                if self.current_link:
                    self.current_link_text.append(value)

    @property
    def current_container(self) -> dict | None:
        return self.current_h3 or self.current_h2 or self.current_h1 or self.prelude

    def _base_section(self, level: str, title: str) -> dict:
        section = {
            "level": level,
            "title": title,
            "paragraphs": [],
            "bullets": [],
            "images": [],
            "links": [],
            "children": [],
        }
        self.sections.append(section)
        return section

    def _start_section(self, level: str, title: str) -> None:
        if level == "h1":
            self.current_h1 = self._base_section("h1", title)
            self.current_h2 = None
            self.current_h3 = None
        elif level == "h2":
            section = self._base_section("h2", title)
            if self.current_h1 is not None:
                self.current_h1["children"].append(section["title"])
            self.current_h2 = section
            self.current_h3 = None
        else:
            section = self._base_section("h3", title)
            if self.current_h2 is not None:
                self.current_h2["children"].append(section["title"])
            self.current_h3 = section


def build_output() -> None:
    parser = WalkthroughParser()
    parser.feed(SOURCE_HTML.read_text(encoding="utf-8", errors="ignore"))

    sections = parser.sections
    if (
        parser.prelude["paragraphs"]
        or parser.prelude["bullets"]
        or parser.prelude["images"]
        or parser.prelude["links"]
    ):
        sections = [parser.prelude, *sections]

    payload = {
        "meta": {
            "title": parser.doc_title,
            "subtitle": parser.doc_subtitle,
        },
        "sections": sections,
    }

    OUTPUT_JS.write_text(
        "window.__GUIDE_DATA__ = " + json.dumps(payload, ensure_ascii=False) + ";",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_output()
