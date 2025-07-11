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
本プロジェクトは、.github/workflows/main.ymlの定義に基づき、毎日午前4時（JST）に自動でtv_schedule_updater.pyを実行します。
また、GitHubのActionsタブから手動で実行することも可能です。

ローカルでのテスト実行
ローカル環境でスクリプトをテスト実行する場合は、ターミナルで環境変数を設定した上で実行します。

Windows (PowerShell) の場合:

PowerShell

$env:SUPABASE_URL="https://..."
$env:SUPABASE_KEY="ey..."
$env:DISCORD_WEBHOOK_URL="https://..."

python tv_schedule_updater.py
スクリプト一覧
tv_schedule_updater.py: このプロジェクトのメインスクリプト。データの収集、登録、バックアップ、アーカイブを全て行います。

import_local_json.py: ローカルに保存された多数のJSONファイルを一括でデータベースにインポートするためのユーティリティ。

migrate_from_sqlite.py: 古いSQLiteデータベースからデータを移行するためのユーティリティ。

update_channel_codes.py: データベース内の既存のchannel_codeを更新するためのユーティリティ。

将来の展望
トランスクリプト連携: 音声認識などで生成した番組のトランスクリプトデータをMongoDBに格納。

LLMによる要約: SupabaseのメタデータとMongoDBのトランスクリプトデータを組み合わせ、LLMに与えることで高品質な番組概要メモを自動生成する。

データ分析基盤: 蓄積したデータを活用し、出演者ごとの出演傾向や番組内容のトレンドなどを分析する。

ライセンス
MIT
