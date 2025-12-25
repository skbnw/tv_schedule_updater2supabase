# 簡易実行スクリプト（対話なし）
# 使用方法: .\run_supplement_simple.ps1

# 環境変数の確認
if (-not $env:SUPABASE_URL -or -not $env:SUPABASE_KEY) {
    Write-Host "❌ 環境変数が設定されていません" -ForegroundColor Red
    Write-Host "以下のコマンドで環境変数を設定してください:" -ForegroundColor Yellow
    Write-Host "  `$env:SUPABASE_URL='https://your-project.supabase.co'" -ForegroundColor Yellow
    Write-Host "  `$env:SUPABASE_KEY='your-service-role-key'" -ForegroundColor Yellow
    exit 1
}

# デフォルト設定
if (-not $env:TARGET_DAYS_BACK) {
    $env:TARGET_DAYS_BACK = "3"
}
if (-not $env:MAX_PROGRAMS) {
    $env:MAX_PROGRAMS = "2000"
}
if (-not $env:MAX_FILES) {
    $env:MAX_FILES = "100"
}

Write-Host "🚀 出演者情報補完スクリプトを実行します" -ForegroundColor Green
Write-Host "📅 対象: 過去$($env:TARGET_DAYS_BACK)日間" -ForegroundColor Cyan
Write-Host "📊 最大処理件数: $($env:MAX_PROGRAMS)件" -ForegroundColor Cyan
Write-Host "📄 最大ファイル数: $($env:MAX_FILES)件" -ForegroundColor Cyan

Write-Host "`n=== supplement_appearances_from_json.py を実行 ===" -ForegroundColor Yellow
python supplement_appearances_from_json.py

Write-Host "`n=== update_supabase_storage.py を実行 ===" -ForegroundColor Yellow
python update_supabase_storage.py

Write-Host "`n✅ 処理が完了しました！" -ForegroundColor Green

