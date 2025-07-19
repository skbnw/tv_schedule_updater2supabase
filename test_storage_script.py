#!/usr/bin/env python3
"""
ストレージスクリプトの動作テスト用
"""

import os
from datetime import datetime, timedelta

def get_env(key, default=None):
    v = os.environ.get(key)
    if v is None:
        return default
    return v

def main():
    """メイン処理"""
    print("🚀 ストレージスクリプトの動作テストを開始します")
    
    # 環境変数の確認
    SUPABASE_URL = get_env("SUPABASE_URL")
    SUPABASE_KEY = get_env("SUPABASE_KEY")
    
    print(f"📋 環境変数確認:")
    print(f"  SUPABASE_URL: {'設定済み' if SUPABASE_URL else '未設定'}")
    print(f"  SUPABASE_KEY: {'設定済み' if SUPABASE_KEY else '未設定'}")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("\n❌ 環境変数が設定されていません")
        print("以下のコマンドで環境変数を設定してください:")
        print("$env:SUPABASE_URL='https://your-project.supabase.co'")
        print("$env:SUPABASE_KEY='your-service-role-key'")
        return
    
    # 07/19を中心に前後6日分の日付を生成
    center_date = datetime(2025, 7, 19)
    target_dates = []
    
    for i in range(-6, 7):  # -6日から+6日
        target_date = center_date + timedelta(days=i)
        target_dates.append(target_date.strftime('%Y-%m-%d'))
    
    print(f"\n📅 対象期間: {target_dates[0]} 〜 {target_dates[-1]}")
    print(f"📋 対象日数: {len(target_dates)}日")
    
    print("\n✅ 環境変数が正しく設定されています")
    print("実際のスクリプトを実行する準備ができました")
    print("python update_supabase_storage.py を実行してください")

if __name__ == '__main__':
    main() 