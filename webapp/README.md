# T-Clip 出演トラッカー（Streamlit）

政治家・有識者のテレビ出演を追う閲覧UIと、番組表・番組詳細のキーワード検索（pgroonga）。

- **人物から探す**: カテゴリ（政治家など）→ タレント選択 → 出演一覧 → 番組詳細
- **キーワードで探す**: 全文検索で横断（`国会 消費税` など）。政治プリセット／政治家出演番組に限定も可

接続は **Supabase API（PostgREST）経由**で、DBパスワードは不要。pgroonga 検索を含む処理は
Supabase 側の RPC（`app_search` など）で実行する。DB側の索引・ビュー・RPCは
`docs/architecture_and_roadmap.md` の §3 を参照（構築済み）。

## ローカル実行

```bash
cd webapp
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# macOS/Linux: source .venv/bin/activate && pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml       # 値を設定
streamlit run app.py
```

`.streamlit/secrets.toml`（.gitignore 済み）に以下を設定:

```toml
SUPABASE_URL = "https://<ref>.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."   # Project Settings > API keys の secret
```

環境変数でも可: `SUPABASE_URL` / `SUPABASE_SECRET_KEY`（secrets.toml より優先）。

> secret キーはサーバ用途のみ。クライアントへ公開しないこと。露出したらローテーション（再発行）する。

## Fly.io へデプロイ

```bash
cd webapp
fly launch --no-deploy
fly secrets set SUPABASE_URL="https://<ref>.supabase.co"
fly secrets set SUPABASE_SECRET_KEY="sb_secret_..."
fly deploy
```

- `auto_stop_machines=stop` / `min_machines_running=0` で無アクセス時は停止（コスト最小）。
- API経由（HTTPS）のみなので、DB直結の pooler/IPv4 問題は発生しない。

## 構成ファイル

| ファイル | 役割 |
|---|---|
| `app.py` | Streamlit 本体（supabase-py で RPC を呼ぶ） |
| `requirements.txt` | 依存（streamlit / supabase / pandas） |
| `Dockerfile` | Fly 用イメージ（8080） |
| `fly.toml` | Fly 設定（nrt/Tokyo, autostop） |
| `.streamlit/secrets.toml.example` | 接続情報のひな形 |
