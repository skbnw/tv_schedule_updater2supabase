#!/usr/bin/env python3
"""
Supabaseストレージの構造を確認するスクリプト
"""

import os
from supabase import create_client, Client
import json

# 環境変数から設定を取得
def get_env(key, default=None):
    v = os.environ.get(key)
    if v is None:
        return default
    return v

# Supabase設定
SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Supabase環境変数が設定されていません")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_storage_buckets():
    """ストレージバケット一覧を確認"""
    print("🔍 ストレージバケット一覧を確認中...")
    
    try:
        buckets = supabase.storage.list_buckets()
        print(f"📦 バケット数: {len(buckets)}")
        
        for bucket in buckets:
            print(f"  - {bucket.name} (ID: {bucket.id})")
            
    except Exception as e:
        print(f"❌ バケット一覧取得エラー: {e}")

def check_bucket_contents(bucket_name):
    """指定されたバケットの内容を確認"""
    print(f"\n📂 バケット '{bucket_name}' の内容を確認中...")
    
    try:
        # ルートディレクトリの内容を取得
        files = supabase.storage.from_(bucket_name).list(path="")
        print(f"📄 ルートディレクトリのファイル数: {len(files)}")
        
        for file_info in files:
            print(f"  - {file_info.get('name', 'N/A')} (type: {file_info.get('type', 'N/A')})")
            
            # ディレクトリの場合は中身も確認
            if file_info.get('type') == 'folder':
                sub_path = file_info.get('name')
                try:
                    sub_files = supabase.storage.from_(bucket_name).list(path=sub_path)
                    print(f"    📁 {sub_path} 内のファイル数: {len(sub_files)}")
                    
                    for sub_file in sub_files[:5]:  # 最初の5件のみ表示
                        print(f"      - {sub_file.get('name', 'N/A')} (type: {sub_file.get('type', 'N/A')})")
                    
                    if len(sub_files) > 5:
                        print(f"      ... 他{len(sub_files) - 5}件")
                        
                except Exception as e:
                    print(f"    ❌ {sub_path} の内容取得エラー: {e}")
                    
    except Exception as e:
        print(f"❌ バケット内容取得エラー: {e}")

def check_specific_date(bucket_name, date_str):
    """特定の日付ディレクトリの内容を確認"""
    print(f"\n📅 {date_str} の内容を確認中...")
    
    try:
        # 日付ディレクトリ内のチャンネルディレクトリ一覧を取得
        channel_dirs = supabase.storage.from_(bucket_name).list(path=date_str)
        print(f"📺 チャンネル数: {len(channel_dirs)}")
        
        total_files = 0
        
        for ch_dir in channel_dirs:
            if ch_dir.get('name') and ch_dir.get('type') == 'folder':
                ch_path = f"{date_str}/{ch_dir['name']}"
                
                # チャンネルディレクトリ内のJSONファイル一覧を取得
                json_files = supabase.storage.from_(bucket_name).list(path=ch_path)
                json_count = len([f for f in json_files if f.get('name', '').endswith('.json')])
                
                print(f"  📡 {ch_dir['name']}: {json_count}件")
                total_files += json_count
                
                # 最初の3件のファイル名を表示
                for i, jf in enumerate(json_files[:3]):
                    if jf.get('name', '').endswith('.json'):
                        print(f"    - {jf['name']}")
                
                if json_count > 3:
                    print(f"    ... 他{json_count - 3}件")
        
        print(f"📊 {date_str} の総ファイル数: {total_files}件")
        return total_files
        
    except Exception as e:
        print(f"❌ {date_str} の内容取得エラー: {e}")
        return 0

def check_channel_detail(bucket_name, date_str, channel_name):
    """特定のチャンネルディレクトリの詳細を確認"""
    print(f"\n📡 {date_str}/{channel_name} の詳細確認中...")
    
    try:
        ch_path = f"{date_str}/{channel_name}"
        files = supabase.storage.from_(bucket_name).list(path=ch_path)
        
        print(f"📄 ファイル数: {len(files)}")
        
        for i, file_info in enumerate(files):
            print(f"  {i+1}. {file_info.get('name', 'N/A')} (type: {file_info.get('type', 'N/A')})")
            
            # 最初のファイルの内容を確認
            if i == 0 and file_info.get('name', '').endswith('.json'):
                try:
                    file_path = f"{ch_path}/{file_info['name']}"
                    response = supabase.storage.from_(bucket_name).download(file_path)
                    data = json.loads(response.decode('utf-8'))
                    
                    print(f"    📺 番組: {data.get('program_title', '不明')}")
                    print(f"    👥 出演者数: {len(data.get('performers', []))}")
                    
                    if data.get('performers'):
                        print("    🎭 出演者:")
                        for performer in data['performers'][:3]:
                            print(f"      - {performer.get('name', '不明')}")
                        if len(data['performers']) > 3:
                            print(f"      ... 他{len(data['performers']) - 3}名")
                    else:
                        print("    ⚠️ 出演者情報なし")
                        
                except Exception as e:
                    print(f"    ❌ ファイル読み込みエラー: {e}")
        
    except Exception as e:
        print(f"❌ チャンネル詳細取得エラー: {e}")

def check_specific_program(bucket_name, date_str, channel_name, program_keyword):
    """特定の番組の出演者情報を詳しく確認"""
    print(f"\n🔍 {date_str}/{channel_name} で「{program_keyword}」を検索中...")
    
    try:
        ch_path = f"{date_str}/{channel_name}"
        files = supabase.storage.from_(bucket_name).list(path=ch_path)
        
        found_programs = []
        
        for file_info in files:
            if file_info.get('name', '').endswith('.json'):
                try:
                    file_path = f"{ch_path}/{file_info['name']}"
                    response = supabase.storage.from_(bucket_name).download(file_path)
                    data = json.loads(response.decode('utf-8'))
                    
                    program_title = data.get('program_title', '')
                    if program_keyword in program_title:
                        found_programs.append({
                            'file': file_info['name'],
                            'data': data
                        })
                        
                except Exception as e:
                    print(f"    ❌ ファイル読み込みエラー: {e}")
        
        if found_programs:
            print(f"📺 見つかった番組数: {len(found_programs)}")
            
            for i, program in enumerate(found_programs):
                print(f"\n  {i+1}. {program['file']}")
                print(f"     📺 番組: {program['data'].get('program_title', '不明')}")
                print(f"     👥 出演者数: {len(program['data'].get('performers', []))}")
                
                performers = program['data'].get('performers', [])
                if performers:
                    print("     🎭 出演者詳細:")
                    for j, performer in enumerate(performers):
                        print(f"       {j+1}. {performer.get('name', '不明')} (役: {performer.get('role', '不明')})")
                else:
                    print("     ⚠️ 出演者情報なし")
                    
                # 元のHTMLデータがあれば確認
                if 'html_content' in program['data']:
                    print(f"     📄 HTMLデータあり: {len(program['data']['html_content'])}文字")
                else:
                    print("     📄 HTMLデータなし")
                    
        else:
            print(f"❌ 「{program_keyword}」を含む番組が見つかりませんでした")
            
            # その日の全番組タイトルを表示
            print(f"\n📋 {date_str}/{channel_name} の全番組:")
            for file_info in files[:10]:  # 最初の10件のみ表示
                if file_info.get('name', '').endswith('.json'):
                    try:
                        file_path = f"{ch_path}/{file_info['name']}"
                        response = supabase.storage.from_(bucket_name).download(file_path)
                        data = json.loads(response.decode('utf-8'))
                        print(f"  - {data.get('program_title', '不明')}")
                    except:
                        pass
        
    except Exception as e:
        print(f"❌ 番組検索エラー: {e}")

def main():
    """メイン処理"""
    print("🚀 Supabaseストレージ構造確認を開始します")
    
    # バケット一覧を確認
    check_storage_buckets()
    
    # 主要なバケットの内容を確認
    bucket_names = ["json-backups", "tv-schedules", "backups"]
    
    for bucket_name in bucket_names:
        check_bucket_contents(bucket_name)
    
    # 07/19を中心に前後6日分の詳細確認
    print("\n" + "="*50)
    print("📅 07/19を中心に前後6日分の詳細確認")
    print("="*50)
    
    center_date = "2025-07-19"
    target_dates = [
        "2025-07-13", "2025-07-14", "2025-07-15", "2025-07-16", "2025-07-17", "2025-07-18",
        center_date,
        "2025-07-20", "2025-07-21", "2025-07-22", "2025-07-23", "2025-07-24", "2025-07-25"
    ]
    
    total_files = 0
    
    for date_str in target_dates:
        file_count = check_specific_date("json-backups", date_str)
        total_files += file_count
    
    print(f"\n📊 対象期間の総ファイル数: {total_files}件")
    
    # 07/19のBS-ASAHIチャンネルの詳細確認
    print("\n" + "="*50)
    print("🔍 07/19のBS-ASAHIチャンネルの詳細確認")
    print("="*50)
    
    check_channel_detail("json-backups", "2025-07-19", "BS-ASAHI")
    
    # 07/13の日曜討論を検索
    print("\n" + "="*50)
    print("🔍 07/13の日曜討論を検索")
    print("="*50)
    
    # 主要なチャンネルで日曜討論を検索
    channels_to_check = ["NHKG-TKY", "NTV-TKY", "TBS-TKY", "CX-TKY", "TV-TOKYO-TKY", "MX-TKY"]
    
    for channel in channels_to_check:
        check_specific_program("json-backups", "2025-07-13", channel, "日曜討論")

if __name__ == '__main__':
    main() 