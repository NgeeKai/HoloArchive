#!/usr/bin/env python3
"""
Holoarchive Card Translator
============================
Translates Japanese text in cards.json to English.

Card NAMES use a hardcoded lookup table of official hololive member
names — so ときのそら → "Tokino Sora" not "Time's Sky".

Ability TEXT uses Google Translate (free, no API key).

Usage:
    pip install deep-translator
    python translate_cards.py

Resume-safe: skips already-translated cards on re-run.
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
DELAY       = 0.3   # seconds between Google Translate calls

# ── OFFICIAL MEMBER NAME TABLE ────────────────────────────────────────
# JP name → Official English name
# Always use this before falling back to Google Translate
MEMBER_NAMES = {
    # ── hololive JP — 0期生 ──────────────────────────────────────
    "ときのそら":           "Tokino Sora",
    "ロボ子さん":           "Roboco",
    "さくらみこ":           "Sakura Miko",
    "星街すいせい":         "Hoshimachi Suisei",
    "AZKi":                 "AZKi",
    # ── hololive JP — 1期生 ──────────────────────────────────────
    "夜空メル":             "Yozora Mel",
    "アキ・ローゼンタール": "Aki Rosenthal",
    "赤井はあと":           "Akai Haato",
    "白上フブキ":           "Shirakami Fubuki",
    "夏色まつり":           "Natsuiro Matsuri",
    # ── hololive JP — 2期生 ──────────────────────────────────────
    "湊あくあ":             "Minato Aqua",
    "紫咲シオン":           "Murasaki Shion",
    "百鬼あやめ":           "Nakiri Ayame",
    "癒月ちょこ":           "Yuzuki Choco",
    "大空スバル":           "Oozora Subaru",
    # ── hololive JP — GAMERS ─────────────────────────────────────
    "大神ミオ":             "Ookami Mio",
    "猫又おかゆ":           "Nekomata Okayu",
    "戌神ころね":           "Inugami Korone",
    # ── hololive JP — 3期生 ──────────────────────────────────────
    "兎田ぺこら":           "Usada Pekora",
    "不知火フレア":         "Shiranui Flare",
    "白銀ノエル":           "Shirogane Noel",
    "宝鐘マリン":           "Houshou Marine",
    # ── hololive JP — 4期生 ──────────────────────────────────────
    "天音かなた":           "Amane Kanata",
    "桐生ここ":             "Kiryu Coco",
    "角巻わため":           "Tsunomaki Watame",
    "常闇トワ":             "Tokoyami Towa",
    "姫森ルーナ":           "Himemori Luna",
    # ── hololive JP — 5期生 ──────────────────────────────────────
    "雪花ラミィ":           "Yukihana Lamy",
    "桃鈴ねね":             "Momosuzu Nene",
    "獅白ぼたん":           "Shishiro Botan",
    "尾丸ポルカ":           "Omaru Polka",
    # ── hololive JP — 6期生 / holoX ─────────────────────────────
    "ラプラス・ダークネス": "La+ Darknesss",
    "鷹嶺ルイ":             "Takane Lui",
    "博衣こより":           "Hakui Koyori",
    "沙花叉クロヱ":         "Sakamata Chloe",
    "風真いろは":           "Kazama Iroha",
    # ── hololive DEV_IS — ReGLOSS ───────────────────────────────
    "火威青":               "Hiodoshi Ao",
    "音乃瀬奏":             "Otonose Kanade",
    "一条莉々華":           "Ichijou Ririka",
    "儒烏風亭らでん":       "Juufuutei Raden",
    "轟はじめ":             "Todoroki Hajime",
    # ── hololive DEV_IS — FLOW GLOW ─────────────────────────────
    "響咲リオナ":           "Isaki Riona",
    "小金井ニコ":           "Koganei Niko",
    "水宮枢":               "Mizumiya Su",
    "鈴宮千早":             "Rindo Chihaya",
    "綺々羅々ヴィヴィ":     "Kikirara Vivi",
    # ── hololive EN — Myth ───────────────────────────────────────
    "モリ・カリオペ":       "Mori Calliope",
    "小鳥遊キアラ":         "Takanashi Kiara",
    "一伊那尓栖":           "Ninomae Ina'nis",
    "がうる・ぐら":         "Gawr Gura",
    "ワトソン・アメリア":   "Watson Amelia",
    # ── hololive EN — Council / Promise ─────────────────────────
    "七詩ムメイ":           "Nanashi Mumei",
    "七詩むめい":           "Nanashi Mumei",
    "セレス・ファウナ":     "Ceres Fauna",
    "オーロ・クロニー":     "Ouro Kronii",
    "ベールズ・ゾエタ":     "Hakos Baelz",
    "IRyS":                 "IRyS",
    # ── hololive EN — Advent ─────────────────────────────────────
    "シオリ・ノベラ":       "Shiori Novella",
    "古石ビジュ":           "Koseki Bijou",
    "コセキ・ビジュ":       "Koseki Bijou",
    "ネリッサ・レイヴンクロフト": "Nerissa Ravencroft",
    "フワワ・アビスガード": "Fuwawa Abyssgard",
    "モコ・アビスガード":   "Mococo Abyssgard",
    "モココ・アビスガード": "Mococo Abyssgard",
    # ── hololive EN — Justice ────────────────────────────────────
    "エリザベス・ローズ・ブラッドフレイム": "Elizabeth Rose Bloodflame",
    "ジジ・ムリン":         "Gigi Murin",      # official: ジジ・ムリン not ジジ・マグニ
    "セシリア・イマーグリーン": "Cecilia Immergreen",
    "ラオーラ・パンテーラ": "Raora Panthera",
    # ── hololive ID — Gen 1 ──────────────────────────────────────
    "アユンダ・リス":       "Ayunda Risu",
    "ムーナ・ホシノヴァ":   "Moona Hoshinova",
    "アイラニ・イオフィフティーン": "Iofi Airani",
    # ── hololive ID — Gen 2 ──────────────────────────────────────
    "クレイジー・オリー":   "Kureiji Ollie",
    "アーニャ・メルフィッサ": "Anya Melfissa",
    "パヴォリア・レイネ":   "Pavolia Reine",
    # ── hololive ID — Gen 3 ──────────────────────────────────────
    "ベスティア・ゼータ":   "Vestia Zeta",
    "カエラ・コヴァルスキア": "Kaela Kovalskia",
    "こぼ・かなえる":       "Kobo Kanaeru",
    # ── holoAN announcers ────────────────────────────────────────
    "春先のどか":           "Harusaki Nodoka",
    "出雲みちる":           "Izuki Michiru",
    "花園さやか":           "Hanazono Sayaka",
    "風城ゆき":             "Kazeshiro Yuki",
    # ── Staff / recurring support cards ─────────────────────────
    "マネちゃん":           "Manager-chan",
    # ── Mascots & items ──────────────────────────────────────────
    "うぱお":               "Upao",
    "石の斧":               "Stone Axe",
    "サブパソコン":         "Sub PC",
    "スゴイパソコン":       "Super PC",
    "ホロリスの輪":         "Hololis Circle",
    # ── Units ────────────────────────────────────────────────────
    "SorAZ":                "SorAZ",
}

# Build a "contains" map for partial name matches
# e.g. "ときのそら Birthday" → "Tokino Sora Birthday"
def lookup_name(jp_name):
    """Look up official EN name. Handles exact matches and suffix variants."""
    if not jp_name:
        return jp_name
    # Exact match first
    if jp_name in MEMBER_NAMES:
        return MEMBER_NAMES[jp_name]
    # Try partial — e.g. "ときのそら Birthday" or "ときのそら（水着）"
    for jp, en in MEMBER_NAMES.items():
        if jp_name.startswith(jp) and len(jp) > 3:
            suffix = jp_name[len(jp):].strip()
            if suffix:
                # Translate suffix if it's Japanese, keep if it's already EN
                if is_japanese(suffix):
                    try:
                        suffix = translator.translate(suffix)
                        time.sleep(DELAY)
                    except Exception:
                        pass
                return f"{en} {suffix}".strip()
    return None  # not found — fall back to Google Translate


# ── TAG TRANSLATION MAP ───────────────────────────────────────────────
TAG_MAP = {
    "#0期生":         "#Gen0",
    "#1期生":         "#Gen1",
    "#2期生":         "#Gen2",
    "#3期生":         "#Gen3",
    "#4期生":         "#Gen4",
    "#5期生":         "#Gen5",
    "#6期生":         "#Gen6",
    "#秘密結社holoX": "#holoX",
    "#ID1期生":       "#IDGen1",
    "#ID2期生":       "#IDGen2",
    "#ID3期生":       "#IDGen3",
    "#JP":            "#JP",
    "#EN":            "#EN",
    "#ID":            "#ID",
    "#歌":            "#Song",
    "#ケモミミ":      "#AnimalEars",
    "#トリ":          "#Bird",
    "#絵":            "#Art",
    "#お酒":          "#Alcohol",
    "#ハーフエルフ":  "#HalfElf",
    "#Myth":          "#Myth",
    "#Promise":       "#Promise",
    "#Bird":          "#Bird",
    "#Painting":      "#Painting",
    "#ゲーマーズ":    "#Gamers",
    "#GAMERS":        "#Gamers",
}

# ── HELPERS ───────────────────────────────────────────────────────────
def is_japanese(text):
    if not text:
        return False
    for ch in text:
        cp = ord(ch)
        if (0x3000 <= cp <= 0x9FFF or
            0xFF00 <= cp <= 0xFFEF or
            0x4E00 <= cp <= 0x9FFF):
            return True
    return False

translator = GoogleTranslator(source='ja', target='en')

def translate_text(text):
    """Translate Japanese text to English via Google Translate."""
    if not text or not is_japanese(text):
        return text
    try:
        result = translator.translate(text)
        time.sleep(DELAY)
        return result or text
    except Exception as e:
        print(f"    ⚠ Translation error: {e} — keeping original")
        time.sleep(2)
        return text

def translate_tag(tag):
    if tag in TAG_MAP:
        return TAG_MAP[tag]
    if not is_japanese(tag):
        return tag
    inner = tag.lstrip('#')
    translated = translate_text(inner)
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

        # ── Translate name ────────────────────────────────────────
        if is_japanese(card.get('name', '')):
            official = lookup_name(card['name'])
            if official:
                card['name'] = official
                print(f"         name → {card['name']} (official lookup)")
            else:
                # Fall back to Google Translate
                card['name'] = translate_text(card['name'])
                print(f"         name → {card['name']} (google translate)")

        # ── Translate abilities ───────────────────────────────────
        if card.get('abilities'):
            for key, val in card['abilities'].items():
                if is_japanese(val):
                    card['abilities'][key] = translate_text(val)

        # ── Translate tags ────────────────────────────────────────
        if card.get('tags'):
            card['tags'] = [translate_tag(t) for t in card['tags']]

        # Checkpoint every 50 cards
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
