#!/usr/bin/env python3
"""
Hololive OCG JP Card Scraper
Scrapes https://hololive-official-cardgame.com card detail pages (?id=N)
and outputs a clean cards.json file.

Usage:
    pip install requests beautifulsoup4
    python scrape_hocg.py

Options (edit CONFIG below):
    BASE_URL     - JP or EN site
    ID_START     - First card ID to try
    ID_END       - Last card ID to try (set high, gaps are handled)
    MAX_MISSING  - Stop after this many consecutive 404/empty pages
    DELAY        - Seconds between requests (be polite!)
    OUTPUT_FILE  - Where to write the JSON
    RESUME       - Set True to resume from existing output file
"""

import json
import time
import re
import os
import sys
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

BASE_URL    = "https://hololive-official-cardgame.com"   # JP site
# BASE_URL  = "https://en.hololive-official-cardgame.com"  # EN site (uncomment to use)

ID_START    = 1       # Start scanning from this card ID
ID_END      = 3000    # Scan up to this ID (gaps are skipped automatically)
MAX_MISSING = 50      # Stop if 50 consecutive IDs return nothing (end of database)
DELAY       = 0.8     # Seconds between requests — please be polite to the server
OUTPUT_FILE = "cards.json"
RESUME      = True    # Skip IDs already in output file

# ─── HELPERS ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HoloCardDB-Scraper/1.0; "
        "personal fan database project; "
        "contact: your-email@example.com)"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

COLOR_MAP = {
    "type_white.png":   "white",
    "type_green.png":   "green",
    "type_red.png":     "red",
    "type_blue.png":    "blue",
    "type_purple.png":  "purple",
    "type_yellow.png":  "yellow",
    "type_colorless.png": "colorless",
}

def get_color_from_img(img_tag):
    """Extract color name from the color icon <img> src."""
    if not img_tag:
        return None
    src = img_tag.get("src", "")
    for filename, color in COLOR_MAP.items():
        if filename in src:
            return color
    return None

def build_image_url(card_number, base_url=BASE_URL):
    """
    Construct the official card image URL from a card number like 'hBP01-007'.
    JP site:  /wp-content/images/cardlist/{SET}/{SET}-{NUM}_{RARITY}.png
    EN site:  /wp-content/images/cardlist/{SET}/EN_{SET}-{NUM}_{RARITY}.png
    
    NOTE: We don't know rarity at URL-build time, so we store the image URL
    directly from the <img> tag on the page instead.
    """
    pass  # We extract the img src directly from the page — more reliable

def parse_dl(soup):
    """Parse a <dl> definition list into a normalised dict of {english_key: value}.

    The JP site uses Japanese field labels; the EN site uses English ones.
    We normalise all JP labels to their English equivalents so the rest of the
    parser doesn't need to handle both languages.
    """
    JP_TO_EN = {
        # Card identity
        "カード名":           "Name",
        "カードタイプ":       "Card Type",
        "カードセット":       "Card Set",
        "収録商品":           "Card Set",      # variant seen on real JP site
        "カード番号":         "Card Number",
        "カードナンバー":     "Card Number",   # variant seen on real JP site
        # Stats
        "色":                 "Color",
        "HP":                 "HP",
        "ライフ":             "LIFE",
        "レアリティ":         "Rarity",
        "ブルームレベル":     "Bloom Level",
        "Bloomレベル":        "Bloom Level",   # variant seen on real JP site
        "バトンパス":         "Baton Pass",
        "バトンタッチ":       "Baton Pass",    # variant seen on real JP site
        # Skills / abilities
        "タグ":               "Tag",
        "キーワード":         "Keyword",
        "アーツ":             "Arts",
        "エクストラ":         "Extra",
        "推しスキル":         "Oshi Skill",
        "SPおしスキル":       "SP Oshi Skill",
        "SPお仕スキル":       "SP Oshi Skill",  # typo variant seen in the wild
        "SP推しスキル":       "SP Oshi Skill",  # correct JP form on real site
        "ブルーム効果":       "Bloom Effect",
        "コラボ効果":         "Collab Effect",
        "ギフト":             "Gift",
        "イラストレーター":   "Illustrator",
        "イラストレーター名": "Illustrator",   # variant seen on real JP site
        "イラスト":           "Illustrator",   # short form variant
        # Ability text (Cheer / Support cards)
        "能力テキスト":       "Ability Text",
        "テキスト":           "Ability Text",
        # Buzz holomem variant
        "バズホロメン":       "Buzz holomem",
    }

    result = {}

    # Scan ALL dt/dd pairs in the whole document.
    # On the real site, stats (HP, Color etc.) are inside a <dl>,
    # but abilities (Keyword, Arts, Oshi Skill etc.) sit OUTSIDE the <dl>
    # as bare <dt>/<dd> elements. We need both.
    terms = soup.find_all("dt")
    defs  = soup.find_all("dd")
    for dt, dd in zip(terms, defs):
        raw_key = dt.get_text(strip=True)
        # Normalise JP → EN; fall back to the original key if not in the map
        key = JP_TO_EN.get(raw_key, raw_key)

        # Color field: check img in dd, img in dt, or JP text value
        img_in_dd = dd.find("img", src=lambda s: s and "texticon/type_" in s)
        img_in_dt = dt.find("img", src=lambda s: s and "texticon/type_" in s)
        dd_text = dd.get_text(" ", strip=True)

        JP_COLOR_TEXT = {
            "白": "white", "緑": "green", "赤": "red",
            "青": "blue",  "紫": "purple","黄": "yellow",
        }

        if img_in_dd:
            result[key] = get_color_from_img(img_in_dd)
        elif img_in_dt:
            result[key] = get_color_from_img(img_in_dt)
        elif key == "Color" and dd_text in JP_COLOR_TEXT:
            result[key] = JP_COLOR_TEXT[dd_text]
        else:
            # For Baton Pass, content is often only <img alt="◇"> — get_text() returns empty
            # Fall back to reading the alt attribute directly
            if not dd_text:
                imgs = dd.find_all("img")
                alt_texts = [i.get("alt", "") for i in imgs if i.get("alt", "").strip()]
                result[key] = " ".join(alt_texts) if alt_texts else ""
            else:
                result[key] = dd_text
    return result

def parse_tags(soup):
    """Extract hashtag links like #EN, #Promise, #Bird etc."""
    tags = []
    for a in soup.select("dd a[href*='keyword']"):
        text = a.get_text(strip=True)
        if text.startswith("#"):
            tags.append(text)
    return tags

# Labels that mark the start of an ability block.
# Both JP and EN variants are included.
ABILITY_HEADINGS = {
    "キーワード":   "keyword",
    "アーツ":       "arts",
    "エクストラ":   "extra",
    "能力テキスト": "ability_text",
    "テキスト":     "ability_text",
    "推しスキル":   "oshi_skill",
    "SPお仕スキル": "sp_oshi_skill",
    "SPおしスキル": "sp_oshi_skill",
    "SP推しスキル": "sp_oshi_skill",  # correct JP form on real site
    "ブルーム効果": "bloom_effect",
    "コラボ効果":   "collab_effect",
    "ギフト":       "gift",
    # EN site labels
    "Keyword":       "keyword",
    "Arts":          "arts",
    "Extra":         "extra",
    "Ability Text":  "ability_text",
    "Oshi Skill":    "oshi_skill",
    "SP Oshi Skill": "sp_oshi_skill",
    "Bloom Effect":  "bloom_effect",
    "Collab Effect": "collab_effect",
    "Gift":          "gift",
}

def parse_abilities_from_page(soup):
    """
    Scan the whole document for ability labels followed by ability text.

    The real site renders abilities as:
        <p>キーワード</p>          ← label (short, no colon)
        <p>[icon] ability text</p> ← value

    These are NOT inside <dt>/<dd> pairs — they sit as bare paragraphs
    after the main <dl>. We scan all block elements for known label strings,
    then take the next sibling as the ability text.
    """

    # Icons that indicate keyword type — prepended to the ability text
    # All 3 confirmed from real card data:
    # collabEF = Collab Effect (triggers at collab position)
    # bloomEF  = Bloom Effect (triggers when holomem blooms)
    # giftEF   = Gift (mascot support card abilities)
    KEYWORD_TYPE_ICONS = {
        "collabEF":   "Collab Effect",
        "bloomEF":    "Bloom Effect",
        "giftEF":     "Gift",
    }
    KEYWORD_TYPE_ALT = {
        # JP alt text
        "コラボエフェクト":   "Collab Effect",
        "ブルームエフェクト": "Bloom Effect",
        "ギフト":             "Gift",
        # EN alt text
        "Collab Effect":  "Collab Effect",
        "Bloom Effect":   "Bloom Effect",
        "Gift":           "Gift",
    }

    def extract_ability_text(el):
        """Get text from element, prepending keyword type if an icon is present."""
        keyword_type = None
        for img in el.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            for icon_key, en_type in KEYWORD_TYPE_ICONS.items():
                if icon_key in src:
                    keyword_type = en_type
                    break
            if not keyword_type and alt in KEYWORD_TYPE_ALT:
                keyword_type = KEYWORD_TYPE_ALT[alt]
            if keyword_type:
                break
        text = re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip()
        if keyword_type and text:
            return f"[{keyword_type}] {text}"
        return text

    abilities = {}
    elements = soup.find_all(["p", "h2", "h3", "h4", "dt", "dd"])

    i = 0
    while i < len(elements):
        el = elements[i]
        label = el.get_text(strip=True)

        if label in ABILITY_HEADINGS:
            key = ABILITY_HEADINGS[label]
            if i + 1 < len(elements):
                next_el = elements[i + 1]
                next_text = extract_ability_text(next_el)
                if next_text and next_text not in ABILITY_HEADINGS:
                    if key in abilities:
                        abilities[key] += "\n" + next_text
                    else:
                        abilities[key] = next_text
                    i += 2
                    continue
        i += 1

    return abilities

def parse_abilities(soup, fields):
    """
    Parse all ability/skill text blocks.
    Returns a dict with keys: keyword, arts, oshi_skill, sp_oshi_skill, extra
    """
    abilities = {}

    # The ability sections appear as <dt>/<dd> pairs in the dl
    # but also as standalone paragraphs after the dl — depends on card type.
    # We parse them all from the dl dict already, just clean them up.

    for label in ["Keyword", "Arts", "Extra", "Oshi Skill", "SP Oshi Skill"]:
        val = fields.get(label)
        if val:
            abilities[label.lower().replace(" ", "_")] = val

    return abilities

def parse_card_page(html, card_id, url):
    """
    Parse a single card detail page and return a dict, or None if not a card.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Locate the card art image — it always has /cardlist/ in its src.
    # Try common CSS selectors first, then fall back to a whole-document scan.
    card_img = soup.select_one(".cardDetail img, .card-image img, #cardList img")
    if not card_img:
        card_img = soup.find("img", src=lambda s: s and "/cardlist/" in s)

    if not card_img:
        return None

    image_url = card_img.get("src", "")
    if not image_url.startswith("http"):
        image_url = urljoin(BASE_URL, image_url)

    # Card name — use the image title attribute first (most reliable, works on
    # both JP and EN sites regardless of h1 language).
    # e.g. <img src="..." title="Nanashi Mumei">
    card_name = card_img.get("title", "").strip()

    # Fallback: find the h1 that comes *after* the card image in the DOM.
    # The page has two h1s: first is the section heading ("CARD LIST" / "カードリスト"),
    # second is the actual card name. We skip any h1 whose text matches known
    # section headings in either language.
    SKIP_HEADINGS = {
        "card list", "cardlist", "カードリスト", "カード一覧",
    }
    if not card_name:
        for h1 in soup.find_all("h1"):
            text = h1.get_text(strip=True)
            if text and text.lower() not in SKIP_HEADINGS and len(text) > 1:
                card_name = text
                break

    if not card_name:
        return None

    # Parse the definition list
    fields = parse_dl(soup)

    # Tags (#EN, #Promise etc.)
    tags = parse_tags(soup)

    # Card number -- always present; also buried in page text as fallback
    # parse_dl() has already normalised JP keys to EN, so just use "Card Number"
    card_number = fields.get("Card Number")
    if not card_number:
        match = re.search(r'h[A-Za-z]+\d+-\d+', soup.get_text())
        card_number = match.group(0) if match else None

    if not card_number:
        return None

    # Derive set code from card number (e.g. hBP01-007 -> hBP01)
    set_code = re.match(r'^(h[A-Za-z]+\d*)', card_number)
    set_code = set_code.group(1) if set_code else None

    # Rarity -- prefer image URL (most reliable) then fall back to normalised field
    rarity_match = re.search(r'_([A-Z]+)\.png$', image_url)
    rarity = rarity_match.group(1) if rarity_match else fields.get("Rarity")

    # All field keys are now in English thanks to parse_dl() normalisation
    card_type_raw = fields.get("Card Type")

    # Translate JP card type VALUES (not keys) to English
    JP_CARD_TYPE_VALUES = {
        "推しホロメン":               "推しホロメン",   # keep as-is, site translates
        "ホロメン":                   "ホロメン",
        "Buzzホロメン":               "Buzzホロメン",
        "チア":                       "Cheer",         # JP Cheer value → English
        "エール":                     "Cheer",         # JP Cheer value variant
        "サポート・アイテム":         "サポート・アイテム",
        "サポート・アイテム・LIMITED":"サポート・アイテム・LIMITED",
        "サポート・イベント":         "サポート・イベント",
        "サポート・イベント・LIMITED":"サポート・イベント・LIMITED",
        "サポート・ツール":           "サポート・ツール",
        "サポート・マスコット":       "サポート・マスコット",
        "サポート・ファン":           "サポート・ファン",
        "サポート・スタッフ":         "サポート・スタッフ",
        "サポート・スタッフ・LIMITED":"サポート・スタッフ・LIMITED",
    }
    card_type = JP_CARD_TYPE_VALUES.get(card_type_raw, card_type_raw)
    color      = fields.get("Color")

    # Fallback: if color still missing, scan entire page for color icon imgs
    if not color:
        for img in soup.find_all("img", src=lambda s: s and "texticon/type_" in s):
            c = get_color_from_img(img)
            if c:
                color = c
                break

    hp_raw = fields.get("HP")
    hp = int(hp_raw) if hp_raw and str(hp_raw).isdigit() else None

    life_raw = fields.get("LIFE")
    life = int(life_raw) if life_raw and str(life_raw).isdigit() else None

    bloom_raw  = fields.get("Bloom Level")
    # Translate JP bloom level values
    BLOOM_VALUES = {
        "デビュー": "Debut", "Debut": "Debut",
        "1st": "1st", "１st": "1st",
        "2nd": "2nd", "２nd": "2nd",
        "3rd": "3rd", "３rd": "3rd",
        "スポット": "Spot", "Spot": "Spot",
    }
    bloom = BLOOM_VALUES.get(bloom_raw, bloom_raw) if bloom_raw else None
    baton_pass = fields.get("Baton Pass")

    # Capture set_name and translate JP → English
    JP_SET_NAME_MAP = {
        'ブースターパック「ブルーミングレディアンス」':   'Booster Pack – Blooming Radiance',
        'ブースターパック「クインテットスペクトラム」':   'Booster Pack – Quintet Spectrum',
        'ブースターパック「エリートスパーク」':           'Booster Pack – Elite Spark',
        'ブースターパック「キュリアスユニバース」':       'Booster Pack – Curious Universe',
        'ブースターパック「アヤカシヴァーミリオン」':     'Booster Pack – Ayakashi Vermillion',
        'ブースターパック「ディーヴァフィーバー」':       'Booster Pack – Diva Fever',
        'ブースターパック「エンチャントレガリア」':       'Booster Pack – Enchant Regalia',
        'スタートデッキ「ときのそら＆AZKi」':            'Start Deck – Tokino Sora & AZKi',
        'スタートデッキ 赤 百鬼あやめ':                  'Start Deck – Red Nakiri Ayame',
        'スタートデッキ 青 猫又おかゆ':                  'Start Deck – Blue Nekomata Okayu',
        'スタートデッキ 紫 癒月ちょこ':                  'Start Deck – Purple Yuzuki Choco',
        'スタートデッキ 白 轟はじめ':                    'Start Deck – White Todoroki',
        'スタートデッキ 緑 風真いろは':                  'Start Deck – Green Kazama Iroha',
        'スタートデッキ 黄 不知火フレア':                'Start Deck – Yellow Shiranui Flare',
        'スタートデッキ 白 天音かなた':                  'Start Deck – White Amane Kanata',
        'スタートデッキ 赤 宝鐘マリン':                  'Start Deck – Red Houshou Marine',
        'スタートデッキ FLOW GLOW 推し 輪堂千速':        'Start Deck – Rindo Chihaya',
        'スタートデッキ FLOW GLOW 推し 虎金妃笑虎':      'Start Deck – Koganei Niko',
        'スタートデッキ 推し Advent':                    'Start Deck – Oshi Advent',
        'スタートデッキ 推し Justice':                   'Start Deck – Oshi Justice',
        'スタートエールセット':                          'Start Cheer Set',
        'PRカード':                                      'Promo Cards',
        '【hololive production OFFICIAL SHOP限定】hololive OFFICIAL CARD GAME 1st Anniversary Celebration Set':  '【hololive production OFFICIAL SHOP限定】hololive OFFICIAL CARD GAME 1st Anniversary Celebration Set',  # AUTO-ADDED — verify EN name
        '【イベント物販／hololive production OFFICIAL SHOP限定商品】オフィシャルホロカコレクション-PCセット-':  '【イベント物販／hololive production OFFICIAL SHOP限定商品】オフィシャルホロカコレクション-PCセット-',  # AUTO-ADDED — verify EN name
    }
    raw_set_name = fields.get("Card Set") or ""
    raw_set_name = raw_set_name.strip()
    set_name = JP_SET_NAME_MAP.get(raw_set_name) or (raw_set_name if raw_set_name else None)

    # Derive product_set_code from the actual product name
    # This is different from set_code (which comes from card number)
    # For reprints, set_code = original set, product_set_code = the set it was actually printed in
    SET_NAME_TO_CODE = {v: k for k, v in {
        'hSD01': 'Start Deck – Tokino Sora & AZKi',
        'hBP01': 'Booster Pack – Blooming Radiance',
        'hYS01': 'Start Cheer Set',
        'hBP02': 'Booster Pack – Quintet Spectrum',
        'hSD02': 'Start Deck – Red Nakiri Ayame',
        'hSD03': 'Start Deck – Blue Nekomata Okayu',
        'hSD04': 'Start Deck – Purple Yuzuki Choco',
        'hSD05': 'Start Deck – White Todoroki',
        'hSD06': 'Start Deck – Green Kazama Iroha',
        'hSD07': 'Start Deck – Yellow Shiranui Flare',
        'hBP03': 'Booster Pack – Elite Spark',
        'hBP04': 'Booster Pack – Curious Universe',
        'hSD08': 'Start Deck – White Amane Kanata',
        'hSD09': 'Start Deck – Red Houshou Marine',
        'hBP05': 'Booster Pack – Ayakashi Vermillion',
        'hSD10': 'Start Deck – Rindo Chihaya',
        'hSD11': 'Start Deck – Koganei Niko',
        'hBP06': 'Booster Pack – Diva Fever',
        'hSD12': 'Start Deck – Oshi Advent',
        'hSD13': 'Start Deck – Oshi Justice',
        'hBP07': 'Booster Pack – Enchant Regalia',
        'hPR':   'Promo Cards',
        'hCS01': '【hololive production OFFICIAL SHOP限定】hololive OFFICIAL CARD GAME 1st Anniversary Celebration Set',  # AUTO-ADDED — verify EN name
        'hPC01': '【イベント物販／hololive production OFFICIAL SHOP限定商品】オフィシャルホロカコレクション-PCセット-',  # AUTO-ADDED — verify EN name
    }.items()}
    product_set_code = SET_NAME_TO_CODE.get(set_name) or set_code

    # Illustrator -- field first, then scan raw page text (covers both JP/EN format)
    illustrator_raw = fields.get("Illustrator") or ""
    if not illustrator_raw:
        page_text = soup.get_text()
        # Match EN "Illustrator: Name" and JP variants:
        # "イラストレーター名：Name", "イラストレーター：Name", "イラスト：Name"
        illus_match = re.search(
            r'(?:Illustrator|イラストレーター名|イラストレーター|イラスト)[:\uff1a\s]+([^\n\r\t]+)',
            page_text
        )
        if illus_match:
            illustrator_raw = illus_match.group(1).strip()
            # Trim anything after a card number pattern or newline
            illustrator_raw = re.split(r'[\n\r]|(?=h[A-Z]\w+-\d+)', illustrator_raw)[0].strip()

    # Abilities — scan the whole page for ability label/text pairs.
    # The real site puts abilities as bare <p> tags OUTSIDE the <dl>,
    # so parse_dl() never sees them. parse_abilities_from_page() handles this.
    abilities = parse_abilities_from_page(soup)

    # Fallback: also check fields dict for any abilities that DID end up in dt/dd
    # (covers edge cases and older page formats)
    fallback_keys = {
        # EN keys
        "Keyword": "keyword", "Arts": "arts", "Extra": "extra",
        "Ability Text": "ability_text",
        "Oshi Skill": "oshi_skill",
        "SP Oshi Skill": "sp_oshi_skill",
        "Bloom Effect": "bloom_effect",
        "Collab Effect": "collab_effect",
        "Gift": "gift",
        # JP keys — all known variants
        "キーワード": "keyword",
        "アーツ": "arts",
        "エクストラ": "extra",
        "能力テキスト": "ability_text",
        "テキスト": "ability_text",
        "推しスキル": "oshi_skill",
        "SPお仕スキル": "sp_oshi_skill",   # typo variant
        "SPおしスキル": "sp_oshi_skill",   # hiragana variant
        "SP推しスキル": "sp_oshi_skill",   # correct form on real site
        "ブルーム効果": "bloom_effect",
        "コラボ効果": "collab_effect",
        "ギフト": "gift",
    }
    for label, key in fallback_keys.items():
        if key not in abilities:  # don't overwrite paragraph-parsed values
            val = fields.get(label)
            if val and val.strip():
                abilities[key] = val.strip()

    # Parallel prints are identified by rarity
    PARALLEL_RARITIES = {'OUR', 'UR', 'SEC', 'SR', 'S', 'SY', 'HR'}
    is_parallel = rarity in PARALLEL_RARITIES if rarity else False

    # Multicolor cards have null color — label as 'colorless' for filtering
    if not color:
        color = 'colorless'

    card = {
        "id": card_id,
        "card_number": card_number,
        "set_code": set_code,              # derived from card number (e.g. hBP01 from hBP01-092)
        "product_set_code": product_set_code,  # actual product printed in (may differ for reprints)
        "set_name": set_name,
        "name": card_name,
        "card_type": card_type,
        "rarity": rarity,
        "color": color,
        "hp": hp,
        "life": life,
        "bloom_level": bloom,
        "baton_pass": baton_pass,
        "tags": tags,
        "abilities": abilities,
        "illustrator": illustrator_raw.strip() if illustrator_raw else None,
        "is_parallel": is_parallel,
        "image_url": image_url,
        "source_url": url,
    }

    return card

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Hololive OCG Scraper")
    print(f"Target: {BASE_URL}")
    print(f"Range:  ID {ID_START} → {ID_END}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Delay:  {DELAY}s per request")
    print("─" * 50)

    # Load existing data if resuming
    existing = {}
    if RESUME and os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                print(f"Warning: {OUTPUT_FILE} is empty — starting fresh")
            else:
                existing_list = json.loads(content)
                existing = {c["id"]: c for c in existing_list}
                print(f"Resuming: {len(existing)} cards already scraped")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: {OUTPUT_FILE} is corrupted ({e}) — starting fresh")
            existing = {}

    cards = dict(existing)
    session = requests.Session()
    session.headers.update(HEADERS)

    consecutive_missing = 0
    scraped = 0
    skipped = 0
    errors  = 0

    for card_id in range(ID_START, ID_END + 1):
        # Skip already-scraped IDs
        if card_id in cards:
            skipped += 1
            continue

        url = f"{BASE_URL}/cardlist/?id={card_id}"

        try:
            resp = session.get(url, timeout=15)

            if resp.status_code == 404:
                consecutive_missing += 1
                if consecutive_missing >= MAX_MISSING:
                    print(f"\nNo cards found for {MAX_MISSING} consecutive IDs. Stopping.")
                    break
                continue

            if resp.status_code != 200:
                print(f"  [{card_id}] HTTP {resp.status_code} — skipping")
                errors += 1
                consecutive_missing += 1
                continue

            card = parse_card_page(resp.text, card_id, url)

            if card is None:
                # Not a card page (redirect to list page, or empty)
                consecutive_missing += 1
                if consecutive_missing % 10 == 0:
                    print(f"  [{card_id}] No card (consecutive missing: {consecutive_missing})")
                if consecutive_missing >= MAX_MISSING:
                    print(f"\nNo cards found for {MAX_MISSING} consecutive IDs. Stopping.")
                    break
                time.sleep(DELAY)
                continue

            consecutive_missing = 0
            cards[card_id] = card
            scraped += 1

            print(f"  [{card_id:>4}] ✓ {card['card_number']:<16} {card['name']:<30} "
                  f"{card.get('card_type','?'):<12} {card.get('rarity','?')}")

            # Save incrementally every 50 cards
            if scraped % 50 == 0:
                _save(cards, OUTPUT_FILE)
                print(f"  → Saved checkpoint ({len(cards)} total cards)")

        except requests.exceptions.Timeout:
            print(f"  [{card_id}] Timeout — retrying once...")
            time.sleep(3)
            errors += 1
            consecutive_missing += 1
            continue
        except requests.exceptions.RequestException as e:
            print(f"  [{card_id}] Request error: {e}")
            errors += 1
            consecutive_missing += 1
            time.sleep(2)
            continue

        time.sleep(DELAY)

    # Final save
    _save(cards, OUTPUT_FILE)

    print("\n" + "─" * 50)
    print(f"Done.")
    print(f"  Cards scraped this run : {scraped}")
    print(f"  Cards skipped (resume) : {skipped}")
    print(f"  Errors                 : {errors}")
    print(f"  Total cards in output  : {len(cards)}")
    print(f"  Output file            : {OUTPUT_FILE}")

def _save(cards, path):
    sorted_cards = sorted(cards.values(), key=lambda c: c["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted_cards, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
