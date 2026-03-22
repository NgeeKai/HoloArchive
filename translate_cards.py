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

# ── MEMBER NAME REPLACEMENT IN ABILITY TEXT ───────────────────────────
# Applied BEFORE and AFTER Google Translate to ensure names are never mangled.
# Full JP names are safe to replace anywhere (long enough to be unambiguous).
# Short names only replaced inside 〈〉 brackets (where context is clear).

# Full official names: JP → EN romanization
FULL_NAME_MAP = {
    # 0期生
    "ときのそら":                 "Tokino Sora",
    "ロボ子さん":                 "Roboco",
    "さくらみこ":                 "Sakura Miko",
    "星街すいせい":               "Hoshimachi Suisei",
    # 1期生
    "夜空メル":                   "Yozora Mel",
    "アキ・ローゼンタール":       "Aki Rosenthal",
    "赤井はあと":                 "Akai Haato",
    "白上フブキ":                 "Shirakami Fubuki",
    "夏色まつり":                 "Natsuiro Matsuri",
    # 2期生
    "湊あくあ":                   "Minato Aqua",
    "紫咲シオン":                 "Murasaki Shion",
    "百鬼あやめ":                 "Nakiri Ayame",
    "癒月ちょこ":                 "Yuzuki Choco",
    "大空スバル":                 "Oozora Subaru",
    # GAMERS
    "大神ミオ":                   "Ookami Mio",
    "猫又おかゆ":                 "Nekomata Okayu",
    "戌神ころね":                 "Inugami Korone",
    # 3期生
    "兎田ぺこら":                 "Usada Pekora",
    "不知火フレア":               "Shiranui Flare",
    "白銀ノエル":                 "Shirogane Noel",
    "宝鐘マリン":                 "Houshou Marine",
    # 4期生
    "天音かなた":                 "Amane Kanata",
    "桐生ここ":                   "Kiryu Coco",
    "角巻わため":                 "Tsunomaki Watame",
    "常闇トワ":                   "Tokoyami Towa",
    "姫森ルーナ":                 "Himemori Luna",
    # 5期生
    "雪花ラミィ":                 "Yukihana Lamy",
    "桃鈴ねね":                   "Momosuzu Nene",
    "獅白ぼたん":                 "Shishiro Botan",
    "尾丸ポルカ":                 "Omaru Polka",
    # holoX
    "ラプラス・ダークネス":       "La+ Darknesss",
    "鷹嶺ルイ":                   "Takane Lui",
    "博衣こより":                 "Hakui Koyori",
    "沙花叉クロヱ":               "Sakamata Chloe",
    "風真いろは":                 "Kazama Iroha",
    # DEV_IS ReGLOSS
    "火威青":                     "Hiodoshi Ao",
    "音乃瀬奏":                   "Otonose Kanade",
    "一条莉々華":                 "Ichijou Ririka",
    "儒烏風亭らでん":             "Juufuutei Raden",
    "轟はじめ":                   "Todoroki Hajime",
    # DEV_IS FLOW GLOW
    "響咲リオナ":                 "Isaki Riona",
    "小金井ニコ":                 "Koganei Niko",
    "水宮枢":                     "Mizumiya Su",
    "鈴宮千早":                   "Rindo Chihaya",
    "綺々羅々ヴィヴィ":           "Kikirara Vivi",
    # EN Myth
    "モリ・カリオペ":             "Mori Calliope",
    "小鳥遊キアラ":               "Takanashi Kiara",
    "一伊那尓栖":                 "Ninomae Ina'nis",
    "がうる・ぐら":               "Gawr Gura",
    "ワトソン・アメリア":         "Watson Amelia",
    # EN Council/Promise
    "七詩ムメイ":                 "Nanashi Mumei",
    "七詩むめい":                 "Nanashi Mumei",
    "セレス・ファウナ":           "Ceres Fauna",
    "オーロ・クロニー":           "Ouro Kronii",
    "ベールズ・ゾエタ":           "Hakos Baelz",
    "IRyS":                       "IRyS",
    # EN Advent
    "シオリ・ノベラ":             "Shiori Novella",
    "古石ビジュ":                 "Koseki Bijou",
    "コセキ・ビジュ":             "Koseki Bijou",
    "ネリッサ・レイヴンクロフト": "Nerissa Ravencroft",
    "フワワ・アビスガード":       "Fuwawa Abyssgard",
    "モコ・アビスガード":         "Mococo Abyssgard",
    "モココ・アビスガード":       "Mococo Abyssgard",
    # EN Justice
    "エリザベス・ローズ・ブラッドフレイム": "Elizabeth Rose Bloodflame",
    "ジジ・ムリン":               "Gigi Murin",
    "セシリア・イマーグリーン":   "Cecilia Immergreen",
    "ラオーラ・パンテーラ":       "Raora Panthera",
    # ID Gen1
    "アユンダ・リス":             "Ayunda Risu",
    "ムーナ・ホシノヴァ":         "Moona Hoshinova",
    "アイラニ・イオフィフティーン": "Iofi Airani",
    # ID Gen2
    "クレイジー・オリー":         "Kureiji Ollie",
    "アーニャ・メルフィッサ":     "Anya Melfissa",
    "パヴォリア・レイネ":         "Pavolia Reine",
    # ID Gen3
    "ベスティア・ゼータ":         "Vestia Zeta",
    "カエラ・コヴァルスキア":     "Kaela Kovalskia",
    "こぼ・かなえる":             "Kobo Kanaeru",
    # Support/Staff
    "春先のどか":                 "Harusaki Nodoka",
    # Mascots
    "うぱお":                     "Upao",
    # Units
    "SorAZ":                      "SorAZ",
}

# Short names only used inside 〈〉 brackets — safe because brackets mean it's a card reference
BRACKETED_NAME_MAP = {
    "すいせい":     "Hoshimachi Suisei",
    "フブキ":       "Shirakami Fubuki",
    "まつり":       "Natsuiro Matsuri",
    "あくあ":       "Minato Aqua",
    "シオン":       "Murasaki Shion",
    "あやめ":       "Nakiri Ayame",
    "ちょこ":       "Yuzuki Choco",
    "スバル":       "Oozora Subaru",
    "おかゆ":       "Nekomata Okayu",
    "ころね":       "Inugami Korone",
    "ぺこら":       "Usada Pekora",
    "フレア":       "Shiranui Flare",
    "ノエル":       "Shirogane Noel",
    "マリン":       "Houshou Marine",
    "かなた":       "Amane Kanata",
    "わため":       "Tsunomaki Watame",
    "トワ":         "Tokoyami Towa",
    "ルーナ":       "Himemori Luna",
    "ラミィ":       "Yukihana Lamy",
    "ねね":         "Momosuzu Nene",
    "ぼたん":       "Shishiro Botan",
    "ポルカ":       "Omaru Polka",
    "こより":       "Hakui Koyori",
    "いろは":       "Kazama Iroha",
    "ルイ":         "Takane Lui",
    "ムメイ":       "Nanashi Mumei",
    "ファウナ":     "Ceres Fauna",
    "クロニー":     "Ouro Kronii",
    "バエル":       "Hakos Baelz",
}

def replace_names_in_text(text):
    """
    Replace JP member names with official EN names in ability text.
    - Full names: replaced anywhere they appear (safe — long and specific)
    - Short names: only replaced inside 〈〉 brackets (safe — context is clear)
    - Also handles post-Google-Translate garbled versions of names
    """
    if not text:
        return text

    # 1. Replace full JP names (safe anywhere)
    for jp, en in FULL_NAME_MAP.items():
        if jp in text:
            text = text.replace(jp, en)

    # 2. Replace short names only inside 〈〉 brackets
    def replace_bracketed(m):
        inner = m.group(1)
        return BRACKETED_NAME_MAP.get(inner, inner)

    text = re.sub(r'〈([^〉]+)〉', replace_bracketed, text)

    # 3. Remove remaining lenticular brackets 〈〉 → just the content
    # (any name not in our map should still be readable without the brackets)
    text = re.sub(r'[〈〉]', '', text)

    # 4. Fix common GT garbling of EN member names
    # GT sometimes translates EN katakana names back weirdly
    garbled_fixes = {
        "Ouro Chrony":          "Ouro Kronii",
        "Ouro Crony":           "Ouro Kronii",
        "Hakos Bale":           "Hakos Baelz",
        "Hakos Bayle":          "Hakos Baelz",
        "Gaul Gura":            "Gawr Gura",
        "Gal Gura":             "Gawr Gura",
        "Nanashi Mumei":        "Nanashi Mumei",
        "Mori Calliope":        "Mori Calliope",
        "Watson Amelia":        "Watson Amelia",
        "Ninomae Ina'nis":      "Ninomae Ina'nis",
        "La Darkness":          "La+ Darknesss",
        "La+ Darkness":         "La+ Darknesss",
        "Raora Panthera":       "Raora Panthera",
        "Gigi Mulin":           "Gigi Murin",
        "Kirikara Vivi":        "Kikirara Vivi",
    }
    for wrong, correct in garbled_fixes.items():
        if wrong in text:
            text = text.replace(wrong, correct)

    return text

# ── GAME TERM FIXES ───────────────────────────────────────────────────
# Google Translate mangles these card game terms. Fix them after translation.
TERM_FIXES = [
    # Card positions
    (r'\bCenter( position)?\b',         'Center',          re.I),
    (r'\bBack (position|holo\w+)?\b',   'Back',            re.I),
    (r'\bCollab( position)?\b',         'Collab',          re.I),
    # Card types
    (r'\bHolo ?mem\b',                  'Holomem',         re.I),
    (r'\bHolo ?member\b',               'Holomem',         re.I),
    (r'\bAle\b',                        'Cheer',           0),      # エール mistranslated as Ale
    (r'\bYell\b',                       'Cheer',           0),      # エール mistranslated as Yell
    (r'\bCheer card\b',                 'Cheer',           re.I),
    (r'\bBuzz holo\w+\b',               'Buzz Holomem',    re.I),
    (r'\bOshi holo\w+\b',               'Oshi Holomem',    re.I),
    (r'\bSpot holo\w+\b',               'Spot Holomem',    re.I),
    # Bloom levels
    (r'\bDebut holo\w+\b',              'Debut Holomem',   re.I),
    (r'\b1st holo\w+\b',               '1st Holomem',     re.I),
    (r'\b2nd holo\w+\b',               '2nd Holomem',     re.I),
    (r'\bDebut bloom\b',               'Debut',            re.I),
    # Actions
    (r'\bBloom\b',                      'Bloom',           0),      # preserve capitalisation
    (r'\bbloom\b',                      'bloom',           0),
    (r'\bDown(ed)?\b',                  'Down',            0),      # going down = eliminated
    (r'\bArchive\b',                    'Archive',         0),
    (r'\bHolo Power\b',                 'Holo Power',      re.I),
    (r'\bHolo power\b',                 'Holo Power',      re.I),
    (r'\[Holo Power: ?-(\d+)\]',       r'[Holo Power: -\1]', 0),
    # Common mistranslations
    (r'\bBack Holomen\b',              'back Holomem',    0),
    (r'\bFront Holomen\b',             'front Holomem',   0),
    (r'\bmy deck\b',                   'your deck',       re.I),   # JP "自分" = "you" not "me"
    (r'\bmy stage\b',                  'your stage',      re.I),
    (r'\bmy hand\b',                   'your hand',       re.I),
    (r'\bmy life\b',                   'your life',       re.I),
    (r'\bmy cheer\b',                  'your cheer',      re.I),
    (r'\bopponent\'s deck\b',          "opponent's deck", re.I),
    (r'\bonce per turn\b',             'once per turn',   re.I),
    (r'\bonce per game\b',             'once per game',   re.I),
    (r'\bspecial damage\b',            'Special Damage',  re.I),
    (r'Special damage',                'Special Damage',  0),
    # Punctuation cleanup
    (r'　',                            ' ',               0),      # full-width space
    (r'  +',                           ' ',               0),      # double spaces
    (r' \.',                           '.',               0),
    (r' ,',                            ',',               0),
]

def fix_game_terms(text):
    """Apply card game term corrections to a translated ability string."""
    if not text:
        return text
    for pattern, replacement, flags in TERM_FIXES:
        if flags:
            text = re.sub(pattern, replacement, text, flags=flags)
        else:
            text = re.sub(pattern, replacement, text)
    return text.strip()

def translate_ability(text):
    """
    Translate a card ability text from JP to readable English.
    Applies name replacement before translation (to protect names from GT)
    and after (to fix any that slipped through or were garbled).
    """
    if not text:
        return text

    # Pre-processing: replace full-width numbers with ASCII
    text = text.replace('１', '1').replace('２', '2').replace('３', '3')
    text = text.replace('４', '4').replace('５', '5').replace('６', '6')
    text = text.replace('７', '7').replace('８', '8').replace('９', '9')
    text = text.replace('０', '0')

    # Step 1: Replace JP member names BEFORE translation
    # This protects them — GT won't try to translate "ときのそら" → "Time Sky"
    text = replace_names_in_text(text)

    # Step 2: Translate remaining JP text
    if is_japanese(text):
        translated = translate_text(text)
        if not translated:
            return text
        text = translated

    # Step 3: Replace any names that survived/garbled through GT
    text = replace_names_in_text(text)

    # Step 4: Fix game terms
    text = fix_game_terms(text)

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
            # NOTE: illustrator is intentionally excluded — never translated
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
                # Try name replacement first (handles full names not in MEMBER_NAMES)
                replaced = replace_names_in_text(card['name'])
                if not is_japanese(replaced):
                    card['name'] = replaced
                    print(f"         name → {card['name']} (name map)")
                else:
                    # Fall back to Google Translate
                    card['name'] = translate_text(card['name'])
                    print(f"         name → {card['name']} (google translate)")

        # ── Translate abilities ───────────────────────────────────
        if card.get('abilities'):
            for key, val in card['abilities'].items():
                if is_japanese(val):
                    card['abilities'][key] = translate_ability(val)
                elif val:
                    # Even already-translated text may have bad game terms from a previous run
                    card['abilities'][key] = fix_game_terms(val)

        # ── Translate tags ────────────────────────────────────────
        if card.get('tags'):
            card['tags'] = [translate_tag(t) for t in card['tags']]

        # ── Illustrator — NEVER translate, keep original ──────────
        # Illustrator names are proper nouns — 高崎律, あずーる, Nekojira etc.
        # should always display exactly as written on the card.
        # (No code needed — we simply never touch card['illustrator'])

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
