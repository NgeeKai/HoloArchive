#!/usr/bin/env python3
"""
check_new_sets.py — Auto-detects new sets on the official JP site and
patches them into scrape_hocg.py and index.html automatically.

Run order:
    python check_new_sets.py   ← detects + patches
    python scrape_hocg.py      ← scrapes new cards
    python translate_cards.py  ← translates
    python generate_og.py      ← updates sitemap/og

All triggered automatically by the GitHub Actions workflow.
"""

import re, sys, json, time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing: pip install requests beautifulsoup4")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HoloArchive-Scraper/2.0; https://holoarchiveocg.com)",
    "Accept-Language": "ja,en;q=0.9",
}

# ── ALL KNOWN SETS ─────────────────────────────────────────────────────────────
# JP name → English name  (for scraper JP_SET_NAME_MAP)
KNOWN_JP_TO_EN = {
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
}

# Set code → English name  (for index.html SET_NAMES)
KNOWN_CODE_TO_EN = {
    'hSD01': 'Start Deck – Tokino Sora & AZKi',
    'hBP01': 'Booster Pack – Blooming Radiance',
    'hYS01': 'Start Cheer Set',
    'hBD24': 'Birthday Deck 2024',
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
    'hBP05': 'Booster Pack – Enchant Regalia',
    'hSD10': 'Start Deck – Rindo Chihaya',
    'hSD11': 'Start Deck – Koganei Niko',
    'hBP06': 'Booster Pack – Ayakashi Vermillion',
    'hSD12': 'Start Deck – Oshi Advent',
    'hSD13': 'Start Deck – Oshi Justice',
    'hBP07': 'Booster Pack – Diva Fever',
    'hPR':   'Promo Cards',
    'hY01':  'White Cheer',
    'hY02':  'Green Cheer',
    'hY03':  'Red Cheer',
    'hY04':  'Blue Cheer',
    'hY05':  'Purple Cheer',
    'hY06':  'Yellow Cheer',
}

# ── EMOJI ICON per set type ────────────────────────────────────────────────────
def guess_icon(code, en_name):
    """Pick an emoji icon for a new set based on its code prefix."""
    if code.startswith('hBP'):
        # Cycle through booster pack icons
        bp_icons = ['🌸','⭐','⚡','🌌','🎭','🔥','💎','🌙','🌊','🎆','🎇','✨','🌟']
        num = int(re.search(r'\d+', code).group(0)) if re.search(r'\d+', code) else 1
        return bp_icons[(num - 1) % len(bp_icons)]
    elif code.startswith('hSD'):
        sd_icons = ['🎵','⚔️','🐱','💜','⬜','🌿','💛','🎤','🌙','🌊','🦊','🌺','🎪','🎭','🎨']
        num = int(re.search(r'\d+', code).group(0)) if re.search(r'\d+', code) else 1
        return sd_icons[(num - 1) % len(sd_icons)]
    elif code.startswith('hBD'):
        return '🎂'
    elif code.startswith('hYS'):
        return '🎀'
    elif code.startswith('hPR') or code == 'hPR':
        return '🎁'
    elif code.startswith('hY'):
        color_icons = {'hY01':'⬜','hY02':'💚','hY03':'❤️','hY04':'💙','hY05':'💜','hY06':'💛'}
        return color_icons.get(code, '🎴')
    return '📦'


def guess_en_name(jp_name, code):
    """
    Auto-generate a best-effort English name from the JP set name.
    Always reviewed in the GitHub Actions log before going live.
    """
    name = jp_name.strip()

    # Strip Japanese brackets
    name = re.sub(r'[「」]', ' ', name).strip()

    # Direct prefix replacements
    replacements = [
        ('ブースターパック',      'Booster Pack –'),
        ('スタートデッキ',        'Start Deck –'),
        ('スタートエールセット',  'Start Cheer Set'),
        ('PRカード',              'Promo Cards'),
        ('バースデーデッキ',      'Birthday Deck'),
        ('バースデーセット',      'Birthday Set'),
        ('月例大会パック',        'Monthly Tournament Pack'),
        ('月刊ブシロード',        'Monthly Bushiroad'),
        ('エントリーカップ',      'Entry Cup –'),
        ('ブルームカップ',        'Bloom Cup –'),
        ('チャンピオンシップ',    'Championship –'),
    ]
    for jp_prefix, en_prefix in replacements:
        if jp_name.startswith(jp_prefix):
            suffix = name[len(jp_prefix):].strip().strip('–').strip()
            name = f"{en_prefix} {suffix}".strip().strip('–').strip()
            break

    # Code-based fallback hints
    if code.startswith('hBP') and 'Booster Pack' not in name:
        name = f'Booster Pack – {name}'
    elif code.startswith('hSD') and 'Start Deck' not in name:
        name = f'Start Deck – {name}'

    return name.strip(' –')


# ── FETCH SETS FROM JP SITE ────────────────────────────────────────────────────

def fetch_sets_from_jp_site():
    """
    Fetch the card list page and extract all expansion codes + JP names.
    Returns: list of (code, jp_name)
    """
    url = "https://hololive-official-cardgame.com/cardlist/"
    print(f"Fetching {url} ...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"✗ Failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    seen = {}

    # Method 1: select dropdown with expansion values
    for select in soup.find_all('select'):
        for option in select.find_all('option'):
            val  = option.get('value', '').strip()
            text = ' '.join(option.get_text().split())
            if re.match(r'^h[A-Za-z]+\d*$', val) and text and val not in seen:
                seen[val] = text

    # Method 2: links with ?expansion= or cardsearch?expansion=
    for a in soup.find_all('a', href=True):
        m = re.search(r'[?&]expansion=([a-zA-Z0-9]+)', a['href'])
        if m:
            val  = m.group(1)
            text = ' '.join(a.get_text().split())
            if re.match(r'^h[A-Za-z]+\d*$', val) and val not in seen and text:
                seen[val] = text

    return list(seen.items())


# ── PATCH SCRAPER ──────────────────────────────────────────────────────────────

def patch_scraper(new_sets):
    """Add new sets to scrape_hocg.py JP_SET_NAME_MAP and SET_NAME_TO_CODE."""
    try:
        with open('scrape_hocg.py', 'r', encoding='utf-8') as f:
            src = f.read()
    except FileNotFoundError:
        print("  ⚠ scrape_hocg.py not found")
        return

    changed = False

    for code, jp_name, en_name in new_sets:
        # Add to JP_SET_NAME_MAP
        anchor = "    'PRカード':                                      'Promo Cards',"
        new_jp  = f"\n    '{jp_name}':  '{en_name}',  # AUTO-ADDED"
        if anchor in src and jp_name not in src:
            src = src.replace(anchor, anchor + new_jp)
            print(f"  ✓ scraper JP_SET_NAME_MAP: {jp_name} → {en_name}")
            changed = True

        # Add to SET_NAME_TO_CODE
        anchor2 = "    'Promo Cards':                        'hPR',"
        new_sn  = f"\n    '{en_name}':  '{code}',  # AUTO-ADDED"
        if anchor2 in src and en_name not in src:
            src = src.replace(anchor2, anchor2 + new_sn)
            print(f"  ✓ scraper SET_NAME_TO_CODE: {en_name} → {code}")
            changed = True

    if changed:
        with open('scrape_hocg.py', 'w', encoding='utf-8') as f:
            f.write(src)


# ── PATCH INDEX.HTML ───────────────────────────────────────────────────────────

def patch_index(new_sets):
    """
    Add new sets to index.html:
    - SET_NAMES constant
    - SET_NAME_TO_CODE in getProductSetCode
    - SET_ICONS constant
    - SET_ORDER_IDX in buildSetIndex and applyFilters sort
    """
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        print("  ⚠ index.html not found")
        return

    changed = False

    for code, jp_name, en_name in new_sets:
        icon = guess_icon(code, en_name)

        # ── 1. SET_NAMES ────────────────────────────────────────────────
        # Insert before the closing }; of SET_NAMES
        sn_anchor = "  hPR:   'Promo Cards',"
        sn_entry  = f"\n  {code}: '{en_name}',  // AUTO-ADDED"
        if sn_anchor in html and f"  {code}:" not in html:
            html = html.replace(sn_anchor, sn_anchor + sn_entry, 1)
            print(f"  ✓ index.html SET_NAMES: {code} → {en_name}")
            changed = True

        # ── 2. SET_NAME_TO_CODE (in getProductSetCode) ──────────────────
        snc_anchor = "  'Promo Cards':                        'hPR',"
        snc_entry  = f"\n  '{en_name}':  '{code}',  // AUTO-ADDED"
        if snc_anchor in html and f"'{en_name}'" not in html:
            html = html.replace(snc_anchor, snc_anchor + snc_entry, 1)
            print(f"  ✓ index.html SET_NAME_TO_CODE: {en_name} → {code}")
            changed = True

        # ── 3. SET_ICONS ────────────────────────────────────────────────
        icon_anchor = "  hPR:'🎁',"
        icon_entry  = f"\n  {code}:'{icon}',"
        if icon_anchor in html and f"  {code}:'" not in html:
            html = html.replace(icon_anchor, icon_anchor + icon_entry, 1)
            print(f"  ✓ index.html SET_ICONS: {code} → {icon}")
            changed = True

        # ── 4. SET_ORDER_IDX in buildSetIndex ───────────────────────────
        # Insert new code before 'hPR' in the order array
        # Placement logic: BP after last BP, SD after last SD, else before hPR
        order_anchor = "'hPR'"

        if code.startswith('hBP'):
            # Find last hBPxx in array and insert after it
            last_bp = None
            for m in re.finditer(r"'hBP\d+'", html):
                last_bp = m
            if last_bp:
                insert_pos = last_bp.end()
                html = html[:insert_pos] + f",'{code}'" + html[insert_pos:]
                print(f"  ✓ index.html SET_ORDER_IDX: {code} added after last BP")
                changed = True

        elif code.startswith('hSD'):
            last_sd = None
            for m in re.finditer(r"'hSD\d+'", html):
                last_sd = m
            if last_sd:
                insert_pos = last_sd.end()
                html = html[:insert_pos] + f",'{code}'" + html[insert_pos:]
                print(f"  ✓ index.html SET_ORDER_IDX: {code} added after last SD")
                changed = True

        else:
            # Insert before hPR
            if f"'{code}'" not in html:
                html = html.replace(
                    f"'{order_anchor}'",
                    f"'{code}',{order_anchor}",
                    1
                )
                print(f"  ✓ index.html SET_ORDER_IDX: {code} added before hPR")
                changed = True

    if changed:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Holoarchive — New Set Detector")
    print("=" * 60)

    site_sets = fetch_sets_from_jp_site()

    if not site_sets:
        print("\n⚠ Could not reach JP site — skipping set detection")
        print("  Scraper will proceed with existing mappings")
        sys.exit(0)

    print(f"\nFound {len(site_sets)} set(s) on JP site")

    # Find genuinely new sets
    new_sets = []
    for code, jp_name in site_sets:
        jp_name = ' '.join(jp_name.split())  # normalise whitespace
        if jp_name not in KNOWN_JP_TO_EN and code not in KNOWN_CODE_TO_EN:
            en_name = guess_en_name(jp_name, code)
            new_sets.append((code, jp_name, en_name))

    if not new_sets:
        print("\n✓ No new sets — everything is up to date")
        sys.exit(0)

    print(f"\n🆕 {len(new_sets)} NEW set(s) detected:\n")
    for code, jp_name, en_name in new_sets:
        print(f"  [{code}]  JP: {jp_name}")
        print(f"           EN: {en_name}  (auto-guessed — verify!)")

    print("\nPatching files...")
    patch_scraper(new_sets)
    patch_index(new_sets)

    print("\n" + "=" * 60)
    print("⚠  AUTO-ADDED SETS — PLEASE REVIEW EN NAMES:")
    for code, jp_name, en_name in new_sets:
        print(f"  {code}: '{en_name}'")
    print("\nEdit scrape_hocg.py and index.html to correct if needed.")
    print("=" * 60)

    sys.exit(0)  # Always exit 0 — never fail the workflow on new sets


if __name__ == '__main__':
    main()
