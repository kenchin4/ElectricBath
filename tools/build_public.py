#!/usr/bin/env python3
"""
電気風呂マップ: Artifact(原本) → GitHub Pages 公開版 index.html ビルダー

使い方:
    python3 build_public.py <artifact_full.html> <out_index.html> [--updated YYYY-MM-DD]

Artifact ツールの action:"read" で落としたフレーム込みの完成HTMLを入力にして、
公開版(訪問日を出さない・単体で動く完成HTML)を書き出す。
加工内容は claude/google-sites-publish.md の「公開版は訪問日を出さない」6項目に対応。
"""
import json, re, sys, os, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject_ga
import inject_seo

# GA4 測定ID。--ga-id で上書き可。空文字にすると計測タグなしでビルドする。
# 注意: CSP への追記も inject_ga 側で自動的に行われる（HEAD_TMPL は素のままでよい）。
GA_ID = "G-4RX2TGNQPV"

HEAD_TMPL = '''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; form-action 'none'; base-uri 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>電浴Go!!</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:title" content="電浴Go!!">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ctext y='26' font-size='26'%3E%E2%9A%A1%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&family=Oswald:wght@400;600&display=swap">
</head>
<body>
'''

def sub1(s, old, new, label):
    """1箇所だけ置換。0回 or 2回以上なら例外(Artifact側の構造変化を検知する)。"""
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"[FAIL] {label}: 期待1件 / 実際{n}件 -- Artifact側の構造が変わっています")
    return s.replace(old, new, 1)

def extract_json_array(s, marker):
    i = s.index(marker) + len(marker)
    assert s[i] == '['
    depth, in_str, esc = 0, False, False
    for j in range(i, len(s)):
        ch = s[j]
        if in_str:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': in_str = False
        else:
            if ch == '"': in_str = True
            elif ch == '[': depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    return i, j + 1, json.loads(s[i:j+1])
    raise SystemExit("[FAIL] SHOPS配列の終端が見つかりません")

def build(raw, updated, ga_id=GA_ID):
    # --- 1. body抜き出し（フレーム込みHTMLから中身だけ取る） ---
    bs = raw.find('<body>')
    be = raw.rfind('</body>')
    if bs < 0 or be < 0:
        raise SystemExit("[FAIL] <body> が見つかりません")
    body = raw[bs + len('<body>'):be]
    # Artifact本体の先頭にある title / フォントlink は head 側に移してあるので落とす
    st = body.find('<style>')
    if st < 0:
        raise SystemExit("[FAIL] 先頭の <style> が見つかりません")
    body = body[st:]

    # --- 2. SHOPS から d(訪問日) と v(回数) を落とす ---
    i, j, shops = extract_json_array(body, '/*__SHOPS__*/')
    n_before = len(shops)
    n_d = sum(1 for s in shops if 'd' in s)
    for s in shops:
        s.pop('d', None)
        s.pop('v', None)
    assert len(shops) == n_before
    body = body[:i] + json.dumps(shops, ensure_ascii=False, separators=(',', ':')) + body[j:]

    # --- 3. カードの訪問日行を削除 ---
    body = sub1(body,
        '''     ${s.d?`<div class="visitdate">入湯 ${esc(s.d)}${s.v?` ・ ${esc(s.v)}回`:""}</div>`:""}\n''',
        '', 'カードの訪問日行')

    # --- 4. .visitdate の CSS を削除 ---
    body = sub1(body,
        '.visitdate{font-size:11px;color:var(--dim);font-family:var(--num)}\n',
        '', '.visitdate CSS')

    # --- 5. 並べ替えの「訪問が新しい順」を削除（optionとソート分岐） ---
    body = sub1(body,
        '        <option value="recent">訪問が新しい順</option>\n',
        '', '並べ替えoption')
    body = sub1(body,
        '  else l.sort((a,b)=>String(b.d||"").localeCompare(String(a.d||"")));\n',
        '', '訪問日ソート分岐')

    # --- 6. 「入湯した年数」は d から算出していたので定数化 ---
    body = sub1(body,
        '''  const yrs = SHOPS.map(s=>s.d).filter(Boolean).sort();
  $("#s-years").textContent = yrs.length
    ? (Number(yrs[yrs.length-1].slice(0,4)) - Number(yrs[0].slice(0,4)) + 1) : "–";''',
        '  $("#s-years").textContent = 10;', '入湯した年数の算出')

    # --- 7. フッターの文言と META.updated ---
    body = sub1(body, '"収録データの最終入湯日："', '"データ最終更新："', 'フッター文言')
    mi = body.index('/*__META__*/') + len('/*__META__*/')
    mj = body.index('/*__END__*/', mi)
    meta = json.loads(body[mi:mj])
    meta['updated'] = updated
    body = body[:mi] + json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + body[mj:]

    # --- 8. 検証: 公開版に訪問日が残っていないこと ---
    for bad in ['visitdate', '最終入湯日', '訪問が新しい順']:
        if bad in body:
            raise SystemExit(f"[FAIL] 公開版に '{bad}' が残っています")
    if re.search(r'"d":"\d{4}-\d{2}-\d{2}"', body):
        raise SystemExit("[FAIL] SHOPSに訪問日が残っています")

    desc = (f"全国{n_before}軒の電気風呂を、自分の足で回って記録した地図。"
            "都道府県や強さの目安で絞り込み、訪問チェックで訪問率が出ます。")
    html = HEAD_TMPL.format(desc=desc) + body + '</body>\n</html>\n'
    n_prefs = len({s['k'] for s in shops})

    # --- 9. フッターにプライバシーポリシーへの導線 + アクセス解析(GA4)タグ ---
    html = inject_ga.add_privacy_link(html)
    if ga_id:
        html = inject_ga.inject(html, ga_id)   # CSP への追記もここで行われる

    # --- 10. 検索エンジン向けメタ情報（title / description / canonical / OGP / JSON-LD） ---
    # HEAD_TMPL の title / description / og:* はここで上書きされる（inject_seo が唯一の定義元）
    html = inject_seo.inject(html, 'index.html', shops=n_before, prefs=n_prefs, updated=updated)

    stats = {
        'shops': n_before,
        'prefs': n_prefs,
        'closed': sum(1 for s in shops if s.get('c')),
        'paused_x': sum(1 for s in shops if s.get('cx')),
        'unclear': sum(1 for s in shops if s.get('cw')),
        'had_visitdate': n_d,
        'updated': updated,
        'bytes': len(html.encode('utf-8')),
        'ga_id': ga_id or '(なし)',
    }
    return html, stats

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--updated', default=datetime.date.today().isoformat())
    ap.add_argument('--ga-id', default=GA_ID, help='GA4測定ID。空文字で計測タグなし')
    a = ap.parse_args()
    html, stats = build(open(a.src, encoding='utf-8').read(), a.updated, a.ga_id)
    open(a.dst, 'w', encoding='utf-8').write(html)
    # sitemap.xml / robots.txt を index.html と同じ場所に書く（lastmod は --updated）
    stats['sitemap'] = inject_seo.write_sitemap(os.path.dirname(os.path.abspath(a.dst)) , a.updated)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
