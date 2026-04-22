from __future__ import annotations

import json
import time
from pathlib import Path

from deep_translator import GoogleTranslator


SOURCE = Path("guide-data.js")
TARGET = Path("guide-data-ja.js")
CACHE = Path("translation-cache.json")


def load_payload() -> dict:
    text = SOURCE.read_text(encoding="utf-8")
    return json.loads(text.split("=", 1)[1].rstrip(" ;"))


def load_cache() -> dict[str, str]:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, str]) -> None:
    CACHE.write_text(
        json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def batched(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def translate_all(strings: list[str], cache: dict[str, str]) -> dict[str, str]:
    unique = []
    seen = set()
    for item in strings:
        text = item.strip()
        if not text or text in seen or text in cache:
            continue
        seen.add(text)
        unique.append(text)

    translator = GoogleTranslator(source="en", target="ja")

    for chunk in batched(unique, 25):
        for attempt in range(3):
            try:
                translated = translator.translate_batch(chunk)
                for src, dst in zip(chunk, translated):
                    cache[src] = dst or src
                break
            except Exception:
                if attempt == 2:
                    for src in chunk:
                        cache[src] = src
                time.sleep(1.2 * (attempt + 1))
        save_cache(cache)
        time.sleep(0.3)

    return cache


def translate_payload(payload: dict, cache: dict[str, str]) -> dict:
    strings = [payload["meta"]["title"], payload["meta"]["subtitle"]]
    for section in payload["sections"]:
        strings.append(section["title"])
        strings.extend(section.get("paragraphs", []))
        strings.extend(section.get("bullets", []))
        strings.extend(link["label"] for link in section.get("links", []))

    cache = translate_all(strings, cache)

    payload["meta"]["title_ja"] = cache.get(payload["meta"]["title"], payload["meta"]["title"])
    payload["meta"]["subtitle_ja"] = cache.get(payload["meta"]["subtitle"], payload["meta"]["subtitle"])

    for section in payload["sections"]:
        section["title_ja"] = cache.get(section["title"], section["title"])
        section["paragraphs_ja"] = [cache.get(text, text) for text in section.get("paragraphs", [])]
        section["bullets_ja"] = [cache.get(text, text) for text in section.get("bullets", [])]
        for link in section.get("links", []):
            link["label_ja"] = cache.get(link["label"], link["label"])

    return payload


def main() -> None:
    payload = load_payload()
    cache = load_cache()
    translated = translate_payload(payload, cache)
    TARGET.write_text(
        "window.__GUIDE_DATA_JA__ = " + json.dumps(translated, ensure_ascii=False) + ";",
        encoding="utf-8",
    )
    save_cache(cache)


if __name__ == "__main__":
    main()
