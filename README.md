# tv_schedule_updater2supabase

システムアーキテクチャ
本システムは、GitHub Actionsをスケジューラ兼実行環境とし、Supabaseをバックエンドとして活用することで、サーバーレスな自動化を実現しています。

コード スニペット

graph TD
    subgraph A[自動実行環境: GitHub Actions]
        runner[スケジュール実行<br>(毎日 AM 4:00 JST)] --> script[Pythonスクリプト<br>tv_schedule_updater.py]
    end

    subgraph B[データソース]
        website[bangumi.org]
    end

    subgraph C[BaaS: Supabase]
        db[(PostgreSQLデータベース)]
        storage[(ファイルストレージ)]
    end
    
    subgraph D[通知]
        discord[Discord Webhook]
    end

    script -- 1. スクレイピング --> website
    script -- 2. データ登録/更新 --> db
    script -- 3. JSONバックアップ --> storage
    script -- 4. 実行結果を通知 --> discord
データベース設計 (ER図)
データは3つの主要テーブルと、それらを結びつける中間テーブルによって構成されています。これにより、データの整合性を保ちつつ、柔軟な検索を可能にしています。

コード スニペット

erDiagram
    programs {
        TEXT event_id PK
        TEXT program_title
        TEXT broadcast_date
        TEXT start_time
        TEXT description_detail
    }

    program_talent_appearances {
        BIGINT id PK
        TEXT program_event_id FK
        TEXT talent_id FK
    }

    talents {
        TEXT talent_id PK
        TEXT name
        TEXT link
    }

    programs ||--o{ program_talent_appearances : "出演"
    talents  ||--o{ program_talent_appearances : "出演"
技術スタック
言語: Python 3.10+

主要ライブラリ: requests, beautifulsoup4, supabase-py

データベース: Supabase (PostgreSQL)

ファイルストレージ: Supabase Storage

自動化/CI/CD: GitHub Actions

通知: Discord Webhooks

## 主要機能

### 番組データ取得
- 地上波7局 + BS7局 = 計14局の番組表を自動取得
- 7日分の番組データを毎日更新
- 番組詳細情報（タイトル、説明、ジャンル等）を取得

### 出演者情報抽出（強化版）
- HTMLの複数セクションから出演者情報を抽出
  - `ul.addition`セクション
  - `ul.talent_panel`セクション
- `description_detail`からも出演者情報を抽出
- 役職と名前の組み合わせを正確に解析
- 重複除去とデータ統合

### データ管理
- Supabaseデータベースへの自動登録
- JSONファイルのバックアップ保存
- 古いデータの自動アーカイブ
- 出演者情報の継続的な補完

セットアップ手順
1. 前提条件
Python 3.10以上

Git

2. リポジトリのクローン
Bash

git clone https://github.com/あなたのユーザー名/tv_schedule_updater2supabase.git
cd tv_schedule_updater2supabase
3. Python環境のセットアップ
仮想環境の作成を推奨します。

Bash

# 仮想環境の作成
python -m venv venv
# 仮想環境のアクティベート
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 必要なライブラリのインストール
pip install -r requirements.txt
requirements.txtファイルの内容:

supabase
requests
beautifulsoup4
4. Supabaseのセットアップ
Supabaseで新規プロジェクトを作成します。

左メニューの「Storage」アイコンから、「New bucket」をクリックし、json-backupsという名前のバケットを作成します（Public bucketのチェックはオフのまま）。

左メニューの「SQL Editor」を開き、「New query」で以下のSQLを全て実行して、必要なテーブルを作成します。

テーブル作成用SQL（クリックで展開）
5. GitHub Secretsの設定
自動実行のために、リポジトリに以下の秘密情報を登録します。

GitHubリポジトリのページで「Settings」>「Secrets and variables」>「Actions」を開きます。

「New repository secret」ボタンを押し、以下の3つを登録します。

SUPABASE_URL: SupabaseプロジェクトのURL（Settings > API）

SUPABASE_KEY: Supabaseプロジェクトのservice_roleキー（Settings > API）

DISCORD_WEBHOOK_URL: 通知を送りたいDiscordチャンネルのWebhook URL

使用方法
自動実行
本プロジェクトは、以下のGitHub Actionsワークフローにより自動実行されます：

- **TV Program Scraper** (main.yml):
  - **目的**: 毎日AM4時に実行され、地上波・BS計14局の番組情報を取得してSupabase（DBおよびStorage）に保存するメインアクション。
  - **内容**: `tv_schedule_updater.py` を実行。
- **Supplement Appearances from JSON** (supplement_appearances.yml):
  - **目的**: 毎日AM3時に実行され、ストレージに保存されたJSONバックアップから最新の出演者情報を抽出し、DBの出演者テーブルを補完する。
  - **内容**: `supplement_appearances_from_json.py` を実行。
- **Talent Profile Scraper** (talent_profile_scraper.yml):
  - **目的**: 不定期または手動で実行され、DBに登録されたタレントのリンクから詳細なプロフィール情報をスクレイピングして `talent_profiles` テーブルを構築する。
  - **内容**: `talent_profile_scraper.py` を実行。

また、GitHubのActionsタブから手動で実行することも可能です（`workflow_dispatch` 対応）。

## 障害・メンテナンス記録

### 2026年3月30日：bangumi.orgの仕様変更による同期停止
- **事象**: 番組データの取得が停止し、GitHub Actionsが正常終了（30秒程度）するがデータが更新されない状態となった。
- **原因**: データソースである `bangumi.org` が、デフォルトのPython `requests` ライブラリの `User-Agent` を検知して `403 Forbidden` を返すように変更されたため。
- **修正内容**: 
  - 全リクエストにブラウザを装う `User-Agent` ヘッダーを追加。
  - GitHub Actions上でデバッグしやすくするため、致命的エラー時に終了コード `1` を返すように修正。
  - Supabase Storageへのアップロード時に `upsert` オプションが真偽値だとエラーになる環境（GitHub Actions等）に対応するため、文字列 `"true"` に修正。
- **復旧対応**: 3月30日分からの不足データを手動実行（遡り設定）によりリカバリ済み。

ローカルでのテスト実行
ローカル環境でスクリプトをテスト実行する場合は、ターミナルで環境変数を設定した上で実行します。

Windows (PowerShell) の場合:

PowerShell

$env:SUPABASE_URL="https://..."
$env:SUPABASE_KEY="ey..."
$env:DISCORD_WEBHOOK_URL="https://..."

python tv_schedule_updater.py
スクリプト一覧
tv_schedule_updater.py: このプロジェクトのメインスクリプト。データの収集、登録、バックアップ、アーカイブを全て行います。出演者情報の抽出機能が強化されており、HTMLの複数セクションとdescription_detailから出演者情報を取得します。

supplement_appearances_from_json.py: ローカルに保存されたJSONファイルから不足している出演者情報を抽出し、データベースに補完するユーティリティ。

update_existing_json.py: 既存のローカルJSONファイルを更新し、不足している出演者情報をWebから再スクレイピングして補完するユーティリティ。

update_supabase_storage.py: SupabaseストレージのJSONファイルを一括で更新し、不足している出演者情報を補完するユーティリティ。

talent_profile_scraper.py: タレントのプロフィール情報を取得するスクリプト。

import_local_json.py: ローカルに保存された多数のJSONファイルを一括でデータベースにインポートするためのユーティリティ。

migrate_from_sqlite.py: 古いSQLiteデータベースからデータを移行するためのユーティリティ。

update_channel_codes.py: データベース内の既存のchannel_codeを更新するためのユーティリティ。

## 最近の改善点

### 出演者情報抽出の強化（2025年1月）
- `description_detail`からの出演者情報抽出機能を追加
- 複数ソースからの出演者情報統合処理を改善
- 日曜討論などの複雑な番組でも正確な出演者情報を取得

### 自動補完システムの導入
- 既存データの出演者情報を自動で補完
- SupabaseストレージのJSONファイルも自動更新
- データ品質の継続的な向上

## 将来の展望
トランスクリプト連携: 音声認識などで生成した番組のトランスクリプトデータをMongoDBに格納。

LLMによる要約: SupabaseのメタデータとMongoDBのトランスクリプトデータを組み合わせ、LLMに与えることで高品質な番組概要メモを自動生成する。

データ分析基盤: 蓄積したデータを活用し、出演者ごとの出演傾向や番組内容のトレンドなどを分析する。

ライセンス
MIT


付録：チャンネルコード一覧 (Appendix: Channel Code List)
本システムで定義されているCHANNEL_MAPPINGの一覧です。スクリプトは、Webサイトから取得したチャンネル名に、この表の「検索用チャンネル名」が含まれているかを判断し、対応する「チャンネルコード」を付与します。

地上波（関東）
チャンネルコード

検索用チャンネル名

NHKG-TKY

NHK総合

NHKE-TKY

NHKEテレ

NTV-TKY

日テレ

TV-ASAHI-TKY

テレビ朝日

TBS-TKY

TBS

TV-TOKYO-TKY

テレ東

FUJI-TV-TKY

フジテレビ

TOKYO-MX

TOKYO

TVS

テレ玉

CTC

チバテレ

TVK

tvk


Google スプレッドシートにエクスポート
BS放送
チャンネルコード

検索用チャンネル名

NHK-BS

ＮＨＫ　ＢＳ

BS-NTV

BS日テレ

BS-ASAHI

BS朝日

BS-TBS

BS-TBS

BS-TV-TOKYO

ＢＳテレ東

BS-FUJI

BSフジ

BS11

BS11

BS12-TWELLV

BS12

BS-YOSHIMOTO

ＢＳよしもと

OUJ-TV-BS

放送大学

WOWOW-PRIME-BS

WOWOWプ

WOWOW-LIVE-BS

WOWOWライブ

WOWOW-CINEMA-BS

WOWOWシネマ

WOWOW-PLUS-BS

WOWOWプラス

STAR-CH-BS

スターｃｈ

JSPORTS-1-BS

J SPORTS 1

JSPORTS-2-BS

J SPORTS 2

JSPORTS-3-BS

J SPORTS 3

JSPORTS-4-BS

J SPORTS 4

GREEN-CH-BS

グリーンチャンネル

ANIMAX-BS

BSアニマックス

TSURIVISION-BS

BS釣りビジョン

DISNEY-CH-BS

ディズニーch

NIHON-EIGA-BS

日本映画専門ch


Google スプレッドシートにエクスポート
その他
チャンネルコード

検索用チャンネル名

JCOM-BS

J:COM


