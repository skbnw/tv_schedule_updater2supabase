#!/usr/bin/env python3
"""
既存のJSONファイルを更新して出演者情報を追加するスクリプト
"""

import os
import json
import requests
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime

# 共通ヘッダー（ブラウザを装う）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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

def update_json_file(json_file_path):
    """JSONファイルを更新して出演者情報を追加"""
    try:
        # JSONファイルを読み込み
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📄 処理中: {json_file_path}")
        print(f"  📺 番組: {data.get('program_title', '不明')}")
        print(f"  📅 放送日: {data.get('broadcast_date', '不明')}")
        
        # 既に出演者情報がある場合はスキップ
        if data.get('performers') and len(data['performers']) > 0:
            print(f"  ✅ 既に出演者情報があります（{len(data['performers'])}名）")
            return False
        
        # 番組詳細ページから出演者情報を取得
        event_id = data.get('event_id')
        if not event_id:
            print(f"  ❌ event_idが見つかりません")
            return False
        
        # 正しいURL形式を生成（EPGページのhref形式に基づく）
        url = f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=x"
        print(f"  🔗 URL: {url}")
        
        try:
            res = requests.get(url, timeout=30, headers=HEADERS)
            res.raise_for_status()
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
                
                # JSONファイルを更新
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"  ✅ 出演者情報を追加しました（{len(performers_data)}名）")
                return True
            else:
                print(f"  ⚠️ 出演者情報が見つかりませんでした")
                return False
                
        except Exception as e:
            print(f"  ❌ ページ取得エラー: {e}")
            return False
            
    except Exception as e:
        print(f"❌ JSONファイル処理エラー: {e}")
        return False

def main():
    """メイン処理"""
    print("🚀 既存JSONファイルの出演者情報更新を開始します")
    
    # 現在のディレクトリのJSONファイルを検索
    json_files = [f for f in os.listdir('.') if f.endswith('.json') and 'NHKG-TKY' in f]
    
    if not json_files:
        print("❌ 更新対象のJSONファイルが見つかりません")
        return
    
    print(f"📋 更新対象: {len(json_files)}ファイル")
    
    updated_count = 0
    error_count = 0
    
    for json_file in json_files:
        try:
            if update_json_file(json_file):
                updated_count += 1
            else:
                error_count += 1
            
            # サーバーに負荷をかけないよう少し待機
            time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"❌ {json_file} の処理でエラー: {e}")
            error_count += 1
    
    print(f"\n📊 更新完了:")
    print(f"  ✅ 更新成功: {updated_count}件")
    print(f"  ❌ エラー: {error_count}件")
    print(f"  📋 総処理件数: {len(json_files)}件")

if __name__ == '__main__':
    main() 