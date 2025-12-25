# ローカル実行ガイド

このドキュメントでは、出演者情報補完スクリプトをローカルPCで実行する方法を説明します。

## 前提条件

1. Python 3.10以上がインストールされていること
2. 必要なライブラリがインストールされていること
   ```powershell
   pip install -r requirements.txt
   ```
3. Supabaseの認証情報（URLとキー）を取得していること

## 環境変数の設定

PowerShellで以下のコマンドを実行して環境変数を設定します：

```powershell
$env:SUPABASE_URL='https://your-project.supabase.co'
$env:SUPABASE_KEY='your-service-role-key'
```

### 環境変数を永続化する場合

PowerShellのプロファイルに追加するか、`.env`ファイルを使用する方法があります。

## 実行方法

### 方法1: 対話型スクリプト（推奨）

```powershell
.\run_supplement_local.ps1
```

このスクリプトは、処理対象日付や処理件数を対話形式で指定できます。

### 方法2: 簡易実行スクリプト

```powershell
.\run_supplement_simple.ps1
```

このスクリプトは、デフォルト設定（過去3日間、最大2000件）で実行します。

### 方法3: 直接実行

環境変数を設定した後、直接Pythonスクリプトを実行できます：

```powershell
# 環境変数の設定
$env:SUPABASE_URL='https://your-project.supabase.co'
$env:SUPABASE_KEY='your-service-role-key'
$env:TARGET_DAYS_BACK='3'
$env:MAX_PROGRAMS='2000'
$env:MAX_FILES='100'

# スクリプトの実行
python supplement_appearances_from_json.py
python update_supabase_storage.py
```

### 特定日付を処理する場合

```powershell
$env:TARGET_DATES='2025-01-20,2025-01-21'
python supplement_appearances_from_json.py
python update_supabase_storage.py
```

## 環境変数の説明

| 環境変数 | 説明 | デフォルト値 |
|---------|------|-------------|
| `SUPABASE_URL` | SupabaseプロジェクトのURL | （必須） |
| `SUPABASE_KEY` | Supabaseのservice_roleキー | （必須） |
| `TARGET_DATES` | 処理対象日付（カンマ区切り） | なし（TARGET_DAYS_BACKが使用される） |
| `TARGET_DAYS_BACK` | 過去何日分を処理するか | 7 |
| `MAX_PROGRAMS` | 最大処理件数（supplement_appearances_from_json.py） | 5000 |
| `MAX_FILES` | 最大ファイル数（update_supabase_storage.py） | 500 |

## 注意事項

1. **処理時間**: ファイル数が多い場合、処理に時間がかかります
2. **ネットワーク**: Supabaseへの接続と、Webスクレイピング（update_supabase_storage.py）にはインターネット接続が必要です
3. **レート制限**: Webスクレイピング時は、サーバーに負荷をかけないよう適切な間隔で処理されます
4. **エラー処理**: エラーが発生した場合、スクリプトはエラーメッセージを表示して続行します

## トラブルシューティング

### 環境変数が設定されていないエラー

```powershell
# 環境変数を確認
$env:SUPABASE_URL
$env:SUPABASE_KEY

# 設定されていない場合は設定
$env:SUPABASE_URL='https://your-project.supabase.co'
$env:SUPABASE_KEY='your-service-role-key'
```

### モジュールが見つからないエラー

```powershell
# 必要なライブラリをインストール
pip install -r requirements.txt
```

### 処理が遅い場合

- `MAX_PROGRAMS`や`MAX_FILES`を減らして処理件数を制限
- `TARGET_DAYS_BACK`を減らして処理日数を制限
- 特定日付のみを処理（`TARGET_DATES`を使用）

