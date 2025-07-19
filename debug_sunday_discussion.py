#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# 環境変数から設定を取得
def get_env_var(var_name, default=None):
    """環境変数を取得"""
    return os.getenv(var_name, default)

# Supabase設定
SUPABASE_URL = get_env_var('SUPABASE_URL')
SUPABASE_KEY = get_env_var('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 環境変数 SUPABASE_URL または SUPABASE_KEY が設定されていません")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def find_sunday_discussion():
    """07/13の日曜討論を検索"""
    print("🔍 07/13の日曜討論を検索中...")
    
    try:
        # NHKG-TKYチャンネルのファイル一覧を取得
        ch_path = "2025-07-13/NHKG-TKY"
        print(f"📂 パス: {ch_path}")
        
        files = supabase.storage.from_("json-backups").list(path=ch_path)
        print(f"📄 ファイル数: {len(files)}")
        
        if not files:
            print("❌ ファイルが見つかりませんでした")
            return
        
        sunday_discussion_files = []
        
        for file_info in files:
            if file_info.get('name', '').endswith('.json'):
                try:
                    file_path = f"{ch_path}/{file_info['name']}"
                    response = supabase.storage.from_("json-backups").download(file_path)
                    data = json.loads(response.decode('utf-8'))
                    
                    program_title = data.get('program_title', '')
                    if '日曜討論' in program_title:
                        sunday_discussion_files.append({
                            'file': file_info['name'],
                            'data': data
                        })
                        print(f"📺 発見: {file_info['name']}")
                        print(f"   タイトル: {program_title}")
                        
                except Exception as e:
                    print(f"❌ ファイル読み込みエラー: {e}")
        
        if sunday_discussion_files:
            print(f"\n📊 日曜討論ファイル数: {len(sunday_discussion_files)}")
            
            for i, program in enumerate(sunday_discussion_files):
                print(f"\n=== {i+1}番目のファイル ===")
                print(f"ファイル: {program['file']}")
                print(f"番組タイトル: {program['data'].get('program_title', '不明')}")
                print(f"出演者数: {len(program['data'].get('performers', []))}")
                
                performers = program['data'].get('performers', [])
                if performers:
                    print("出演者詳細:")
                    for j, performer in enumerate(performers):
                        print(f"  {j+1}. {performer.get('name', '不明')} (役: {performer.get('role', '不明')})")
                else:
                    print("⚠️ 出演者情報なし")
                
                # event_idを取得して再スクレイピングを試行
                event_id = program['data'].get('event_id')
                if event_id:
                    print(f"\n🔄 event_id: {event_id} で再スクレイピングを試行...")
                    retry_scraping(event_id, program['data'].get('program_title', ''))
                
        else:
            print("❌ 日曜討論が見つかりませんでした")
            
            # その日の全番組タイトルを表示
            print(f"\n📋 {ch_path} の全番組:")
            for file_info in files[:20]:  # 最初の20件のみ表示
                if file_info.get('name', '').endswith('.json'):
                    try:
                        file_path = f"{ch_path}/{file_info['name']}"
                        response = supabase.storage.from_("json-backups").download(file_path)
                        data = json.loads(response.decode('utf-8'))
                        print(f"  - {data.get('program_title', '不明')}")
                    except:
                        pass
        
    except Exception as e:
        print(f"❌ 検索エラー: {e}")

def retry_scraping(event_id, program_title):
    """指定されたevent_idで再スクレイピングを試行"""
    print(f"🔗 再スクレイピング: {event_id}")
    
    # 複数のURLパターンを試行
    url_patterns = [
        f"https://bangumi.org/tv_events/seasons?season_id={event_id}",
        f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=x",
        f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=fb",
        f"https://bangumi.org/tv_events/{event_id}",
        f"https://bangumi.org/tv_events/seasons/{event_id}"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for i, url in enumerate(url_patterns):
        try:
            print(f"  🔗 試行 {i+1}: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"  ✅ ステータス: {response.status_code}")
                print(f"  📄 ページサイズ: {len(response.text)}文字")
                
                # HTMLを解析して出演者を抽出
                soup = BeautifulSoup(response.text, 'html.parser')
                performers = extract_performers(soup)
                
                if performers:
                    print(f"  👥 出演者検出: {len(performers)}名")
                    for j, performer in enumerate(performers[:5]):  # 最初の5名のみ表示
                        print(f"    {j+1}. {performer.get('name', '不明')} (役: {performer.get('role', '不明')})")
                    if len(performers) > 5:
                        print(f"    ... 他{len(performers) - 5}名")
                else:
                    print("  ⚠️ 出演者情報が見つかりませんでした")
                
                # HTMLを保存してデバッグ
                debug_filename = f"debug_sunday_discussion_{event_id}_{i+1}.html"
                with open(debug_filename, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"  💾 HTMLを保存: {debug_filename}")
                
                break
                
            else:
                print(f"  ❌ ステータス: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ エラー: {e}")

def extract_performers(soup):
    """HTMLから出演者情報を抽出"""
    performers = []
    
    # 複数のパターンで出演者を検索
    patterns = [
        # ul.addition パターン
        'ul.addition li',
        # ul.talent_panel パターン
        'ul.talent_panel li',
        # 出演者テキストを含む要素
        'div:contains("出演者")',
        'p:contains("出演者")',
        'span:contains("出演者")'
    ]
    
    for pattern in patterns:
        elements = soup.select(pattern)
        if elements:
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 1:
                    # 出演者名を抽出（簡単なパターンマッチング）
                    if '出演者' in text or '【' in text or '】' in text:
                        # テキストを解析して出演者名を抽出
                        extracted = parse_performer_text(text)
                        performers.extend(extracted)
    
    # 重複を除去
    unique_performers = []
    seen_names = set()
    for performer in performers:
        name = performer.get('name', '')
        if name and name not in seen_names:
            unique_performers.append(performer)
            seen_names.add(name)
    
    return unique_performers

def parse_performer_text(text):
    """テキストから出演者情報を解析"""
    performers = []
    
    # 出演者テキストのパターンを検索
    if '出演者' in text:
        # 出演者セクションを抽出
        performer_section = text.split('出演者')[1] if '出演者' in text else text
        
        # 【】で囲まれた役割と名前を抽出
        import re
        role_pattern = r'【([^】]+)】([^【]+)'
        matches = re.findall(role_pattern, performer_section)
        
        for role, names in matches:
            # 名前を分割（カンマ、スペースなどで区切られている場合）
            name_list = re.split(r'[、\s]+', names.strip())
            for name in name_list:
                if name and len(name) > 1:
                    performers.append({
                        'name': name.strip(),
                        'role': role.strip()
                    })
    
    return performers

if __name__ == '__main__':
    find_sunday_discussion() 