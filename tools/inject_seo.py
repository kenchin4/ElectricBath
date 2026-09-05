#!/usr/bin/env python3
"""
電浴Go!! : 検索エンジン向けのメタ情報(SEO)を HTML に注入する。

  python3 inject_seo.py --shops 1146 --prefs 41 index.html
  python3 inject_seo.py profile.html contact.html privacy.html
  python3 inject_seo.py --sitemap .        # sitemap.xml / robots.txt を書き出す

* 冪等（何度かけても二重にならない）。既存の SEO ブロックを消してから入れ直す。
* build_public.py からは inject(html, page, **info) を import して使う。
* やること
    - <title> を「検索語(電気風呂)を含む形」に書き換える
    - meta description / OGP / Twitter カード / canonical を揃える
    - JSON-LD(構造化データ)を入れる（WebSite / Dataset / Person）
      → <script type="application/ld+json"> は実行されないので CSP の script-src の対象外
    - sitemap.xml / robots.txt を生成する（noindex のページは sitemap に載せない）
* 個人情報は入れない。Person に書くのは公開プロフィールページに既に載っている
  名義・肩書き・公開リンクだけ。
"""
import json, re, sys, os, argparse, datetime

SITE = "https://kenchin4.github.io/ElectricBath/"
SITE_NAME = "電浴Go!!"
AUTHOR = {
    "@type": "Person",
    "name": "けんちん",
    "url": SITE + "profile.html",
    "jobTitle": "電気風呂鑑定士",
    "sameAs": ["https://x.com/kenchin", "https://denkiburo.jimdofree.com/"],
}

BEGIN = "<!--SEO-BEGIN-->"
END = "<!--SEO-END-->"

# ページごとの設定。noindex のページは canonical だけ付けて sitemap に載せない。
PAGES = {
    "index.html": {
        "url": SITE,
        "title": "電浴Go!! 全国の電気風呂マップ｜{shops}軒の銭湯一覧と入り方ガイド",
        "desc": ("電気風呂のある銭湯を全国{shops}軒・{prefs}都道府県、すべて自分で入って記録した"
                 "電気風呂マップ。都道府県や強さの目安で絞り込み、閉店情報も掲載。"
                 "初心者向けの電気風呂の入り方ガイド付き。"),
        "og_type": "website",
        "index": True,
        "priority": "1.0", "changefreq": "weekly",
    },
    "profile.html": {
        "url": SITE + "profile.html",
        "title": "けんちん（電気風呂鑑定士）のプロフィール｜電浴Go!!",
        "desc": None,   # 既存の description を使う
        "og_type": "profile",
        "index": True,
        "priority": "0.6", "changefreq": "monthly",
    },
    "contact.html": {"url": SITE + "contact.html", "title": None, "desc": None,
                     "og_type": "website", "index": False},
    "privacy.html": {"url": SITE + "privacy.html", "title": None, "desc": None,
                     "og_type": "website", "index": False},
}


def _esc(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def jsonld_for(page, info):
    if page == "index.html":
        shops, prefs = info["shops"], info["prefs"]
        return [{
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_NAME,
            "alternateName": ["電浴GO!!", "全国電気風呂データベース", "電気風呂マップ"],
            "url": SITE,
            "inLanguage": "ja",
            "description": PAGES[page]["desc"].format(shops=shops, prefs=prefs),
            "author": AUTHOR,
        }, {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": "全国電気風呂データベース（電浴Go!!）",
            "description": (f"電気風呂を設置している銭湯・温浴施設 {shops}軒（{prefs}都道府県）の"
                            "店名・住所・電気の強さの目安（1〜5）・閉店情報。"
                            "運営者が実際に入浴して記録した一次情報。"),
            "url": SITE,
            "inLanguage": "ja",
            "keywords": ["電気風呂", "銭湯", "スーパー銭湯", "温浴施設", "電気風呂マップ",
                         "電気風呂 一覧", "電気風呂 強さ"],
            "spatialCoverage": {"@type": "Place", "name": "日本"},
            "creator": AUTHOR,
            "dateModified": info.get("updated", datetime.date.today().isoformat()),
            "isAccessibleForFree": True,
        }]
    if page == "profile.html":
        p = dict(AUTHOR)
        p["@context"] = "https://schema.org"
        p["description"] = "全国の電気風呂を巡って記録している「電浴Go!!」の運営者。"
        p["mainEntityOfPage"] = SITE + "profile.html"
        return [p]
    return []


def _strip(html):
    return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", html, flags=re.S)


def _drop_tag(html, pattern):
    """既存の title/description/og/twitter/canonical を head から取り除く（1行単位）。"""
    return re.sub(pattern, "", html, flags=re.S)


def inject(html, page, **info):
    if page not in PAGES:
        raise SystemExit("[FAIL] 未知のページ: " + page)
    cfg = PAGES[page]
    if "</head>" not in html:
        raise SystemExit("[FAIL] </head> が見つかりません: " + page)
    html = _strip(html)
    head_end = html.index("</head>")
    head, rest = html[:head_end], html[head_end:]

    # 既存の description を拾っておく（書き換えないページ用）
    m = re.search(r'<meta name="description" content="([^"]*)"', head)
    old_desc = m.group(1) if m else ""
    m = re.search(r"<title>(.*?)</title>", head, re.S)
    old_title = m.group(1).strip() if m else SITE_NAME

    title = (cfg["title"] or old_title).format(**info)
    desc = (cfg["desc"] or old_desc).format(**info)
    if not desc:
        raise SystemExit("[FAIL] description が空です: " + page)

    # 重複しないように既存タグを落とす（順序: title, description, og:*, twitter:*, canonical）
    head = _drop_tag(head, r"\s*<title>.*?</title>")
    head = _drop_tag(head, r'\s*<meta name="description" content="[^"]*">')
    head = _drop_tag(head, r'\s*<meta property="og:[a-z_:]+" content="[^"]*">')
    head = _drop_tag(head, r'\s*<meta name="twitter:[a-z_]+" content="[^"]*">')
    head = _drop_tag(head, r'\s*<link rel="canonical" href="[^"]*">')

    lines = [BEGIN,
             f"<title>{_esc(title)}</title>",
             f'<meta name="description" content="{_esc(desc)}">',
             f'<link rel="canonical" href="{cfg["url"]}">',
             f'<meta property="og:type" content="{cfg["og_type"]}">',
             f'<meta property="og:site_name" content="{SITE_NAME}">',
             f'<meta property="og:locale" content="ja_JP">',
             f'<meta property="og:url" content="{cfg["url"]}">',
             f'<meta property="og:title" content="{_esc(title)}">',
             f'<meta property="og:description" content="{_esc(desc)}">',
             '<meta name="twitter:card" content="summary">',
             f'<meta name="twitter:title" content="{_esc(title)}">',
             f'<meta name="twitter:description" content="{_esc(desc)}">']
    if not cfg["index"]:
        if 'name="robots"' not in head:
            lines.append('<meta name="robots" content="noindex">')
    for obj in jsonld_for(page, info):
        # </script> をデータ中に含まないよう < をエスケープ
        js = json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
        lines.append(f'<script type="application/ld+json">{js}</script>')
    lines.append(END)

    # charset / viewport の直後（CSP の前）だと read しやすいが、位置は問わない。referrer の後に入れる
    anchor = '<meta name="referrer" content="strict-origin-when-cross-origin">'
    if anchor in head:
        i = head.index(anchor) + len(anchor)
        head = head[:i] + "\n" + "\n".join(lines) + head[i:]
    else:
        head = head + "\n".join(lines) + "\n"
    html = head + rest

    # 検証
    for need in ("<title>", 'name="description"', 'rel="canonical"', 'property="og:title"'):
        if html[:html.index("</head>")].count(need) != 1:
            raise SystemExit(f"[FAIL] {page}: {need} が1個になっていません")
    if html.count(BEGIN) != 1 or html.count(END) != 1:
        raise SystemExit("[FAIL] SEO マーカーが1個になっていません: " + page)
    return html


def write_sitemap(outdir, updated=None):
    updated = updated or datetime.date.today().isoformat()
    urls = []
    for page, cfg in PAGES.items():
        if not cfg["index"]:
            continue
        urls.append(f"  <url>\n    <loc>{cfg['url']}</loc>\n    <lastmod>{updated}</lastmod>\n"
                    f"    <changefreq>{cfg['changefreq']}</changefreq>\n"
                    f"    <priority>{cfg['priority']}</priority>\n  </url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    open(os.path.join(outdir, "sitemap.xml"), "w", encoding="utf-8").write(xml)
    robots = ("User-agent: *\nAllow: /\nDisallow: /tools/\n\n"
              f"Sitemap: {SITE}sitemap.xml\n")
    open(os.path.join(outdir, "robots.txt"), "w", encoding="utf-8").write(robots)
    return [c["url"] for c in PAGES.values() if c["index"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shops", type=int, default=0)
    ap.add_argument("--prefs", type=int, default=0)
    ap.add_argument("--updated", default=datetime.date.today().isoformat())
    ap.add_argument("--sitemap", metavar="DIR", help="sitemap.xml / robots.txt をこのディレクトリに書く")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    for f in a.files:
        page = os.path.basename(f)
        src = open(f, encoding="utf-8").read()
        out = inject(src, page, shops=a.shops, prefs=a.prefs, updated=a.updated)
        open(f, "w", encoding="utf-8").write(out)
        print("[OK] {}  {} -> {} bytes".format(f, len(src.encode()), len(out.encode())))
    if a.sitemap:
        print("[OK] sitemap:", write_sitemap(a.sitemap, a.updated))
