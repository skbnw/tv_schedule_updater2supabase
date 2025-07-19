#!/usr/bin/env python3
"""
SupabaseストレージのJSONファイルを更新して出演者情報を追加するスクリプト
07/19を中心に前後6日分（07/13〜07/25）を対象
"""

import os
import json
import requests
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from supabase import create_client, Client

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
    print("SUPABASE_URL と SUPABASE_KEY を設定してください")
    print("例: $env:SUPABASE_URL='https://your-project.supabase.co'")
    print("例: $env:SUPABASE_KEY='your-service-role-key'")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_text(text):
    """テキストのクリーニング"""
    if text is None:
        return ""
    return str(text).strip()

def safe_extract_talent_info(link_element):
    """安全なタレント情報抽出"""
    try:
        name = clean_text(link_element.get_text(strip=True))
        href = link_element.get("href", "")
        
        if not name or not href:
            return None
        
        if href.rstrip("/").endswith("talents"):
            return None
            
        talent_id = href.rstrip("/").split("/")[-1].split("?")[0]
        if not talent_id.isdigit():
            return None
            
        full_link = "https://bangumi.org" + href if href.startswith("/") else href
        
        return {
            "talent_id": talent_id,
            "name": name,
            "link": full_link
        }
    except Exception as e:
        print(f"⚠️ タレント情報抽出エラー: {e}")
        return None

def extract_performers_from_html(soup_detail):
    """HTMLから出演者情報を抽出（改良版）"""
    performers = {}
    
    try:
        # 方法1: ul.addition内の出演者情報を取得
        addition_section = soup_detail.find("ul", class_="addition")
        if addition_section:
            performer_text = addition_section.get_text(strip=True)
            print(f"  🔍 出演者テキスト検出: {performer_text[:100]}...")
            
            performer_links = addition_section.find_all("a", href=lambda x: x and "/talents/" in x)
            for link in performer_links:
                talent_info = safe_extract_talent_info(link)
                if talent_info:
                    performers[talent_info["name"]] = talent_info["link"]
        
        # 方法2: ul.talent_panel内のタレント情報を取得
        talent_panel = soup_detail.find("ul", class_="talent_panel")
        if talent_panel:
            talent_links = talent_panel.find_all("a", href=lambda x: x and "/talents/" in x)
            for link in talent_links:
                talent_info = safe_extract_talent_info(link)
                if talent_info:
                    performers[talent_info["name"]] = talent_info["link"]
        
        # 方法3: ページ全体からタレントリンクを取得（フォールバック）
        if not performers:
            all_talent_links = soup_detail.find_all("a", href=lambda x: x and "/talents/" in x)
            for link in all_talent_links:
                talent_info = safe_extract_talent_info(link)
                if talent_info:
                    performers[talent_info["name"]] = talent_info["link"]
        
        print(f"  👥 出演者検出: {len(performers)}名")
        if performers:
            for name in list(performers.keys())[:3]:
                print(f"    - {name}")
            if len(performers) > 3:
                print(f"    ... 他{len(performers) - 3}名")
        
    except Exception as e:
        print(f"⚠️ 出演者情報抽出エラー: {e}")
    
    return performers

# JSONバックアップストレージ名
STORAGE_BUCKET = "json-backups"

def get_storage_files(target_dates):
    """指定された日付のSupabaseストレージファイル一覧を取得"""
    files = []
    
    for date_str in target_dates:
        try:
            # 日付ディレクトリ内のチャンネルディレクトリ一覧を取得
            channel_dirs = supabase.storage.from_(STORAGE_BUCKET).list(path=date_str)
            
            if channel_dirs:
                for ch_dir in channel_dirs:
                    # typeが'folder'でなくても、ディレクトリとして扱う
                    ch_path = f"{date_str}/{ch_dir.get('name', '')}"
                    
                    # チャンネルディレクトリ内のJSONファイル一覧を取得
                    json_files = supabase.storage.from_(STORAGE_BUCKET).list(path=ch_path)
                    
                    for jf in json_files:
                        if jf.get('name', '').endswith('.json'):
                            file_path = f"{ch_path}/{jf['name']}"
                            files.append(file_path)
                            print(f"  📄 発見: {file_path}")
            
        except Exception as e:
            print(f"⚠️ {date_str}のファイル一覧取得エラー: {e}")
    
    return files

def download_and_update_json(file_path):
    """JSONファイルをダウンロードして出演者情報を更新"""
    try:
        print(f"\n📄 処理中: {file_path}")
        
        # ファイルをダウンロード
        response = supabase.storage.from_(STORAGE_BUCKET).download(file_path)
        data = json.loads(response.decode('utf-8'))
        
        print(f"  📺 番組: {data.get('program_title', '不明')}")
        print(f"  📅 放送日: {data.get('broadcast_date', '不明')}")
        
        # 既に出演者情報がある場合はスキップ
        if data.get('performers') and len(data['performers']) > 0:
            print(f"  ✅ 既に出演者情報があります（{len(data['performers'])}名）")
            return False, "既存データ"
        
        # 番組詳細ページから出演者情報を取得
        event_id = data.get('event_id')
        if not event_id:
            print(f"  ❌ event_idが見つかりません")
            return False, "event_idなし"
        
        # 複数のURLパターンを試す
        url_patterns = [
            f"https://bangumi.org/tv_events/seasons?season_id={event_id}",
            f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=x",
            f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=fb",
            f"https://bangumi.org/tv_events/{event_id}",
            f"https://bangumi.org/tv_events/seasons/{event_id}",
        ]
        
        performers_found = False
        
        for url in url_patterns:
            print(f"  🔗 試行: {url}")
            
            try:
                res = requests.get(url, timeout=30)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    print(f"  📄 ページサイズ: {len(res.text)}文字")
                    
                    # 出演者情報を抽出
                    performer_links = extract_performers_from_html(soup)
                    
                    if performer_links:
                        # 出演者情報をJSONに追加
                        performers_data = []
                        for name, link in performer_links.items():
                            talent_id = link.rstrip("/").split("/")[-1].split("?")[0]
                            performers_data.append({
                                "talent_id": talent_id,
                                "name": name,
                                "link": link
                            })
                        
                        data['performers'] = performers_data
                        data['performer_count'] = len(performers_data)
                        data['updated_at'] = datetime.now().isoformat()
                        
                        # 更新されたJSONをアップロード
                        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                        supabase.storage.from_(STORAGE_BUCKET).update(file_path, json_bytes)
                        
                        print(f"  ✅ 出演者情報を追加しました（{len(performers_data)}名）")
                        performers_found = True
                        break
                    else:
                        print(f"  ⚠️ 出演者情報が見つかりませんでした")
                else:
                    print(f"  ❌ ステータス: {res.status_code}")
                    
            except Exception as e:
                print(f"  ❌ エラー: {e}")
                continue
        
        if performers_found:
            return True, "更新成功"
        else:
            return False, "出演者情報なし"
            
    except Exception as e:
        print(f"❌ JSONファイル処理エラー: {e}")
        return False, f"エラー: {e}"

def main():
    """メイン処理"""
    print("🚀 Supabaseストレージの出演者情報更新を開始します")
    
    # 07/19を中心に前後6日分の日付を生成
    center_date = datetime(2025, 7, 19)
    target_dates = []
    
    for i in range(-6, 7):  # -6日から+6日
        target_date = center_date + timedelta(days=i)
        target_dates.append(target_date.strftime('%Y-%m-%d'))
    
    print(f"📅 対象期間: {target_dates[0]} 〜 {target_dates[-1]}")
    print(f"📋 対象日数: {len(target_dates)}日")
    
    # ストレージからファイル一覧を取得
    print("\n📂 ストレージからファイル一覧を取得中...")
    storage_files = get_storage_files(target_dates)
    
    if not storage_files:
        print("❌ 更新対象のJSONファイルが見つかりません")
        return
    
    print(f"\n📋 更新対象: {len(storage_files)}ファイル")
    
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    for file_path in storage_files:
        try:
            success, status = download_and_update_json(file_path)
            
            if success:
                updated_count += 1
            elif status == "既存データ":
                skipped_count += 1
            else:
                error_count += 1
            
            # サーバーに負荷をかけないよう少し待機
            time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"❌ {file_path} の処理でエラー: {e}")
            error_count += 1
    
    print(f"\n📊 更新完了:")
    print(f"  ✅ 更新成功: {updated_count}件")
    print(f"  ⏭️ スキップ: {skipped_count}件")
    print(f"  ❌ エラー: {error_count}件")
    print(f"  📋 総処理件数: {len(storage_files)}件")

if __name__ == '__main__':
    main() 