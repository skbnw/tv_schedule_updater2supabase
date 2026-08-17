# T-Clip 検索サイト

国会ネクサスの姉妹アプリ。地上波・BSの番組表と出演者を、キーワード／人物／議員名簿から検索する公開サイトです。

p330（LAN内の録画・字幕検索）の公開版にあたります。こちらは bangumi.org 由来の番組表＋出演リンクを Supabase で横断し、録画再生は含みません。

- **番組**: キーワード・日付・チャンネル（p330 相当＋pgroonga 全文検索）
- **出演者**: 名前／カテゴリから人物を選び、出演番組を一覧
- **議員**: 国会議員名簿のうちテレビ登場のある人 → 登場番組

接続は **Supabase API（PostgREST）経由**。secret キーは Node サーバだけが持ち、ブラウザには出しません。

## ローカル実行

```bash
cd webapp
copy .env.example .env   # 値を設定
npm install
node server.js
```

http://localhost:8080 を開きます。環境変数 `SUPABASE_URL` / `SUPABASE_SECRET_KEY`（または `SUPABASE_KEY`）でも可。

## Fly.io へデプロイ

```bash
cd webapp
fly secrets set SUPABASE_URL="https://<ref>.supabase.co"
fly secrets set SUPABASE_SECRET_KEY="sb_secret_..."
fly deploy
```

`auto_stop_machines=stop` / `min_machines_running=0` で無アクセス時は停止します。

## 構成

| ファイル | 役割 |
|---|---|
| `server.js` | Express。`/api/*` が Supabase RPC を代理 |
| `public/` | 検索 UI（番組 / 出演者 / 議員） |
| `Dockerfile` | Fly 用イメージ（8080） |
| `fly.toml` | Fly 設定（nrt/Tokyo, autostop） |
| `app.py` | 旧 Streamlit UI（ローカル検証用。デプロイ対象外） |

RPC・索引の前提は `docs/architecture_and_roadmap.md` の §3 を参照。
