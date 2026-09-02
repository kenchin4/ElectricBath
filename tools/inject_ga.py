#!/usr/bin/env python3
"""
電浴Go!! : Google アナリティクス4(GA4) の計測タグを HTML に注入する。

  python3 inject_ga.py --id G-XXXXXXXXXX index.html contact.html profile.html privacy.html

* 冪等（何度かけても二重にならない）。既存の GA ブロックを消してから入れ直す。
* build_public.py からは inject(html, ga_id) を import して使う。
* 送るのは「どのページを見たか」「どの絞り込み・検索をしたか」「どのお店の地図を開いたか」
  といった行動だけ。個人を特定する情報（入力したメールアドレス等）は一切送らない。
"""
import re, sys, argparse

HEAD_BEGIN = "<!--GA4-BEGIN-->"
HEAD_END = "<!--GA4-END-->"
BODY_BEGIN = "<!--GA4-TRACK-BEGIN-->"
BODY_END = "<!--GA4-TRACK-END-->"

HEAD_TPL = """<!--GA4-BEGIN-->
<script async src="https://www.googletagmanager.com/gtag/js?id={id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{id}', {{ anonymize_ip: true }});
</script>
<!--GA4-END-->"""

BODY_TPL = """<!--GA4-TRACK-BEGIN-->
<script>
/* 電浴Go!! サイト内行動の計測。gtag が無い環境（ローカル確認など）では何もしない。 */
(function(){
  function send(name, params){
    try{
      if(typeof window.gtag === "function"){ window.gtag("event", name, params || {}); }
      (window.__ebEvents = window.__ebEvents || []).push([name, params || {}]);
    }catch(e){}
  }
  window.ebTrack = send;

  var $ = function(id){ return document.getElementById(id); };
  var txt = function(n){ return n ? (n.textContent || "").replace(/\\s+/g," ").trim() : ""; };
  function resultCount(){
    var m = txt($("count")).match(/(\\d+)/);
    return m ? Number(m[1]) : undefined;
  }

  /* --- 絞り込みの「変化」を拾う: クリック/選択の直後に状態を見比べる --- */
  function snap(){
    var sel = $("pref-select");
    var on = [];
    Array.prototype.forEach.call(document.querySelectorAll(".chip.on"), function(b){
      var t = txt(b);
      if(t && t !== "\u3059\u3079\u3066" && t !== "\u3053\u3060\u308f\u3089\u306a\u3044"){ on.push(t); }
    });
    return { pref: sel ? (sel.value || "") : "", chips: on.join(" / ") };
  }
  var prev = snap();
  function diff(source){
    setTimeout(function(){
      var now = snap();
      if(now.pref !== prev.pref || now.chips !== prev.chips){
        send("filter_change", {
          pref: now.pref || "(指定なし)",
          filters: now.chips || "(なし)",
          source: source,
          result_count: resultCount()
        });
      }
      prev = now;
    }, 80);
  }

  document.addEventListener("click", function(e){
    var t = e.target;
    if(!t || !t.closest) return;

    /* Googleマップを開いた */
    var a = t.closest("a");
    if(a && (a.getAttribute("href") || "").indexOf("google.com/maps") >= 0){
      var card = t.closest(".card");
      send("open_gmap", {
        shop: txt(card && card.querySelector("h3")).slice(0,100),
        pref: txt(card && card.querySelector(".pref"))
      });
      return;
    }
    /* サイト内の別ページ / 外部リンク */
    if(a){
      var href = a.getAttribute("href") || "";
      if(/(contact|profile|privacy)\\.html/.test(href)){
        send("page_link", { link_text: txt(a).slice(0,60), link_url: href });
        return;
      }
      if(/^https?:/.test(href) && a.hostname && a.hostname !== location.hostname){
        send("outbound_click", { link_text: txt(a).slice(0,60), link_url: href });
        return;
      }
      if(/^mailto:/.test(href)){ send("mail_link", {}); return; }
    }

    /* 日本地図の都道府県 */
    var svgp = t.closest && t.closest("#japan path");
    if(svgp){
      var ttl = svgp.querySelector && svgp.querySelector("title");
      send("map_pref_click", { pref: txt(ttl).split(/[\\s\\u3000]/)[0] });
      diff("map"); return;
    }
    if(t.closest("#pref-rank")){ diff("ranking"); return; }
    if(t.closest("#pw-dist")){ diff("power_dist"); return; }

    var btn = t.closest("button");
    if(!btn) return;
    if(btn.classList.contains("check")){
      var c2 = t.closest(".card");
      send("visit_check", {
        shop: txt(c2 && c2.querySelector("h3")).slice(0,100),
        pref: txt(c2 && c2.querySelector(".pref")),
        state: btn.classList.contains("on") ? "off" : "on"
      });
      return;
    }
    if(btn.id === "more"){ send("load_more", { result_count: resultCount() }); return; }
    if(btn.id === "reset"){ send("reset_visits", {}); return; }
    if(btn.classList.contains("chip")){ diff("chip"); return; }
  }, true);

  document.addEventListener("change", function(e){
    var t = e.target; if(!t) return;
    if(t.id === "pref-select"){ diff("select"); return; }
    if(t.id === "sort"){ send("sort_change", { sort_by: t.value }); return; }
  }, true);

  /* 検索は入力が落ち着いてから1回だけ送る */
  var timer;
  document.addEventListener("input", function(e){
    if(!e.target || e.target.id !== "q") return;
    clearTimeout(timer);
    timer = setTimeout(function(){
      var v = (e.target.value || "").trim();
      if(v.length >= 2){ send("search", { search_term: v.slice(0,80), result_count: resultCount() }); }
    }, 1200);
  }, true);

  /* お問い合わせフォームの送信（入力内容そのものは送らない） */
  document.addEventListener("submit", function(e){
    if(!e.target || e.target.id !== "contact-form") return;
    var k = $("c-type");
    send("contact_submit", { kind: k ? (k.value || "") : "" });
  }, true);

  /* どのセクションまで読まれたか */
  if(window.IntersectionObserver){
    var seen = {};
    var io = new IntersectionObserver(function(list){
      list.forEach(function(en){
        var id = en.target.id;
        if(en.isIntersecting && id && !seen[id]){
          seen[id] = 1;
          send("view_section", { section: id });
        }
      });
    }, { threshold: 0.35 });
    document.querySelectorAll("section[id]").forEach(function(s){ io.observe(s); });
  }
})();
</script>
<!--GA4-TRACK-END-->"""


# --- CSP: GA4 を通すために必要な最小限の追加先 ---
# セキュリティ強化(コミット 4221709)で default-src 'none' を敷いてあるため、
# 何も足さないと計測タグは無言でブロックされる。追加はGoogleの解析ドメインだけに限定する。
CSP_ADD = {
    "script-src": ["https://www.googletagmanager.com"],
    "img-src": ["https://www.googletagmanager.com", "https://*.google-analytics.com"],
    "connect-src": ["https://*.google-analytics.com",
                    "https://*.analytics.google.com",
                    "https://*.googletagmanager.com"],
}
CSP_RE = re.compile(r'(<meta http-equiv="Content-Security-Policy" content=")([^"]*)(">)')


def patch_csp(html):
    """CSP \u306b GA4 \u306e\u9001\u4fe1\u5148\u3092\u8db3\u3059\uff08\u51aa\u7b49\u30fb\u3059\u3067\u306b\u3042\u308c\u3070\u4f55\u3082\u3057\u306a\u3044\uff09\u3002"""
    m = CSP_RE.search(html)
    if not m:
        return html  # CSP \u3092\u6301\u305f\u306a\u3044\u30da\u30fc\u30b8\u306f\u305d\u306e\u307e\u307e
    parts = [d.strip() for d in m.group(2).split(";") if d.strip()]
    table = []
    for d in parts:
        toks = d.split()
        table.append([toks[0], toks[1:]])
    names = [t[0] for t in table]
    for directive, adds in CSP_ADD.items():
        if directive in names:
            row = table[names.index(directive)]
        else:
            # default-src \u3092\u5f15\u304d\u7d99\u3044\u3060\u4e0a\u3067\u65b0\u8a2d\u3059\u308b
            base = table[names.index("default-src")][1] if "default-src" in names else []
            base = [b for b in base if b != "'none'"]
            row = [directive, list(base)]
            insert_at = names.index("default-src") + 1 if "default-src" in names else len(table)
            table.insert(insert_at, row)
            names = [t[0] for t in table]
        for a in adds:
            if a not in row[1]:
                row[1].append(a)
    new = "; ".join(t[0] + (" " + " ".join(t[1]) if t[1] else "") for t in table)
    return html[:m.start()] + m.group(1) + new + m.group(3) + html[m.end():]


PRIVACY_MARK = "data-ga-privacy"
PRIVACY_LINK = ('<p ' + PRIVACY_MARK + '><a href="./privacy.html">'
                '\u30d7\u30e9\u30a4\u30d0\u30b7\u30fc\u30dd\u30ea\u30b7\u30fc\u3000\u2192</a></p>')


def add_privacy_link(html):
    """\u30d5\u30c3\u30bf\u30fc\u306b privacy.html \u3078\u306e\u5c0e\u7dda\u3092\u8db3\u3059\uff08\u51aa\u7b49\uff09\u3002"""
    if PRIVACY_MARK in html:
        return html
    if "</footer>" not in html:
        raise SystemExit("[FAIL] </footer> \u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093")
    i = html.rindex("</footer>")
    fstart = html.rindex("<footer", 0, i)
    j = html.rfind("</div>", fstart, i)
    if j > fstart:
        return html[:j] + "  " + PRIVACY_LINK + "\n  " + html[j:]
    return html[:i] + "  " + PRIVACY_LINK + "\n  " + html[i:]


def _strip(html, begin, end):
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.S)
    return pat.sub("", html)


def inject(html, ga_id):
    if not re.match(r"^G-[A-Za-z0-9]+$", ga_id):
        raise SystemExit("[FAIL] 測定IDの形式が違います（G- で始まる必要があります）: " + ga_id)
    html = _strip(html, HEAD_BEGIN, HEAD_END)
    html = _strip(html, BODY_BEGIN, BODY_END)
    if "</head>" not in html or "</body>" not in html:
        raise SystemExit("[FAIL] </head> または </body> が見つかりません")
    html = patch_csp(html)
    html = html.replace("</head>", HEAD_TPL.format(id=ga_id) + "\n</head>", 1)
    i = html.rindex("</body>")
    html = html[:i] + BODY_TPL + "\n" + html[i:]
    # 検証
    for need in (HEAD_BEGIN, HEAD_END, BODY_BEGIN, BODY_END):
        if html.count(need) != 1:
            raise SystemExit("[FAIL] マーカー " + need + " が1個になっていません")
    if html.count("googletagmanager.com/gtag/js") != 1:
        raise SystemExit("[FAIL] gtag のタグが1個になっていません")
    return html


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="GA4 測定ID (G-XXXXXXXXXX)")
    ap.add_argument("--no-privacy-link", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    for f in a.files:
        src = open(f, encoding="utf-8").read()
        out = inject(src, a.id)
        if not a.no_privacy_link and not f.endswith("privacy.html"):
            out = add_privacy_link(out)
        open(f, "w", encoding="utf-8").write(out)
        print("[OK] {}  {} -> {} bytes".format(f, len(src.encode()), len(out.encode())))
