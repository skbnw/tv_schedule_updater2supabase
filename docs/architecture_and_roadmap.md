# T-Clip 検索UI・通知基盤 — アーキテクチャとロードマップ

政治家・有識者のテレビ出演を追跡し、キーワード検索・ウォッチ通知まで発展させるための設計メモ。

## 1. 全体構成（Supabase Pro ＋ Fly.io）

```
[Fly.io] Streamlit UI（閲覧・キーワード検索）──読取──┐
[Fly.io] Python スクレイパ（日次 cron, 既存資産）──書込─┤
                                                       [Supabase Postgres (Pro)]
[Supabase] pg_cron: アーカイブ / 通知差分 ──────────────┘
                     └─ pg_net ─→ Discord / メール 通知
```

- **データ本体**: Supabase（マネージド Postgres, Pro）。移設不要。
- **UI**: Streamlit を Fly.io（Tokyo/nrt）にコンテナデプロイ。`webapp/` 参照。
- **データ取得**: 既存の Python スクレイパ（`tv_schedule_updater.py`）。Edge Function へは移さない（下記 §4）。
- **GCP は不採用**: 現規模では運用負担が増えるだけ。将来 BigQuery 連携や大規模公開時に再検討。

## 2. データモデル（要点）

- `talents` →(`program_talent_appearances`)→ `programs`（詳細）。FK 制約あり。
- 番組は日次でローテーションし、古い分は `programs_archive` / `programs_epg_archive` へ退避。
  過去の出演・番組も辿るには稼働テーブルとアーカイブの **UNION が必須**。
- `talent_tags`（14種、`politician` / `weather_forecaster` / `disaster_prevention_specialist` / `financial_planner` 等）で
  カテゴリ絞り込み。
- `start_time` は `YYYYMMDDHHMM` のテキスト。表示時にパース。

## 3. 実装済み（本番 Supabase に反映済み）

| 種別 | 名称 | 内容 |
|---|---|---|
| 拡張 | `pgroonga` | 日本語全文検索（辞書不要の TokenBigram） |
| 索引 | `idx_programs_pgroonga` | `programs` の (title‖desc‖detail) 連結への式インデックス |
| 索引 | `idx_programs_archive_pgroonga` | `programs_archive` 同上 |
| ビュー | `v_program_search` | 稼働＋アーカイブ統合＋`search_text`。`security_invoker=on` |
| ビュー | `v_talent_appearances` | タレント→出演番組（統合、重複0）。`security_invoker=on` |
| RPC | `app_categories()` / `app_talents(p_tag)` / `app_appearances(p_talent_id)` / `app_search(p_query,p_politician_only,p_limit)` | アプリがAPI経由で呼ぶ。`SECURITY DEFINER`＋固定`search_path`。pgroonga検索も内包 |

**接続方式**: UIは **Supabase API（PostgREST）経由**で RPC を呼ぶ（DBパスワード不要・HTTPSのみ）。
サーバ用 `secret` キーを使用（RLSをバイパス。サーバサイド前提）。DB直結（psycopg2）は不採用にした
（Flyでの pooler/IPv4 問題回避・鍵管理の一本化のため）。

**検索性能**: `search_text &@~ '国会 消費税'` が 18万件横断で ~30ms（従来のシーケンシャルスキャンは ~24,000ms）。

> ⚠️ 多カラム pgroonga 索引（`ARRAY[col,...] &@~`）はこの環境ではインデックスが効かず、
> **連結式への単一インデックス**でのみプッシュダウンした。式は
> `coalesce(program_title,'')||' '||coalesce(description,'')||' '||coalesce(description_detail,'')`。
> クエリ側も同じ式（またはビューの `search_text`）で叩くこと。

### 政治番組の抽出
2軸併用が有効:
1. **キーワード（pgroonga）**: 政治・国会・選挙・内閣・与党・野党・政党名・政治家名 等。現状 ~6,972件ヒット。
2. **構造フィルタ**: `genre ~ '報道|ニュース'` ＋ `politician` タグ出演者。

## 4. データ取得: なぜ Edge Function ではないか

`pg_cron + Edge Function` はスクレイパ本体には**不採用**。

- Edge Function は Deno/TypeScript 専用 → 既存 Python スクレイパの全面書き直しが必要。
- 実行時間上限（数分）があり、14局×複数日の HTML パースは超過リスク。
- pg_cron/pg_net は「引き金」に過ぎず、重い処理の実行場所が別途要る。

**採用方針（役割分担）**:

| 処理 | 実行場所 | 理由 |
|---|---|---|
| 番組表スクレイプ（重い/Python） | Fly.io scheduled machine | 書き直し不要・時間制限なし・常時利用可 |
| 古いレコードのアーカイブ | pg_cron（純SQL化） | DB内完結・軽量 |
| ウォッチ差分→通知発火 | pg_cron + pg_net | 未来出演を検知し Webhook を叩くだけ |

## 5. ロードマップ

### Phase 1 — 閲覧＋検索（実装中）
- [x] pgroonga 検索基盤・統合ビュー（済）
- [x] Streamlit アプリ（`webapp/app.py`）: 人物から探す／キーワード検索
- [ ] Fly.io デプロイ（`webapp/` の Dockerfile / fly.toml）

### Phase 2 — ウォッチリスト＋出演予定通知
- [ ] `app_users`（Supabase Auth）、`watchlist(user_id, talent_id)`、`notified(user_id, event_id)`（二重通知防止）
- [ ] pg_cron: `broadcast_date >= today` の新規出演のうち、ウォッチ対象かつ未通知を抽出 → pg_net で通知 → `notified` に記録
- [ ] 通知先は既存 Discord を流用、将来メール / LINE へ拡張

### Phase 3 — スケジューラ移行と安定化
- [ ] スクレイパを GitHub Actions → Fly scheduled machine へ（60日無効化・遅延の解消）
- [ ] アーカイブ処理を pg_cron 化

## 6. 将来的な可能性: P520（放送波受信系）との統合

現在このDBは **インターネット経由（番組表サイトのスクレイピング）** でデータを取得している。
一方、別マシン **Lenovo ThinkStation P520（Linux Mint / Quadro P2000 ×2）** では、
**テレビ放送波を直接受信**し、以下を取得している:

- 放送波由来の**番組表データ**（EPG）
- **番組本編の MP4**（録画）
- **字幕データ**（クローズドキャプション）

**統合イメージ（将来）**:
- 放送波EPG と スクレイピングEPG を **`event_id` / 放送日時＋チャンネルで突合**し、相互補完（欠損・表記ゆれの補正）。
- 番組レコードに **録画MP4・字幕へのポインタ**（ストレージパスや Supabase Storage の署名URL）を紐付け。
  → UI から「出演番組の該当シーンを視聴」「字幕全文検索」まで拡張可能。
- **字幕全文検索**は pgroonga と極めて相性が良い（本設計の索引方式をそのまま字幕テーブルへ適用可能）。
  発言単位の検索・政治家の発言抽出（WhisperX 書き起こしとも接続）へ発展。
- P520 は GPU 潤沢のため、字幕・音声書き起こし・話者分離の**重い前処理を担当**し、
  成果物（テキスト/メタデータ）を Supabase に集約する分担が自然。

> この統合は Phase 2/3 と独立に進められる。まずは番組メタデータのキー設計（`event_id` 体系の共通化）を
> P520 側と揃えておくと、後の突合コストが最小になる。

## 7. セキュリティ／運用メモ（アドバイザ結果）

DDL 適用後の Supabase アドバイザ（security）で以下を検出。**いずれも検索機能とは別軸**:

- `extension_in_public`（WARN, 今回起因）: `pgroonga` が `public` スキーマにある。
  専用スキーマ（例 `extensions`）へ移すのが推奨（任意・低リスク）。
- `rls_policy_always_true`（WARN, 既存）: `talent_profiles` / `talent_tags` / `talent_tag_relations` の
  INSERT/UPDATE/DELETE ポリシーが `true`。**一般公開ログインを入れる前に要見直し**（Phase 2 の前提）。
- `vulnerable_postgres_version`（WARN, 既存）: Postgres にセキュリティパッチあり。計画的にアップグレード推奨。

参考: <https://supabase.com/docs/guides/database/database-linter>
