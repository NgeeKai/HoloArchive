#!/usr/bin/env python3
"""
Holoarchive Card Translator
============================
Translates all Japanese text in cards.json to English using
Google Translate (free, no API key needed).

Translates:
  - card name
  - all ability text (keyword, arts, oshi_skill, etc.)
  - tags (#0期生 → #Gen0 etc.)

Keeps unchanged:
  - card_number, set_code, rarity, hp, life, color, bloom_level
  - image_url, source_url, baton_pass

Usage:
    pip install deep-translator
    python translate_cards.py

Resume-safe: already-translated cards are skipped on re-run.
"""

import json, time, os, sys, re

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Installing deep-translator...")
    os.system(f"{sys.executable} -m pip install deep-translator")
    from deep_translator import GoogleTranslator

# ── CONFIG ────────────────────────────────────────────────────────────
INPUT_FILE  = "cards.json"
OUTPUT_FILE = "cards.json"
BACKUP_FILE = "cards_jp_backup.json"
DELAY       = 0.3   # seconds between API calls — free tier is generous

# ── HELPERS ───────────────────────────────────────────────────────────

# Tag translation map — common JP OCG tags to English
TAG_MAP = {
    "#0期生":          "#Gen0",
    "#1期生":          "#Gen1",
    "#2期生":          "#Gen2",
    "#3期生":          "#Gen3",
    "#4期生":          "#Gen4",
    "#5期生":          "#Gen5",
    "#6期生":          "#Gen6",
    "#秘密結社holoX":  "#holoX",
    "#ID1期生":        "#IDGen1",
    "#ID2期生":        "#IDGen2",
    "#ID3期生":        "#IDGen3",
    "#JP":             "#JP",
    "#EN":             "#EN",
    "#ID":             "#ID",
    "#歌":             "#Song",
    "#ケモミミ":       "#AnimalEars",
    "#トリ":           "#Bird",
    "#絵":             "#Art",
    "#お酒":           "#Alcohol",
    "#ハーフエルフ":   "#HalfElf",
    "#Myth":           "#Myth",
    "#Promise":        "#Promise",
    "#Bird":           "#Bird",
    "#Painting":       "#Painting",
}

def is_japanese(text):
    """Return True if text contains Japanese characters."""
    if not text:
        return False
    for ch in text:
        if '\u3000' <= ch <= '\u9fff' or '\uff00' <= ch <= '\uffef':
            return True
    return False

translator = GoogleTranslator(source='ja', target='en')

def translate(text):
    """Translate Japanese text to English. Returns original if not Japanese."""
    if not text or not is_japanese(text):
        return text
    try:
        result = translator.translate(text)
        time.sleep(DELAY)
        return result or text
    except Exception as e:
        print(f"    ⚠ Translation error: {e}")
        time.sleep(2)
        return text  # keep original on error

def translate_tag(tag):
    """Translate a hashtag using the map, fall back to Google Translate."""
    if tag in TAG_MAP:
        return TAG_MAP[tag]
    if not is_japanese(tag):
        return tag
    # Strip # prefix, translate, re-add
    inner = tag.lstrip('#')
    translated = translate(inner)
    # Capitalise and remove spaces for clean hashtag
    clean = ''.join(w.capitalize() for w in translated.split())
    return f"#{clean}"

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: {INPUT_FILE} not found.")
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        cards = json.load(f)

    # Backup
    if not os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
        print(f"✓ Backed up original to {BACKUP_FILE}")

    total = len(cards)
    print(f"Translating {total} cards...\n")

    for i, card in enumerate(cards):
        needs_work = (
            is_japanese(card.get('name', '')) or
            any(is_japanese(v) for v in (card.get('abilities') or {}).values()) or
            any(is_japanese(t) for t in (card.get('tags') or []))
        )
        if not needs_work:
            continue

        print(f"  [{card['id']:>4}] {card['card_number']:<16} {card.get('name','')[:25]}")

        # Translate name
        if is_japanese(card.get('name', '')):
            card['name'] = translate(card['name'])
            print(f"         name → {card['name']}")

        # Translate abilities
        if card.get('abilities'):
            for key, val in card['abilities'].items():
                if is_japanese(val):
                    card['abilities'][key] = translate(val)
                    print(f"         {key} → {card['abilities'][key][:60]}...")

        # Translate tags
        if card.get('tags'):
            card['tags'] = [translate_tag(t) for t in card['tags']]

        # Save checkpoint every 50 cards
        if (i + 1) % 50 == 0:
            _save(cards, OUTPUT_FILE)
            print(f"\n  → Checkpoint saved ({i+1}/{total})\n")

    _save(cards, OUTPUT_FILE)
    print(f"\n✓ Done! Saved to {OUTPUT_FILE}")

def _save(cards, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
