#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

def analyze_sunday_discussion():
    """日曜討論の出演者情報を分析"""
    
    # 提供されたJSONデータ
    data = {
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
    
    print("🔍 日曜討論の出演者情報分析")
    print("="*50)
    
    # description_detailから出演者を抽出
    description_detail = data.get('description_detail', '')
    print(f"📄 description_detail: {description_detail}")
    
    # 出演者セクションを抽出
    performer_section = extract_performer_section(description_detail)
    print(f"\n🎭 出演者セクション: {performer_section}")
    
    # 出演者を解析
    extracted_performers = parse_performers_from_text(performer_section)
    print(f"\n📋 抽出された出演者 ({len(extracted_performers)}名):")
    for i, performer in enumerate(extracted_performers, 1):
        print(f"  {i:2d}. {performer['name']} ({performer['role']})")
    
    # performers配列の出演者
    performers_array = data.get('performers', [])
    print(f"\n📋 performers配列の出演者 ({len(performers_array)}名):")
    for i, performer in enumerate(performers_array, 1):
        print(f"  {i:2d}. {performer['name']} (ID: {performer['talent_id']})")
    
    # 比較分析
    print(f"\n🔍 比較分析:")
    
    # description_detailに含まれるがperformers配列にない出演者
    extracted_names = {p['name'] for p in extracted_performers}
    array_names = {p['name'] for p in performers_array}
    
    missing_in_array = extracted_names - array_names
    missing_in_text = array_names - extracted_names
    
    if missing_in_array:
        print(f"❌ description_detailにあるがperformers配列にない出演者 ({len(missing_in_array)}名):")
        for name in missing_in_array:
            performer = next((p for p in extracted_performers if p['name'] == name), None)
            if performer:
                print(f"  - {name} ({performer['role']})")
    
    if missing_in_text:
        print(f"❌ performers配列にあるがdescription_detailにない出演者 ({len(missing_in_text)}名):")
        for name in missing_in_text:
            performer = next((p for p in performers_array if p['name'] == name), None)
            if performer:
                print(f"  - {name} (ID: {performer['talent_id']})")
    
    if not missing_in_array and not missing_in_text:
        print("✅ 出演者情報は一致しています")
    
    # 原因分析
    print(f"\n🤔 原因分析:")
    print("1. スクレイピング時に一部の出演者情報が取得できなかった可能性")
    print("2. サイトのHTML構造が複雑で、すべての出演者を抽出できなかった可能性")
    print("3. 一部の出演者が別のセクションに記載されていた可能性")
    
    # 改善提案
    print(f"\n💡 改善提案:")
    print("1. description_detailからも出演者情報を抽出する処理を追加")
    print("2. 複数のHTMLセクションから出演者を抽出する処理を強化")
    print("3. 出演者情報の重複チェックと統合処理を改善")

def extract_performer_section(text):
    """テキストから出演者セクションを抽出"""
    # 【出演】セクションを抽出
    if '【出演】' in text:
        start = text.find('【出演】') + len('【出演】')
        end = text.find('【', start)
        if end == -1:
            end = len(text)
        return text[start:end].strip()
    return text

def parse_performers_from_text(text):
    """テキストから出演者情報を解析"""
    performers = []
    
    # 役職・名前のパターンを抽出
    # 例: "自由民主党幹事長・森山裕"
    pattern = r'([^・]+)・([^、]+)'
    matches = re.findall(pattern, text)
    
    for role, name in matches:
        performers.append({
            'name': name.strip(),
            'role': role.strip()
        })
    
    return performers

if __name__ == '__main__':
    analyze_sunday_discussion() 