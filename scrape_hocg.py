#!/usr/bin/env python3
"""
Holoarchive — hololive OCG Card Scraper  v2.0
==============================================
Scrapes card detail pages from hololive-official-cardgame.com and writes
a clean cards.json suitable for the Holoarchive site.

Usage:
    pip install requests beautifulsoup4
    python scrape_hocg.py

Resume-safe: add new IDs without re-scraping existing ones.
"""

import json, time, re, os, sys
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_URL    = "https://hololive-official-cardgame.com"
ID_START    = 1
ID_END      = 3000
MAX_MISSING = 50      # stop after this many consecutive empty pages
DELAY       = 0.8     # seconds between requests — be polite
OUTPUT_FILE = "cards.json"
RESUME      = True    # skip IDs already in output file

# Fields to compare when checking if an existing card has changed.
# Excludes 'name'/'abilities' (translator handles those) and image_url (not critical).
CHANGE_FIELDS = [
    "card_number", "set_code", "product_set_code", "product_set_codes",
    "set_name", "card_type", "rarity", "color", "hp", "life",
    "bloom_level", "baton_pass", "tags", "illustrator", "is_parallel",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HoloArchive-Scraper/2.0; "
        "unofficial fan database; "
        "https://holoarchiveocg.com)"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

# ── LOOKUP TABLES ─────────────────────────────────────────────────────────────

# JP field label → English key (all variants seen on the real JP site)
JP_FIELD_MAP = {
    "カード名":            "Card Name",
    "カードタイプ":        "Card Type",
    "収録商品":            "Card Set",      # primary on real JP site
    "カードセット":        "Card Set",
    "カードナンバー":      "Card Number",   # primary on real JP site
    "カード番号":          "Card Number",
    "色":                  "Color",
    "HP":                  "HP",
    "LIFE":                "Life",     # Oshi cards use all-caps on JP site
    "ライフ":              "Life",
    "レアリティ":          "Rarity",
    "Bloomレベル":         "Bloom Level",   # primary on real JP site
    "ブルームレベル":      "Bloom Level",
    "バトンタッチ":        "Baton Pass",    # primary on real JP site
    "バトンパス":          "Baton Pass",
    "タグ":                "Tag",
    "イラストレーター名":  "Illustrator",   # primary on real JP site
    "イラストレーター":    "Illustrator",
    "イラスト":            "Illustrator",
}

# Cheer card type normalisation (JP has two words for the same type)
JP_CARD_TYPE_MAP = {
    "チア":   "Cheer",
    "エール": "Cheer",
}

# Color icon filename → color name
COLOR_ICON_MAP = {
    "type_white.png":     "white",
    "type_green.png":     "green",
    "type_red.png":       "red",
    "type_blue.png":      "blue",
    "type_purple.png":    "purple",
    "type_yellow.png":    "yellow",
    "type_colorless.png": "colorless",
}

# JP color text fallback
JP_COLOR_TEXT = {
    "白": "white", "緑": "green", "赤": "red",
    "青": "blue",  "紫": "purple", "黄": "yellow",
}

# Bloom level → normalised English
BLOOM_VALUE_MAP = {
    "デビュー": "Debut", "Debut":  "Debut",
    "1st":      "1st",  "１st":   "1st",
    "2nd":      "2nd",  "２nd":   "2nd",
    "3rd":      "3rd",  "３rd":   "3rd",
    "スポット": "Spot",  "Spot":   "Spot",
}

# JP set name → English set name
JP_SET_NAME_MAP = {
    'スタートデッキ「ときのそら＆AZKi」':           'Start Deck – Tokino Sora & AZKi',
    'ブースターパック「ブルーミングレディアンス」':   'Booster Pack – Blooming Radiance',
    'スタートエールセット':                          'Start Cheer Set',
    'バースデーデッキ2024':                          'Birthday Deck 2024',
    'バースデーセット2024':                          'Birthday Deck 2024',
    'ブースターパック「クインテットスペクトラム」':   'Booster Pack – Quintet Spectrum',
    'スタートデッキ 赤 百鬼あやめ':                  'Start Deck – Red Nakiri Ayame',
    'スタートデッキ 青 猫又おかゆ':                  'Start Deck – Blue Nekomata Okayu',
    'スタートデッキ 紫 癒月ちょこ':                  'Start Deck – Purple Yuzuki Choco',
    'スタートデッキ 白 轟はじめ':                    'Start Deck – White Todoroki',
    'スタートデッキ 緑 風真いろは':                  'Start Deck – Green Kazama Iroha',
    'スタートデッキ 黄 不知火フレア':                'Start Deck – Yellow Shiranui Flare',
    'ブースターパック「エリートスパーク」':           'Booster Pack – Elite Spark',
    'ブースターパック「キュリアスユニバース」':       'Booster Pack – Curious Universe',
    'スタートデッキ 白 天音かなた':                  'Start Deck – White Amane Kanata',
    'スタートデッキ 赤 宝鐘マリン':                  'Start Deck – Red Houshou Marine',
    'ブースターパック「エンチャントレガリア」':       'Booster Pack – Enchant Regalia',
    'スタートデッキ FLOW GLOW 推し 輪堂千速':        'Start Deck – Rindo Chihaya',
    'スタートデッキ FLOW GLOW 推し 虎金妃笑虎':      'Start Deck – Koganei Niko',
    'ブースターパック「アヤカシヴァーミリオン」':     'Booster Pack – Ayakashi Vermillion',
    'スタートデッキ 推し Advent':                    'Start Deck – Oshi Advent',
    'スタートデッキ 推し Justice':                   'Start Deck – Oshi Justice',
    'ブースターパック「ディーヴァフィーバー」':       'Booster Pack – Diva Fever',
    'PRカード':                                      'Promo Cards',
    # ── Promo specific sources ──────────────────────────────────────────
    '月例大会パック Vol.1':                          'Monthly Tournament Pack Vol.1',
    '月例大会パック Vol.2':                          'Monthly Tournament Pack Vol.2',
    '月例大会パック Vol.3':                          'Monthly Tournament Pack Vol.3',
    '月例大会パック Vol.4':                          'Monthly Tournament Pack Vol.4',
    '月例大会パック Vol.5':                          'Monthly Tournament Pack Vol.5',
    '月例大会パック Vol.6':                          'Monthly Tournament Pack Vol.6',
    '月刊ブシロード2024年11月号':                    'Monthly Bushiroad Nov 2024',
    '月刊ブシロード2025年1月号':                     'Monthly Bushiroad Jan 2025',
    '月刊ブシロード2025年3月号':                     'Monthly Bushiroad Mar 2025',
    '月刊ブシロード2025年5月号':                     'Monthly Bushiroad May 2025',
    '月刊ブシロード2025年7月号':                     'Monthly Bushiroad Jul 2025',
    '月刊ブシロード2025年9月号':                     'Monthly Bushiroad Sep 2025',
    '月刊ブシロード2025年11月号':                    'Monthly Bushiroad Nov 2025',
    'エントリーカップ「ブルーミングレディアンス」':  'Entry Cup – Blooming Radiance',
    'エントリーカップ「クインテットスペクトラム」':  'Entry Cup – Quintet Spectrum',
    'エントリーカップ「エリートスパーク」':          'Entry Cup – Elite Spark',
    'エントリーカップ「キュリアスユニバース」':      'Entry Cup – Curious Universe',
    'エントリーカップ「エンチャントレガリア」':      'Entry Cup – Enchant Regalia',
    'エントリーカップ「アヤカシヴァーミリオン」':    'Entry Cup – Ayakashi Vermillion',
    'エントリーカップ「ディーヴァフィーバー」':      'Entry Cup – Diva Fever',
}

# English set name → set code
SET_NAME_TO_CODE = {
    'Start Deck – Tokino Sora & AZKi':   'hSD01',
    'Booster Pack – Blooming Radiance':   'hBP01',
    'Start Cheer Set':                    'hYS01',
    'Birthday Deck 2024':                 'hBD24',
    'Booster Pack – Quintet Spectrum':    'hBP02',
    'Start Deck – Red Nakiri Ayame':      'hSD02',
    'Start Deck – Blue Nekomata Okayu':   'hSD03',
    'Start Deck – Purple Yuzuki Choco':   'hSD04',
    'Start Deck – White Todoroki':        'hSD05',
    'Start Deck – Green Kazama Iroha':    'hSD06',
    'Start Deck – Yellow Shiranui Flare': 'hSD07',
    'Booster Pack – Elite Spark':         'hBP03',
    'Booster Pack – Curious Universe':    'hBP04',
    'Start Deck – White Amane Kanata':    'hSD08',
    'Start Deck – Red Houshou Marine':    'hSD09',
    'Booster Pack – Enchant Regalia':     'hBP05',
    'Start Deck – Rindo Chihaya':         'hSD10',
    'Start Deck – Koganei Niko':          'hSD11',
    'Booster Pack – Ayakashi Vermillion': 'hBP06',
    'Start Deck – Oshi Advent':           'hSD12',
    'Start Deck – Oshi Justice':          'hSD13',
    'Booster Pack – Diva Fever':          'hBP07',
    'Promo Cards':                        'hPR',
}

# Ability heading text → ability key
ABILITY_HEADINGS = {
    "キーワード":   "keyword",
    "アーツ":       "arts",
    "推しスキル":   "oshi_skill",
    "SP推しスキル": "sp_oshi_skill",
    "SPおしスキル": "sp_oshi_skill",
    "SPお仕スキル": "sp_oshi_skill",
    "ブルーム効果": "bloom_effect",
    "コラボ効果":   "collab_effect",
    "ギフト":       "gift",
    "エクストラ":   "extra",
    "能力テキスト": "ability_text",
    "テキスト":     "ability_text",
    "Keyword":       "keyword",
    "Arts":          "arts",
    "Oshi Skill":    "oshi_skill",
    "SP Oshi Skill": "sp_oshi_skill",
    "Bloom Effect":  "bloom_effect",
    "Collab Effect": "collab_effect",
    "Gift":          "gift",
    "Extra":         "extra",
    "Ability Text":  "ability_text",
}

# Keyword type icons embedded in ability text
KEYWORD_TYPE_ICONS = {
    "collabEF": "Collab Effect",
    "bloomEF":  "Bloom Effect",
    "giftEF":   "Gift",
}
KEYWORD_TYPE_ALT = {
    "コラボエフェクト":   "Collab Effect",
    "ブルームエフェクト": "Bloom Effect",
    "ギフト":             "Gift",
    "Collab Effect":      "Collab Effect",
    "Bloom Effect":       "Bloom Effect",
    "Gift":               "Gift",
}

PARALLEL_RARITIES = {'OUR', 'UR', 'SEC', 'SR', 'S', 'SY', 'HR'}

SKIP_HEADINGS = {
    "card list", "cardlist", "カードリスト", "カード一覧",
    "cARDLIST", "cARD LIST",
}

# ── PARSERS ───────────────────────────────────────────────────────────────────

def color_from_img(img):
    if not img:
        return None
    src = img.get("src", "")
    for filename, color in COLOR_ICON_MAP.items():
        if filename in src:
            return color
    return None


def parse_fields(soup):
    """Parse all dt/dd pairs → normalised English-key dict."""
    result = {}
    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        raw_key = dt.get_text(strip=True)
        key = JP_FIELD_MAP.get(raw_key, raw_key)

        img_dd = dd.find("img", src=lambda s: s and "texticon/type_" in s)
        img_dt = dt.find("img", src=lambda s: s and "texticon/type_" in s)
        dd_text = dd.get_text(" ", strip=True)

        if img_dd:
            result[key] = color_from_img(img_dd)
        elif img_dt:
            result[key] = color_from_img(img_dt)
        elif key == "Color" and dd_text in JP_COLOR_TEXT:
            result[key] = JP_COLOR_TEXT[dd_text]
        else:
            if not dd_text:
                alts = [i.get("alt", "") for i in dd.find_all("img") if i.get("alt", "").strip()]
                result[key] = " ".join(alts) if alts else ""
            else:
                result[key] = dd_text

    return result


def parse_tags(soup):
    """Extract #hashtag links."""
    return [
        a.get_text(strip=True)
        for a in soup.select("dd a[href*='keyword'], dd a[href*='cardsearch']")
        if a.get_text(strip=True).startswith("#")
    ]


def extract_ability_text(el):
    """Get text from an ability element, prepending [Keyword Type] if present."""
    keyword_type = None
    for img in el.find_all("img"):
        src, alt = img.get("src", ""), img.get("alt", "")
        for icon_key, en_type in KEYWORD_TYPE_ICONS.items():
            if icon_key in src:
                keyword_type = en_type
                break
        if not keyword_type and alt in KEYWORD_TYPE_ALT:
            keyword_type = KEYWORD_TYPE_ALT[alt]
        if keyword_type:
            break

    text = re.sub(r'[\s\u3000]+', ' ', el.get_text(' ', strip=True)).strip()
    return f"[{keyword_type}] {text}" if (keyword_type and text) else text


def parse_abilities(soup):
    """
    Scan the page for ability label → text pairs.
    Real JP site uses bare <p> tags outside <dl> for abilities.
    """
    abilities = {}
    elements = soup.find_all(["p", "h2", "h3", "h4", "dt", "dd"])
    i = 0
    while i < len(elements):
        label = elements[i].get_text(strip=True)
        if label in ABILITY_HEADINGS:
            key = ABILITY_HEADINGS[label]
            if i + 1 < len(elements):
                text = extract_ability_text(elements[i + 1])
                if text and text not in ABILITY_HEADINGS:
                    abilities[key] = (abilities[key] + "\n" + text) if key in abilities else text
                    i += 2
                    continue
        i += 1
    return abilities


def parse_card(html, card_id, url):
    """Parse one card detail page. Returns a dict or None if not a card."""
    soup = BeautifulSoup(html, "html.parser")

    # ── Image ──────────────────────────────────────────────────────────
    img_tag = soup.find("img", src=lambda s: s and "/cardlist/" in s)
    if not img_tag:
        return None

    image_url = img_tag.get("src", "")
    if not image_url.startswith("http"):
        image_url = urljoin(BASE_URL, image_url)

    # ── Name ───────────────────────────────────────────────────────────
    name = img_tag.get("title", "").strip()
    if not name:
        for h1 in soup.find_all("h1"):
            text = h1.get_text(strip=True)
            if text and text.lower() not in SKIP_HEADINGS and len(text) > 1:
                name = text
                break
    if not name:
        return None

    # ── Fields ─────────────────────────────────────────────────────────
    fields = parse_fields(soup)
    tags   = parse_tags(soup)

    # ── Card number ────────────────────────────────────────────────────
    card_number = fields.get("Card Number") or ""
    if not card_number:
        m = re.search(r'h[A-Za-z]+\d*-\d+', soup.get_text())
        card_number = m.group(0) if m else None
    if not card_number:
        return None

    # ── Set code (from card number) ────────────────────────────────────
    m = re.match(r'^(h[A-Za-z]+\d*)', card_number)
    set_code = m.group(1) if m else None

    # ── Rarity (from image URL — most reliable) ────────────────────────
    m = re.search(r'_([A-Z]+)\.png$', image_url)
    rarity = m.group(1) if m else (fields.get("Rarity") or None)

    # ── Card type ──────────────────────────────────────────────────────
    card_type_raw = fields.get("Card Type") or ""
    card_type = JP_CARD_TYPE_MAP.get(card_type_raw, card_type_raw) or None

    # ── Color ──────────────────────────────────────────────────────────
    color = fields.get("Color") or None
    if not color:
        for img in soup.find_all("img", src=lambda s: s and "texticon/type_" in s):
            c = color_from_img(img)
            if c:
                color = c
                break
    if not color:
        color = "colorless"

    # ── HP / Life ──────────────────────────────────────────────────────
    hp_raw   = str(fields.get("HP") or "").strip()
    hp       = int(hp_raw) if hp_raw.isdigit() else None

    life_raw = str(fields.get("Life") or "").strip()
    life     = int(life_raw) if life_raw.isdigit() else None

    # ── Bloom level ────────────────────────────────────────────────────
    bloom_raw = (fields.get("Bloom Level") or "").replace("１","1").replace("２","2").replace("３","3")
    bloom = BLOOM_VALUE_MAP.get(bloom_raw) or (bloom_raw if bloom_raw else None)

    # ── Baton pass ─────────────────────────────────────────────────────
    baton_pass = (fields.get("Baton Pass") or "").strip() or None

    # ── Set name & product set codes ───────────────────────────────────
    # 収録商品 field can contain multiple products space-separated, e.g.:
    # "ブースターパック「ブルーミングレディアンス」 スタートデッキ「ときのそら＆AZKi」"
    # This means the card genuinely appears in ALL those sets.
    raw_set_name = (fields.get("Card Set") or "").strip()

    # Strip event eligibility prefixes: 【使用可能カード】エントリーカップ「xxx」
    cleaned_set_name = re.sub(r'【[^】]*】\s*', '', raw_set_name).strip()

    # Parse ALL product codes from the field (longest match first to avoid partial matches)
    def parse_all_set_codes_from_raw(raw):
        """Extract all set codes from a raw 収録商品 string."""
        cleaned = re.sub(r'【[^】]*】\s*', '', raw).strip()
        found_codes = []
        remaining = cleaned
        for jp_key in sorted(JP_SET_NAME_MAP.keys(), key=len, reverse=True):
            if jp_key in remaining:
                en_name = JP_SET_NAME_MAP[jp_key]
                code = SET_NAME_TO_CODE.get(en_name)
                if code and code not in found_codes:
                    found_codes.append(code)
                remaining = remaining.replace(jp_key, '')
        return found_codes

    if set_code == 'hBD24':
        # Birthday Deck — always hBD24 regardless of set_name
        product_set_codes = ['hBD24']
        set_name = 'Birthday Deck 2024'
    elif cleaned_set_name:
        product_set_codes = parse_all_set_codes_from_raw(cleaned_set_name)
        if not product_set_codes:
            # Direct EN lookup (already translated field)
            code = SET_NAME_TO_CODE.get(cleaned_set_name)
            if code:
                product_set_codes = [code]
            elif rarity == 'P':
                product_set_codes = ['hPR']
            else:
                product_set_codes = [set_code] if set_code else []
        # set_name = primary set (first one found)
        code_to_en = {v: k for k, v in SET_NAME_TO_CODE.items()}
        set_name = code_to_en.get(product_set_codes[0]) if product_set_codes else cleaned_set_name
    else:
        if rarity == 'P':
            product_set_codes = ['hPR']
        else:
            product_set_codes = [set_code] if set_code else []
        set_name = None

    # Single product_set_code = primary (first) set for backwards compatibility
    product_set_code = product_set_codes[0] if product_set_codes else set_code

    # ── Illustrator (never translated) ────────────────────────────────
    illustrator = (fields.get("Illustrator") or "").strip() or None
    if not illustrator:
        m = re.search(
            r'(?:Illustrator|イラストレーター名|イラストレーター|イラスト)[:\uff1a\s]+([^\n\r\t]+)',
            soup.get_text()
        )
        if m:
            raw = m.group(1).strip()
            illustrator = re.split(r'[\n\r]|(?=h[A-Z]\w+-\d+)', raw)[0].strip() or None

    # ── Abilities ──────────────────────────────────────────────────────
    abilities = parse_abilities(soup)

    # Fallback: pick up any abilities that ended up in dt/dd instead of bare <p>
    ABILITY_FALLBACK_KEYS = {
        "keyword": ["キーワード", "Keyword"],
        "arts":    ["アーツ", "Arts"],
        "oshi_skill":    ["推しスキル", "Oshi Skill"],
        "sp_oshi_skill": ["SP推しスキル", "SPおしスキル", "SPお仕スキル", "SP Oshi Skill"],
        "bloom_effect":  ["ブルーム効果", "Bloom Effect"],
        "collab_effect": ["コラボ効果", "Collab Effect"],
        "gift":          ["ギフト", "Gift"],
        "extra":         ["エクストラ", "Extra"],
        "ability_text":  ["能力テキスト", "テキスト", "Ability Text"],
    }
    for ability_key, jp_labels in ABILITY_FALLBACK_KEYS.items():
        if ability_key not in abilities:
            for label in jp_labels:
                val = (fields.get(label) or "").strip()
                if val:
                    abilities[ability_key] = val
                    break

    # ── Parallel ───────────────────────────────────────────────────────
    is_parallel = rarity in PARALLEL_RARITIES if rarity else False

    return {
        "id":                card_id,
        "card_number":       card_number,
        "set_code":          set_code,
        "product_set_code":  product_set_code,   # primary set (backwards compat)
        "product_set_codes": product_set_codes,  # all sets this card appears in
        "set_name":          set_name,
        "name":             name,
        "card_type":        card_type,
        "rarity":           rarity,
        "color":            color,
        "hp":               hp,
        "life":             life,
        "bloom_level":      bloom,
        "baton_pass":       baton_pass,
        "tags":             tags,
        "abilities":        abilities,
        "illustrator":      illustrator,
        "is_parallel":      is_parallel,
        "image_url":        image_url,
        "source_url":       url,
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────

def save(cards, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(cards.values(), key=lambda c: c["id"]), f, ensure_ascii=False, indent=2)


def card_has_changed(old, new):
    """Return list of changed fields between old and new card dicts."""
    changed = []
    for field in CHANGE_FIELDS:
        oval, nval = old.get(field), new.get(field)
        # Normalize lists for comparison
        if isinstance(oval, list): oval = sorted(str(x) for x in oval)
        if isinstance(nval, list): nval = sorted(str(x) for x in nval)
        if oval != nval:
            changed.append(f"{field}: {oval!r} → {nval!r}")
    return changed


def main():
    print("Holoarchive Card Scraper v2.1")
    print(f"  Target : {BASE_URL}")
    print(f"  Range  : ID {ID_START} → {ID_END}")
    print(f"  Output : {OUTPUT_FILE}")
    print(f"  Delay  : {DELAY}s")
    print("─" * 50)

    existing = {}
    if RESUME and os.path.exists(OUTPUT_FILE):
        try:
            content = open(OUTPUT_FILE, encoding="utf-8").read().strip()
            if content:
                existing = {c["id"]: c for c in json.loads(content)}
                print(f"Loaded {len(existing)} existing cards — will check for updates\n")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: {OUTPUT_FILE} corrupt ({e}) — starting fresh\n")

    cards = dict(existing)
    session = requests.Session()
    session.headers.update(HEADERS)

    consecutive_missing = 0
    new_cards = updated = skipped = errors = 0

    for card_id in range(ID_START, ID_END + 1):

        url = f"{BASE_URL}/cardlist/?id={card_id}"

        try:
            resp = session.get(url, timeout=15)

            if resp.status_code == 404:
                consecutive_missing += 1
                if consecutive_missing >= MAX_MISSING:
                    print(f"\nStopped — {MAX_MISSING} consecutive empty IDs.")
                    break
                continue

            if resp.status_code != 200:
                print(f"  [{card_id}] HTTP {resp.status_code}")
                errors += 1
                consecutive_missing += 1
                continue

            card = parse_card(resp.text, card_id, url)

            if card is None:
                consecutive_missing += 1
                if consecutive_missing % 10 == 0:
                    print(f"  [{card_id}] Not a card (consecutive: {consecutive_missing})")
                if consecutive_missing >= MAX_MISSING:
                    print(f"\nStopped — {MAX_MISSING} consecutive empty IDs.")
                    break
                time.sleep(DELAY)
                continue

            consecutive_missing = 0

            if card_id not in existing:
                # Brand new card
                cards[card_id] = card
                new_cards += 1
                print(
                    f"  [{card_id:>4}] NEW  {card['card_number']:<16} "
                    f"{(card['name'] or '')[:28]:<28}  "
                    f"{(card['rarity'] or '?'):<5}  "
                    f"{card['product_set_code'] or card['set_code'] or '?'}"
                )
            else:
                # Existing card — check for changes in key fields
                changes = card_has_changed(existing[card_id], card)
                if changes:
                    # Preserve already-translated name and abilities
                    card['name']      = existing[card_id].get('name') or card['name']
                    card['abilities'] = existing[card_id].get('abilities') or card['abilities']
                    cards[card_id] = card
                    updated += 1
                    print(f"  [{card_id:>4}] UPD  {card['card_number']:<16} {(card['name'] or '')[:28]}")
                    for change in changes:
                        print(f"          ↳ {change}")
                else:
                    skipped += 1

            if (new_cards + updated) % 50 == 0 and (new_cards + updated) > 0:
                save(cards, OUTPUT_FILE)
                print(f"  → Checkpoint ({len(cards)} total, {new_cards} new, {updated} updated)")

        except requests.exceptions.Timeout:
            print(f"  [{card_id}] Timeout")
            time.sleep(3)
            errors += 1
            consecutive_missing += 1

        except requests.exceptions.RequestException as e:
            print(f"  [{card_id}] Error: {e}")
            time.sleep(2)
            errors += 1
            consecutive_missing += 1

        time.sleep(DELAY)

    save(cards, OUTPUT_FILE)
    print("\n" + "─" * 50)
    print(f"New      : {new_cards}")
    print(f"Updated  : {updated}")
    print(f"Skipped  : {skipped}  (unchanged)")
    print(f"Errors   : {errors}")
    print(f"Total    : {len(cards)}")


if __name__ == "__main__":
    main()
