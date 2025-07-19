#!/usr/bin/env python3
"""
番組詳細ページの正しいURLを特定するテストスクリプト
"""

import requests
from bs4 import BeautifulSoup

def test_url(url, description):
    """URLをテストして結果を表示"""
    print(f"\n🔗 テスト: {description}")
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"   ステータス: {response.status_code}")
        print(f"   サイズ: {len(response.text)}文字")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # タイトルを確認
            title = soup.find('title')
            if title:
                print(f"   タイトル: {title.text[:100]}...")
            
            # 出演者情報の存在を確認
            addition = soup.find("ul", class_="addition")
            talent_panel = soup.find("ul", class_="talent_panel")
            talent_links = soup.find_all("a", href=lambda x: x and "/talents/" in x)
            
            print(f"   ul.addition: {'あり' if addition else 'なし'}")
            print(f"   ul.talent_panel: {'あり' if talent_panel else 'なし'}")
            print(f"   タレントリンク: {len(talent_links)}個")
            
            if talent_links:
                print("   最初の3つのタレントリンク:")
                for i, link in enumerate(talent_links[:3]):
                    print(f"     {i+1}. {link.get('href')} - {link.text.strip()}")
            
            return True
        else:
            print(f"   ❌ エラー: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ 例外: {e}")
        return False

def main():
    """メイン処理"""
    event_id = "AkbAQAYlYAM"
    
    print("🚀 番組詳細ページのURLテストを開始します")
    print(f"📺 対象番組: チコちゃんに叱られる！")
    print(f"🆔 Event ID: {event_id}")
    
    # テストするURLパターン
    test_urls = [
        (f"https://bangumi.org/tv_events/seasons?season_id={event_id}", "基本パターン"),
        (f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=x", "from=x付き"),
        (f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=fb", "from=fb付き"),
        (f"https://bangumi.org/tv_events/seasons?season_id={event_id}&from=line", "from=line付き"),
        (f"https://bangumi.org/tv_events/{event_id}", "直接アクセス"),
        (f"https://bangumi.org/tv_events/seasons/{event_id}", "seasons/付き"),
        (f"https://bangumi.org/programs/{event_id}", "programs/付き"),
        (f"https://bangumi.org/tv_events/seasons?program_id={event_id}", "program_idパラメータ"),
    ]
    
    success_count = 0
    
    for url, description in test_urls:
        if test_url(url, description):
            success_count += 1
    
    print(f"\n📊 テスト結果:")
    print(f"  成功: {success_count}/{len(test_urls)}")
    
    if success_count == 0:
        print("❌ 有効なURLが見つかりませんでした")
        print("💡 サイトの構造が変更されている可能性があります")

if __name__ == '__main__':
    main() 