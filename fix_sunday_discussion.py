#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
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

def fix_sunday_discussion():
    """日曜討論の出演者情報を修正"""
    print("🔧 日曜討論の出演者情報を修正中...")
    
    # 日曜討論のJSONデータ
    sunday_discussion_data = {
        "event_id": "AkZgQAVzwAM",
        "broadcast_date": "2025-07-13",
        "channel": "1 NHK総合1..",
        "start_time": "202507130900",
        "end_time": "202507131020",
        "master_title": "日曜討論 投開票まで1週間 参院選の争点を問う",
        "program_title": "日曜討論 投開票まで1週間 参院選の争点を問う",
        "description": "今月２０日に迫る参院選の争点について与野党が徹底討論！▽コメの価格はどうなる？今後のコメ政策は▽「政治とカネ」の問題は▽アメリカとの関税交渉は▽選択的夫婦別姓は",
        "description_detail": "【出演】自由民主党幹事長・森山裕、立憲民主党幹事長・小川淳也、日本維新の会幹事長・岩谷良平、公明党幹事長・西田実仁、国民民主党幹事長・榛葉賀津也、日本共産党書記局長・小池晃、れいわ新選組代表・山本太郎、参政党代表・神谷宗幣、日本保守党事務総長・有本香、社会民主党副党首・大椿ゆうこ【司会】ＮＨＫ解説委員・山下毅、ＮＨＫアナウンサー・上原光紀",
        "genre": "ニュース／報道",
        "official_website": "https://www.nhk.jp/p/touron/ts/GG149Z2M64/",
        "channel_code": "NHKG-TKY",
        "performers": [
            {"talent_id": "172499", "name": "小川淳也", "link": "https://bangumi.org/talents/172499"},
            {"talent_id": "232855", "name": "西田実仁", "link": "https://bangumi.org/talents/232855"},
            {"talent_id": "355854", "name": "榛葉賀津也", "link": "https://bangumi.org/talents/355854"},
            {"talent_id": "138242", "name": "小池晃", "link": "https://bangumi.org/talents/138242"},
            {"talent_id": "139005", "name": "山本太郎", "link": "https://bangumi.org/talents/139005"},
            {"talent_id": "393994", "name": "神谷宗幣", "link": "https://bangumi.org/talents/393994"},
            {"talent_id": "238755", "name": "有本香", "link": "https://bangumi.org/talents/238755"},
            {"talent_id": "383312", "name": "山下毅", "link": "https://bangumi.org/talents/383312"},
            {"talent_id": "251462", "name": "上原光紀", "link": "https://bangumi.org/talents/251462"}
        ]
    }
    
    # description_detailから不足している出演者を抽出
    missing_performers = extract_missing_performers(sunday_discussion_data['description_detail'])
    
    print(f"📋 現在の出演者数: {len(sunday_discussion_data['performers'])}名")
    print(f"📋 不足している出演者数: {len(missing_performers)}名")
    
    # 不足している出演者を追加
    for performer in missing_performers:
        # 既存の出演者に含まれていない場合のみ追加
        existing_names = {p['name'] for p in sunday_discussion_data['performers']}
        if performer['name'] not in existing_names:
            # talent_idがない場合は仮のIDを生成
            performer['talent_id'] = f"extracted_{hash(performer['name']) % 1000000}"
            performer['link'] = f"https://bangumi.org/talents/{performer['talent_id']}"
            sunday_discussion_data['performers'].append(performer)
            print(f"  ➕ 追加: {performer['name']} ({performer['role']})")
    
    # performer_countを更新
    sunday_discussion_data['performer_count'] = len(sunday_discussion_data['performers'])
    
    print(f"\n📊 修正後の出演者数: {len(sunday_discussion_data['performers'])}名")
    
    # 修正されたデータを表示
    print(f"\n📋 修正後の出演者一覧:")
    for i, performer in enumerate(sunday_discussion_data['performers'], 1):
        print(f"  {i:2d}. {performer['name']} (ID: {performer['talent_id']})")
    
    # ファイルパスを生成
    file_path = f"2025-07-13/NHKG-TKY/2025-07-13-0900_NHKG-TKY_AkZgQAVzwAM.json"
    
    # Supabaseストレージに更新
    try:
        json_bytes = json.dumps(sunday_discussion_data, ensure_ascii=False, indent=2).encode('utf-8')
        supabase.storage.from_("json-backups").update(file_path, json_bytes)
        print(f"\n✅ 日曜討論の出演者情報を修正しました: {file_path}")
        
        # 修正されたJSONをローカルに保存
        with open("fixed_sunday_discussion.json", "w", encoding="utf-8") as f:
            json.dump(sunday_discussion_data, f, ensure_ascii=False, indent=2)
        print(f"💾 修正されたJSONをローカルに保存: fixed_sunday_discussion.json")
        
    except Exception as e:
        print(f"❌ ストレージ更新エラー: {e}")

def extract_missing_performers(description_detail):
    """description_detailから不足している出演者を抽出"""
    missing_performers = []
    
    # 【出演】セクションを抽出
    if '【出演】' in description_detail:
        start = description_detail.find('【出演】') + len('【出演】')
        end = description_detail.find('【', start)
        if end == -1:
            end = len(description_detail)
        performer_section = description_detail[start:end].strip()
        
        # 役職・名前のパターンを抽出
        pattern = r'([^・]+)・([^、]+)'
        matches = re.findall(pattern, performer_section)
        
        # 現在の出演者リスト
        current_performers = [
            "小川淳也", "西田実仁", "榛葉賀津也", "小池晃", "山本太郎", 
            "神谷宗幣", "有本香", "山下毅", "上原光紀"
        ]
        
        for role, name in matches:
            name = name.strip()
            if name not in current_performers:
                missing_performers.append({
                    'name': name,
                    'role': role.strip()
                })
    
    return missing_performers

if __name__ == '__main__':
    fix_sunday_discussion() 