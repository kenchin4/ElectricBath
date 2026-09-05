# 電気風呂マップ

全国の電気風呂がある銭湯を、自分の足で回って記録した地図です。

公開URL: https://kenchin4.github.io/ElectricBath/

## このリポジトリの構成

| ファイル | 役割 |
|---|---|
| `index.html` | 公開されているページそのもの（データ込みの単体HTML） |
| `tools/build_public.py` | 原本（Claude Artifact）から `index.html` を作り直すスクリプト |
| `tools/inject_ga.py` | アクセス解析(GA4)タグの注入（build_public.py から呼ばれる） |
| `tools/inject_seo.py` | 検索エンジン向けメタ情報（title / description / canonical / OGP / JSON-LD）の注入と `sitemap.xml` / `robots.txt` の生成 |
| `sitemap.xml` / `robots.txt` | 検索エンジン向け（build_public.py が自動生成。手で編集しない） |
| `.nojekyll` | GitHub Pages の Jekyll 処理を無効化 |

## 更新の流れ

原本は Claude の Artifact「電気風呂マップ」です。`index.html` はそこから
**訪問日を落とした公開版**を機械的に生成したもので、直接手で編集しません。

1. Artifact 側でデータやUIを更新する
2. Artifact の全文HTMLを取得する
3. `python3 tools/build_public.py <取得したHTML> index.html` を実行
4. 差分を確認して commit / push（GitHub Pages が自動で再デプロイ）

`build_public.py` がやっている加工（公開版と原本の違い）:

- 各店舗データから `d`（訪問日）と `v`（訪問回数）を削除
- カードの訪問日表示と、その CSS を削除
- 並べ替えの「訪問が新しい順」オプションとソート処理を削除
- 「入湯した年数」は訪問日から計算していたので定数に置換
- フッターを「収録データの最終入湯日」→「データ最終更新」に変更
- `<head>`（title / OGP / favicon / Google Fonts）を付与して単体で開けるHTMLにする
- 検索エンジン向けの title / description / canonical / JSON-LD を入れ、`sitemap.xml` と `robots.txt` を書き出す

`profile.html` / `contact.html` / `privacy.html` は手で編集するページですが、`<head>` の
SEO 部分（`<!--SEO-BEGIN-->`〜`<!--SEO-END-->`）は `python3 tools/inject_seo.py profile.html contact.html privacy.html`
で入れ直せます（冪等）。

加工後に「訪問日が1件も残っていないか」を自動で検証しており、
Artifact 側の構造が変わって置換に失敗した場合はエラーで止まります。
