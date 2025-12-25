# 出演者情報補完スクリプトのローカル実行用スクリプト
# 使用方法: .\run_supplement_local.ps1

Write-Host "🚀 出演者情報補完スクリプトをローカルで実行します" -ForegroundColor Green

# 環境変数の確認
if (-not $env:SUPABASE_URL) {
    Write-Host "❌ SUPABASE_URL環境変数が設定されていません" -ForegroundColor Red
    Write-Host "設定例: `$env:SUPABASE_URL='https://your-project.supabase.co'" -ForegroundColor Yellow
    exit 1
}

if (-not $env:SUPABASE_KEY) {
    Write-Host "❌ SUPABASE_KEY環境変数が設定されていません" -ForegroundColor Red
    Write-Host "設定例: `$env:SUPABASE_KEY='your-service-role-key'" -ForegroundColor Yellow
    exit 1
}

# 処理対象日付の指定（オプション）
$targetDates = Read-Host "処理対象日付をカンマ区切りで入力（空欄の場合は過去7日間）"
if ($targetDates) {
    $env:TARGET_DATES = $targetDates
    Write-Host "📅 対象日付: $targetDates" -ForegroundColor Cyan
} else {
    $daysBack = Read-Host "過去何日分を処理しますか？（デフォルト: 7）"
    if ($daysBack) {
        $env:TARGET_DAYS_BACK = $daysBack
    }
    Write-Host "📅 過去$($env:TARGET_DAYS_BACK)日間を処理します" -ForegroundColor Cyan
}

# 処理件数の指定（オプション）
$maxPrograms = Read-Host "最大処理件数（空欄の場合はデフォルト: 5000）"
if ($maxPrograms) {
    $env:MAX_PROGRAMS = $maxPrograms
}

Write-Host "`n=== supplement_appearances_from_json.py を実行 ===" -ForegroundColor Yellow
python supplement_appearances_from_json.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ supplement_appearances_from_json.py でエラーが発生しました" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== update_supabase_storage.py を実行 ===" -ForegroundColor Yellow
$maxFiles = Read-Host "最大処理ファイル数（空欄の場合はデフォルト: 500）"
if ($maxFiles) {
    $env:MAX_FILES = $maxFiles
}

python update_supabase_storage.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ update_supabase_storage.py でエラーが発生しました" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ 処理が完了しました！" -ForegroundColor Green

