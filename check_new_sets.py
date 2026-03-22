#!/usr/bin/env python3
"""
check_new_sets.py — Detects new sets on the official JP site and
auto-updates JP_SET_NAME_MAP in scrape_hocg.py and SET_NAMES in index.html.

Run before scraping to ensure new sets are mapped correctly:
    python check_new_sets.py
    python scrape_hocg.py
    python translate_cards.py
    python generate_og.py

Or included automatically in the GitHub Actions workflow.
"""

import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HoloCardDB-Scraper/1.0; "
        "personal fan database project)"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

JP_SITE = "https://hololive-official-cardgame.com/cardlist/"

# ── Known JP set name → EN name mapping ──────────────────────────────
# Any set NOT in this map will be flagged as new
KNOWN_JP_TO_EN = {
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
}

# ── Known set code → EN name for index.html SET_NAMES ────────────────
KNOWN_CODE_TO_EN = {
    'hBP01': 'Booster Pack – Blooming Radiance',
    'hBP02': 'Booster Pack – Quintet Spectrum',
    'hBP03': 'Booster Pack – Elite Spark',
    'hBP04': 'Booster Pack – Curious Universe',
    'hBP05': 'Booster Pack – Ayakashi Vermillion',
    'hBP06': 'Booster Pack – Diva Fever',
    'hBP07': 'Booster Pack – Enchant Regalia',
    'hSD01': 'Start Deck – Tokino Sora & AZKi',
    'hSD02': 'Start Deck – Red Nakiri Ayame',
    'hSD03': 'Start Deck – Blue Nekomata Okayu',
    'hSD04': 'Start Deck – Purple Yuzuki Choco',
    'hSD05': 'Start Deck – White Todoroki',
    'hSD06': 'Start Deck – Green Kazama Iroha',
    'hSD07': 'Start Deck – Yellow Shiranui Flare',
    'hSD08': 'Start Deck – White Amane Kanata',
    'hSD09': 'Start Deck – Red Houshou Marine',
    'hSD10': 'Start Deck – Rindo Chihaya',
    'hSD11': 'Start Deck – Koganei Niko',
    'hSD12': 'Start Deck – Oshi Advent',
    'hSD13': 'Start Deck – Oshi Justice',
    'hBD24': 'Birthday Set 2024',
    'hYS01': 'Start Cheer Set',
    'hPR':   'Promo Cards',
}

def guess_en_name(jp_name, set_code):
    """
    Attempt to auto-generate a readable English name from the JP name.
    This is a best-effort guess — should be reviewed manually.
    """
    name = jp_name

    # Strip Japanese brackets 「」
    name = re.sub(r'[「」]', ' ', name).strip()

    # Common prefix translations
    prefixes = [
        ('ブースターパック',     'Booster Pack –'),
        ('スタートデッキ',       'Start Deck –'),
        ('スタートエールセット', 'Start Cheer Set'),
        ('PRカード',             'Promo Cards'),
        ('バースデーセット',     'Birthday Set'),
        ('エントリーカップ',     'Entry Cup –'),
    ]
    for jp_prefix, en_prefix in prefixes:
        if name.startswith(jp_prefix):
            name = en_prefix + name[len(jp_prefix):].strip()
            break

    # Set code hint: if it's a BP, SD, PR etc use that
    if set_code.startswith('hBP') and 'Booster Pack' not in name:
        name = f'Booster Pack – {name}'
    elif set_code.startswith('hSD') and 'Start Deck' not in name:
        name = f'Start Deck – {name}'

    return name.strip(' –')


def fetch_sets_from_jp_site():
    """
    Fetch the JP cardlist page and extract all set codes + JP names
    from the 収録商品 select dropdown.
    Returns: list of (set_code, jp_name) tuples
    """
    print(f"Fetching {JP_SITE} ...")
    try:
        resp = requests.get(JP_SITE, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"✗ Failed to fetch JP site: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Find the select with expansion options
    sets = []
    for select in soup.find_all('select'):
        for option in select.find_all('option'):
            value = option.get('value', '')
            text = option.get_text(strip=True)
            # Set codes match h[A-Z]+\d* pattern
            if re.match(r'^h[A-Za-z]+\d*$', value) and text:
                sets.append((value, text))

    # Also check links with ?expansion= pattern
    for a in soup.find_all('a', href=True):
        m = re.search(r'expansion=([a-zA-Z0-9]+)', a['href'])
        if m:
            code = m.group(1)
            if re.match(r'^h[A-Za-z]+\d*$', code) and code not in [s[0] for s in sets]:
                text = a.get_text(strip=True)
                if text:
                    sets.append((code, text))

    return sets


def check_and_update():
    """
    Main function: fetch sets, find new ones, update files.
    """
    print("=" * 60)
    print("Checking for new sets on the official JP site...")
    print("=" * 60)

    site_sets = fetch_sets_from_jp_site()

    if not site_sets:
        print("Could not fetch set list — skipping update")
        return False

    print(f"\nFound {len(site_sets)} sets on JP site")

    # Find new sets not in our known maps
    new_sets = []
    for code, jp_name in site_sets:
        # Clean up JP name (remove surrounding whitespace/newlines)
        jp_name = ' '.join(jp_name.split())
        if jp_name not in KNOWN_JP_TO_EN and code not in KNOWN_CODE_TO_EN:
            guessed_en = guess_en_name(jp_name, code)
            new_sets.append((code, jp_name, guessed_en))

    if not new_sets:
        print("\n✓ No new sets found — everything is up to date")
        return False

    print(f"\n🆕 Found {len(new_sets)} NEW set(s):\n")
    for code, jp_name, guessed_en in new_sets:
        print(f"  {code}: {jp_name}")
        print(f"       → {guessed_en} (auto-guessed — please verify)")

    # ── Update scrape_hocg.py ─────────────────────────────────────────
    updated_scraper = False
    try:
        with open('scrape_hocg.py', 'r', encoding='utf-8') as f:
            scraper = f.read()

        for code, jp_name, guessed_en in new_sets:
            if jp_name not in scraper:
                # Add to JP_SET_NAME_MAP
                insert_after = "        'PRカード':                                      'Promo Cards',"
                new_entry = f"\n        '{jp_name}':  '{guessed_en}',  # AUTO-ADDED — verify EN name"
                scraper = scraper.replace(insert_after, insert_after + new_entry)
                print(f"\n  ✓ Added to scrape_hocg.py JP_SET_NAME_MAP: {jp_name}")
                updated_scraper = True

            if code not in scraper:
                # Add to SET_NAME_TO_CODE
                insert_after2 = "        'hPR':   'Promo Cards',"
                new_entry2 = f"\n        '{code}': '{guessed_en}',  # AUTO-ADDED — verify EN name"
                scraper = scraper.replace(insert_after2, insert_after2 + new_entry2)
                print(f"  ✓ Added {code} to SET_NAME_TO_CODE in scrape_hocg.py")

        if updated_scraper:
            with open('scrape_hocg.py', 'w', encoding='utf-8') as f:
                f.write(scraper)

    except FileNotFoundError:
        print("  ⚠ scrape_hocg.py not found — skipping")

    # ── Update index.html SET_NAMES ───────────────────────────────────
    updated_html = False
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()

        for code, jp_name, guessed_en in new_sets:
            if f"  {code}:" not in html:
                insert_after = "  hPR:   'Promo Cards',"
                new_entry = f"\n  {code}: '{guessed_en}',  // AUTO-ADDED — verify EN name"
                html = html.replace(insert_after, insert_after + new_entry)
                print(f"  ✓ Added {code} to SET_NAMES in index.html")
                updated_html = True

        if updated_html:
            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html)

    except FileNotFoundError:
        print("  ⚠ index.html not found — skipping")

    # ── Print summary for GitHub Actions log ─────────────────────────
    print("\n" + "=" * 60)
    print("NEW SETS DETECTED — PLEASE REVIEW EN NAMES:")
    for code, jp_name, guessed_en in new_sets:
        print(f"  {code}: '{guessed_en}'")
    print("\nThese have been auto-added with guessed English names.")
    print("Edit scrape_hocg.py and index.html to correct them if needed.")
    print("=" * 60)

    return True


if __name__ == '__main__':
    changed = check_and_update()
    sys.exit(0)  # Always exit 0 — don't fail the workflow on new set detection
