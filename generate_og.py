#!/usr/bin/env python3
"""
generate_og.py — Auto-generates og-image.svg from cards.json stats.

Run this after scrape_hocg.py, before pushing to GitHub:
    python scrape_hocg.py
    python generate_og.py
    git add cards.json og-image.svg
    git commit -m "update cards"
    git push
"""

import json
import os
from collections import Counter
from datetime import date

CARDS_FILE  = "cards.json"
OUTPUT_FILE = "og-image.svg"
DOMAIN      = "holoarchive.pages.dev"

# ── Read cards.json and compute stats ────────────────────────────────────────
if not os.path.exists(CARDS_FILE):
    print(f"✗ {CARDS_FILE} not found — run scrape_hocg.py first")
    exit(1)

with open(CARDS_FILE, "r", encoding="utf-8") as f:
    cards = json.load(f)

total_cards = len(cards)
total_sets  = len(set(c.get("set_code") for c in cards if c.get("set_code")))
total_colors = len(set(c.get("color") for c in cards if c.get("color")))

# Count unique card types (normalised)
JP_TYPE_MAP = {
    "推しホロメン": "Oshi", "ホロメン": "Holomem", "Buzzホロメン": "Buzz Holomem",
    "サポート・アイテム": "Support", "サポート・アイテム・LIMITED": "Support",
    "サポート・イベント": "Support", "サポート・イベント・LIMITED": "Support",
    "サポート・ツール": "Support", "サポート・マスコット": "Support",
    "サポート・ファン": "Support", "サポート・スタッフ": "Support",
    "サポート・スタッフ・LIMITED": "Support",
}
type_counts = Counter(
    JP_TYPE_MAP.get(c.get("card_type", ""), c.get("card_type", "other"))
    for c in cards
)
total_types = len(type_counts)

today = date.today().strftime("%B %d, %Y")

print(f"Stats from {CARDS_FILE}:")
print(f"  Cards  : {total_cards:,}")
print(f"  Sets   : {total_sets}")
print(f"  Colors : {total_colors}")
print(f"  Types  : {total_types}")
print(f"  Date   : {today}")

# ── Generate SVG ──────────────────────────────────────────────────────────────
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#080e1a"/>
      <stop offset="100%" stop-color="#0c1f3a"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#005fa3"/>
      <stop offset="50%" stop-color="#00a8e8"/>
      <stop offset="100%" stop-color="#00d4ff"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>

  <!-- Grid lines -->
  <g stroke="rgba(0,168,232,0.05)" stroke-width="1">
    <line x1="0" y1="105" x2="1200" y2="105"/>
    <line x1="0" y1="210" x2="1200" y2="210"/>
    <line x1="0" y1="315" x2="1200" y2="315"/>
    <line x1="0" y1="420" x2="1200" y2="420"/>
    <line x1="0" y1="525" x2="1200" y2="525"/>
    <line x1="200" y1="0" x2="200" y2="630"/>
    <line x1="400" y1="0" x2="400" y2="630"/>
    <line x1="600" y1="0" x2="600" y2="630"/>
    <line x1="800" y1="0" x2="800" y2="630"/>
    <line x1="1000" y1="0" x2="1000" y2="630"/>
  </g>

  <!-- Accent bar top -->
  <rect width="1200" height="5" fill="url(#accent)"/>

  <!-- Decorative card outlines right side -->
  <g opacity="0.10">
    <rect x="740" y="40"  width="150" height="210" rx="12" fill="none" stroke="#00a8e8" stroke-width="1.5" transform="rotate(-8,815,145)"/>
    <rect x="840" y="60"  width="150" height="210" rx="12" fill="none" stroke="#00a8e8" stroke-width="1.5" transform="rotate(-2,915,165)"/>
    <rect x="940" y="30"  width="150" height="210" rx="12" fill="none" stroke="#00a8e8" stroke-width="1.5" transform="rotate(6,1015,135)"/>
    <rect x="800" y="330" width="150" height="210" rx="12" fill="none" stroke="#00d4ff" stroke-width="1.5" transform="rotate(4,875,435)"/>
    <rect x="960" y="310" width="150" height="210" rx="12" fill="none" stroke="#00d4ff" stroke-width="1.5" transform="rotate(-5,1035,415)"/>
  </g>

  <!-- Logo mark (left of title) -->
  <g transform="translate(80, 50)">
    <rect width="80" height="80" rx="18" fill="url(#accent)"/>
    <path d="M12 25C12 21 15 19 19 19L38 22L38 61L19 58C15 58 12 56 12 52Z" fill="white" fill-opacity="0.95"/>
    <path d="M68 25C68 21 65 19 61 19L42 22L42 61L61 58C65 58 68 56 68 52Z" fill="white" fill-opacity="0.70"/>
    <line x1="40" y1="20" x2="40" y2="62" stroke="#00d4ff" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="17" y1="29" x2="36" y2="30" stroke="#003d6b" stroke-width="1.8" stroke-linecap="round" stroke-opacity="0.7"/>
    <line x1="17" y1="37" x2="36" y2="38" stroke="#003d6b" stroke-width="1.8" stroke-linecap="round" stroke-opacity="0.7"/>
    <line x1="17" y1="45" x2="30" y2="46" stroke="#003d6b" stroke-width="1.8" stroke-linecap="round" stroke-opacity="0.5"/>
    <path d="M65,12 L66.3,16 L70.5,16 L67.2,18.8 L68.5,23 L65,20.5 L61.5,23 L62.8,18.8 L59.5,16 L63.7,16 Z" fill="white" fill-opacity="0.9"/>
  </g>

  <!-- Title (right of logo, vertically centred) -->
  <text x="180" y="110" font-family="system-ui,-apple-system,sans-serif" font-size="62" font-weight="700" fill="white" letter-spacing="-1">Holoarchive</text>
  <rect x="180" y="120" width="400" height="4" rx="2" fill="url(#accent)"/>

  <!-- Subtitle -->
  <text x="80" y="175" font-family="system-ui,-apple-system,sans-serif" font-size="24" fill="#7ab8d8">hololive OFFICIAL CARD GAME &#8212; Card Database</text>
  <line x1="80" y1="198" x2="680" y2="198" stroke="rgba(0,168,232,0.18)" stroke-width="1"/>

  <!-- Feature pills -->
  <g transform="translate(80, 228)">
    <rect x="0"   y="0" width="170" height="38" rx="19" fill="rgba(0,168,232,0.15)" stroke="rgba(0,168,232,0.4)" stroke-width="1"/>
    <text x="85"  y="25" text-anchor="middle" font-family="system-ui,sans-serif" font-size="15" fill="#00d4ff">Search &amp; Filter</text>
    <rect x="186" y="0" width="120" height="38" rx="19" fill="rgba(0,168,232,0.15)" stroke="rgba(0,168,232,0.4)" stroke-width="1"/>
    <text x="246" y="25" text-anchor="middle" font-family="system-ui,sans-serif" font-size="15" fill="#00d4ff">All Sets</text>
    <rect x="322" y="0" width="155" height="38" rx="19" fill="rgba(0,168,232,0.15)" stroke="rgba(0,168,232,0.4)" stroke-width="1"/>
    <text x="399" y="25" text-anchor="middle" font-family="system-ui,sans-serif" font-size="15" fill="#00d4ff">Card Details</text>
    <rect x="493" y="0" width="140" height="38" rx="19" fill="rgba(0,168,232,0.15)" stroke="rgba(0,168,232,0.4)" stroke-width="1"/>
    <text x="563" y="25" text-anchor="middle" font-family="system-ui,sans-serif" font-size="15" fill="#00d4ff">Free to use</text>
  </g>

  <!-- Stats (auto-generated from cards.json) -->
  <g transform="translate(80, 330)">
    <text x="0"   y="44" font-family="system-ui,sans-serif" font-size="44" font-weight="700" fill="white">{total_cards:,}</text>
    <text x="0"   y="72" font-family="system-ui,sans-serif" font-size="15" fill="#7ab8d8">cards indexed</text>
    <text x="210" y="44" font-family="system-ui,sans-serif" font-size="44" font-weight="700" fill="white">{total_sets}</text>
    <text x="210" y="72" font-family="system-ui,sans-serif" font-size="15" fill="#7ab8d8">sets covered</text>
    <text x="370" y="44" font-family="system-ui,sans-serif" font-size="44" font-weight="700" fill="white">{total_colors}</text>
    <text x="370" y="72" font-family="system-ui,sans-serif" font-size="15" fill="#7ab8d8">colors</text>
    <text x="490" y="44" font-family="system-ui,sans-serif" font-size="44" font-weight="700" fill="white">{total_types}</text>
    <text x="490" y="72" font-family="system-ui,sans-serif" font-size="15" fill="#7ab8d8">card types</text>
  </g>

  <line x1="80" y1="450" x2="680" y2="450" stroke="rgba(0,168,232,0.18)" stroke-width="1"/>

  <!-- Tagline with today's date -->
  <text x="80" y="490" font-family="system-ui,sans-serif" font-size="18" fill="rgba(255,255,255,0.45)">Last updated {today} &#8212; data from the official hololive OCG site</text>

  <!-- Footer -->
  <rect y="590" width="1200" height="40" fill="rgba(0,168,232,0.07)"/>
  <text x="80"   y="615" font-family="system-ui,sans-serif" font-size="14" fill="rgba(255,255,255,0.35)">Fan project &#8212; not affiliated with COVER Corp. or hololive production</text>
  <text x="1120" y="615" text-anchor="end" font-family="system-ui,sans-serif" font-size="14" fill="rgba(0,168,232,0.65)">{DOMAIN}</text>
</svg>"""

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(svg)

print(f"\n✓ {OUTPUT_FILE} generated with live stats")

# ── Auto-generate sitemap.xml from actual set codes in cards.json ─────
SITEMAP_FILE = "sitemap.xml"
BASE_URL_SITE = f"https://{DOMAIN}"
set_codes = sorted(set(c.get("set_code") for c in cards if c.get("set_code")))
today_iso = date.today().isoformat()

sitemap_urls = []

# Main pages
sitemap_urls.append(f"""  <url>
    <loc>{BASE_URL_SITE}/</loc>
    <lastmod>{today_iso}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>""")

sitemap_urls.append(f"""  <url>
    <loc>{BASE_URL_SITE}/?view=cards</loc>
    <lastmod>{today_iso}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>""")

sitemap_urls.append(f"""  <url>
    <loc>{BASE_URL_SITE}/?view=sets</loc>
    <lastmod>{today_iso}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""")

# One entry per set (auto-discovered from cards.json)
for code in set_codes:
    sitemap_urls.append(f"""  <url>
    <loc>{BASE_URL_SITE}/?set={code}</loc>
    <lastmod>{today_iso}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

{chr(10).join(sitemap_urls)}

</urlset>
"""

with open(SITEMAP_FILE, "w", encoding="utf-8") as f:
    f.write(sitemap_xml)

print(f"✓ {SITEMAP_FILE} updated — {len(sitemap_urls)} URLs ({len(set_codes)} sets)")
