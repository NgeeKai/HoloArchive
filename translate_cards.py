#!/usr/bin/env python3
"""
Holoarchive Card Translator
============================
Translates Japanese text in cards.json to English.

Card NAMES use a hardcoded lookup table of official hololive member
names — so ときのそら → "Tokino Sora" not "Time's Sky".

Ability TEXT uses Claude API for natural, accurate card game translation.
Falls back to Google Translate if ANTHROPIC_API_KEY is not set.

Usage:
    pip install requests deep-translator
    ANTHROPIC_API_KEY=your_key python translate_cards.py

    # Or without Claude (uses Google Translate):
    python translate_cards.py

Resume-safe: skips already-translated cards on re-run.
"""

import json, time, os, sys, re, requests

try:
    from deep_translator import GoogleTranslator
    _GT_AVAILABLE = True
except ImportError:
    _GT_AVAILABLE = False

# ── CONFIG ────────────────────────────────────────────────────────────
INPUT_FILE       = "cards.json"
OUTPUT_FILE      = "cards.json"
BACKUP_FILE      = "cards_jp_backup.json"
GT_DELAY         = 0.3    # seconds between Google Translate calls
CLAUDE_DELAY     = 0.5    # seconds between Claude API calls
CLAUDE_BATCH     = 8      # translate N ability texts per Claude API call

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "AIzaSyBbGfm0x7L0mEgzTKcz24fZkwuYnGDs9hU")

# Priority: Gemini first (free, good quality), Claude second, GT only for names/tags
USE_GEMINI  = bool(GEMINI_API_KEY)
USE_CLAUDE  = bool(ANTHROPIC_API_KEY) and not USE_GEMINI  # Claude only if no Gemini key
USE_AI      = USE_GEMINI or USE_CLAUDE

GEMINI_DELAY          = 4.0    # seconds between Gemini calls (free tier: 15 RPM)
GEMINI_MAX_RETRIES    = 3      # retries on transient errors (not rate limits)
GEMINI_DAILY_LIMIT    = 1500   # free tier: 1500 requests/day — stop before hitting it

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
    "シオリ・ノベラ":       "Shiori Novella",   # alternate spelling
    "シオリ・ノヴェラ":     "Shiori Novella",   # correct card spelling
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
                # Translate suffix if it's Japanese
                if is_japanese(suffix):
                    suffix = _gt_translate(suffix) or suffix
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


# ── TRANSLATORS ───────────────────────────────────────────────────────

CLAUDE_SYSTEM = """You are a translator for the hololive OFFICIAL CARD GAME (hOCG), a Japanese trading card game.

Translate Japanese card ability text to natural, readable English.

GAME TERMINOLOGY — always use these exact terms:
- ホロメン → Holomem (never "holo member" or "holomember")
- エール → Cheer (never "yell" or "ale") — these are energy cards
- 推しホロメン → Oshi Holomem
- Buzzホロメン → Buzz Holomem
- ブルーム/Bloom → Bloom (card evolution mechanic)
- ダウン → Down (eliminated/KO'd)
- アーカイブ → Archive (discard pile)
- ホロパワー → Holo Power
- センター/Center → Center position
- バック/Back → Back position
- コラボ/Collab → Collab position
- 特殊ダメージ → Special Damage
- デッキ → deck
- 手札 → hand
- ライフ → Life
- ステージ → stage

PRONOUN RULE:
- 自分 = "you" / "your" (NOT "I" / "my") — abilities are written from the player's perspective
- 相手 = "your opponent" / "opponent's"

STRUCTURE:
- Arts text starts with: [Ability Name] [Cost/Damage number] [Effect]
  e.g. 早送り　60　自分の... → "Fast Forward: 60 — [effect]"
- Costs in brackets: [ホロパワー：-2] → "[Holo Power: -2]"
- "ターンに１回" → "once per turn"
- "ゲームに１回" → "once per game"

OUTPUT: Return ONLY the translated text. No explanations, no notes."""

def translate_with_claude(texts):
    """Translate ability texts using Claude API (best quality)."""
    if not texts:
        return texts

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = f"""Translate each numbered ability text from Japanese to English.\nReturn exactly the same number of lines, each starting with the number.\n\n{numbered}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 2048,
                "system": CLAUDE_SYSTEM,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        time.sleep(CLAUDE_DELAY)
        return _parse_numbered(raw, texts)
    except Exception as e:
        print(f"    ⚠ Claude API error: {e} — falling back")
        return [_gt_translate(t) for t in texts]


def translate_with_gemini(texts):
    """Translate ability texts using Gemini API.
    Hard-stops on rate limit (429) — never silently falls back to Google Translate.
    """
    if not texts:
        return texts

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = (
        f"{CLAUDE_SYSTEM}\n\n"
        f"Translate each numbered ability text from Japanese to English.\n"
        f"Return exactly the same number of lines, each starting with the number.\n\n"
        f"{numbered}"
    )

    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                headers={"content-type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=45,
            )

            # Rate limit hit — hard stop, do not fall back to GT
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "unknown")
                print(f"\n⛔ Gemini daily rate limit hit (429). Retry-After: {retry_after}s")
                print("   Saving progress and exiting — run again tomorrow.")
                print("   Tip: set ANTHROPIC_API_KEY as a backup for when Gemini quota runs out.")
                raise SystemExit(2)   # exit code 2 = rate limited (workflow can detect this)

            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            time.sleep(GEMINI_DELAY)
            return _parse_numbered(raw, texts)

        except SystemExit:
            raise   # propagate the rate limit exit

        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"    ⚠ Gemini error (attempt {attempt+1}/{GEMINI_MAX_RETRIES}): {e} — retrying in {wait}s")
            time.sleep(wait)

    # All retries failed on transient errors — raise so the workflow knows
    raise RuntimeError(f"Gemini failed after {GEMINI_MAX_RETRIES} attempts")


def translate_with_claude(texts):
    """Translate ability texts using Claude API (backup when Gemini not configured)."""
    if not texts:
        return texts

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = (
        f"Translate each numbered ability text from Japanese to English.\n"
        f"Return exactly the same number of lines, each starting with the number.\n\n"
        f"{numbered}"
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 2048,
                "system": CLAUDE_SYSTEM,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        time.sleep(CLAUDE_DELAY)
        return _parse_numbered(raw, texts)
    except Exception as e:
        raise RuntimeError(f"Claude API error: {e}")


def translate_batch(texts):
    """Route to best available translator for ability texts.
    Order: Gemini (default) → Claude (backup) → hard fail.
    Google Translate is NEVER used for abilities — quality too low.
    """
    if USE_GEMINI:
        return translate_with_gemini(texts)
    elif USE_CLAUDE:
        return translate_with_claude(texts)
    else:
        # No AI key — return untranslated and warn once
        if not hasattr(translate_batch, '_warned'):
            print("⚠ No GEMINI_API_KEY or ANTHROPIC_API_KEY set.")
            print("  Abilities will NOT be translated. Set GEMINI_API_KEY in GitHub Secrets.")
            translate_batch._warned = True
        return texts  # keep JP text — better than wrong GT translation


def _parse_numbered(raw, originals):
    """Parse numbered list response back into a list."""
    results = [""] * len(originals)
    for line in raw.split("\n"):
        m = re.match(r'^(\d+)[.)]\s*(.*)', line.strip())
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(results):
                results[idx] = m.group(2).strip()
    return [results[i] or originals[i] for i in range(len(originals))]


_gt = None
def _gt_translate(text):
    """Google Translate fallback."""
    global _gt
    if not _GT_AVAILABLE:
        return text
    if _gt is None:
        _gt = GoogleTranslator(source='ja', target='en')
    try:
        result = _gt.translate(text)
        time.sleep(GT_DELAY)
        return result or text
    except Exception as e:
        print(f"    ⚠ Google Translate error: {e}")
        time.sleep(2)
        return text


def translate_text(text):
    """Translate a single text — uses Google Translate (for names/tags)."""
    if not text or not is_japanese(text):
        return text
    return _gt_translate(text)


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
    "シオリ・ノベラ":             "Shiori Novella",   # alternate spelling
    "シオリ・ノヴェラ":           "Shiori Novella",   # correct card spelling
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
    """Translate a single ability text — used for fallback cases."""
    if not text:
        return text
    text = _preprocess(text)
    text = replace_names_in_text(text)
    if is_japanese(text):
        result = translate_batch([text])
        text = result[0]
    text = replace_names_in_text(text)
    text = fix_game_terms(text)
    return text


def _preprocess(text):
    """Normalize full-width characters before translation."""
    for fw, hw in zip('１２３４５６７８９０', '1234567890'):
        text = text.replace(fw, hw)
    text = text.replace('　', ' ')
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

    if USE_GEMINI:
        print(f"✓ Using Gemini API (gemini-2.0-flash, free tier) for ability translation")
        print(f"  Daily limit guard: will stop at {GEMINI_DAILY_LIMIT} requests to avoid 429")
    elif USE_CLAUDE:
        print(f"✓ Using Claude API (haiku) for ability translation")
    else:
        print(f"⚠ No GEMINI_API_KEY set — abilities will be left in Japanese")
        print(f"  Add GEMINI_API_KEY to GitHub Secrets for automatic translation")

    total = len(cards)
    print(f"Translating {total} cards...\n")

    for i, card in enumerate(cards):
        needs_work = (
            is_japanese(card.get('name', '')) or
            any(is_japanese(v) for v in (card.get('abilities') or {}).values()) or
            any(is_japanese(t) for t in (card.get('tags') or []))
        )
        if not needs_work:
            # Still apply term/name fixes to already-translated text
            if card.get('abilities'):
                for key, val in card['abilities'].items():
                    if val and not is_japanese(val):
                        card['abilities'][key] = fix_game_terms(replace_names_in_text(val))
            continue

        print(f"  [{card['id']:>4}] {card['card_number']:<16} {card.get('name','')[:25]}")

        # ── Translate name ────────────────────────────────────────
        if is_japanese(card.get('name', '')):
            official = lookup_name(card['name'])
            if official:
                card['name'] = official
                print(f"         name → {card['name']} (lookup)")
            else:
                replaced = replace_names_in_text(card['name'])
                if not is_japanese(replaced):
                    card['name'] = replaced
                    print(f"         name → {card['name']} (name map)")
                else:
                    card['name'] = translate_text(card['name'])
                    print(f"         name → {card['name']} (google translate)")

        # ── Translate abilities — batch with Claude ───────────────
        if card.get('abilities'):
            ab_keys   = list(card['abilities'].keys())
            ab_values = list(card['abilities'].values())

            # Pre-process all values
            processed = []
            for v in ab_values:
                v = _preprocess(v) if v else v
                v = replace_names_in_text(v) if v else v
                processed.append(v)

            # Translate JP ones in one Claude batch call
            jp_indices = [j for j, v in enumerate(processed) if v and is_japanese(v)]
            if jp_indices:
                jp_texts = [processed[j] for j in jp_indices]
                translated = translate_batch(jp_texts)
                for j, t in zip(jp_indices, translated):
                    processed[j] = t

            # Post-process all
            for j in range(len(processed)):
                if processed[j]:
                    processed[j] = replace_names_in_text(processed[j])
                    processed[j] = fix_game_terms(processed[j])

            card['abilities'] = dict(zip(ab_keys, processed))

        # ── Translate tags ────────────────────────────────────────
        if card.get('tags'):
            card['tags'] = [translate_tag(t) for t in card['tags']]

        # ── Illustrator — NEVER translate ─────────────────────────
        # Names like 高崎律, あずーる, Nekojira stay exactly as written on the card.

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
