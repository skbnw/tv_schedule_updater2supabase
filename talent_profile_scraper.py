# talent_profile_scraper.py
# このファイルをリポジトリのルートに保存してください

import requests
import time
import re
import os
import json
from bs4 import BeautifulSoup
from supabase import create_client, Client
from datetime import datetime
from typing import Dict, List, Optional
import logging

# 環境変数から設定を取得
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Supabase接続
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class TalentProfileScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.errors = []
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # ログ設定
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def get_talents_to_process(self, offset: int = 0, limit: int = 50):
        """処理対象のタレントを取得"""
        
        try:
            # 既存プロフィールがないタレントのみ取得
            query = '''
            SELECT t.talent_id, t.name, t.link 
            FROM talents t 
            LEFT JOIN talent_profiles tp ON t.talent_id = tp.talent_id 
            WHERE tp.talent_id IS NULL 
            ORDER BY t.talent_id 
            LIMIT {} OFFSET {}
            '''.format(limit, offset)
            
            # SQLクエリ実行（実際のSupabaseでは適切なクエリメソッドを使用）
            talents = supabase.table('talents').select('talent_id, name, link').limit(limit).offset(offset).execute()
            
            self.logger.info(f"処理対象: {len(talents.data)}件 (オフセット: {offset})")
            return talents.data
            
        except Exception as e:
            self.logger.error(f"タレントデータ取得エラー: {str(e)}")
            return []
    
    def scrape_talent_profile(self, talent_id: str, talent_link: str, talent_name: str) -> Optional[Dict]:
        """個別タレントのプロフィール取得"""
        
        try:
            self.logger.info(f"取得中: {talent_name} (ID: {talent_id})")
            
            response = self.session.get(talent_link, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 基本データ構造
            profile_data = {
                'talent_id': talent_id,
                'source_url': talent_link,
                'scraped_at': datetime.now().isoformat()
            }
            
            # 名前と読み方を抽出
            self._extract_name_info(soup, profile_data)
            
            # 基本情報を抽出
            self._extract_basic_info(soup, profile_data)
            
            # プロフィール画像
            img_element = soup.find('img', class_='talent_img')
            if img_element and img_element.get('src'):
                profile_data['profile_image_url'] = img_element['src']
            
            # ジャンル、特技、趣味、芸歴を抽出
            self._extract_profile_details(soup, profile_data)
            
            # 完成度スコアを計算
            profile_data['profile_completeness'] = self._calculate_completeness(profile_data)
            
            return profile_data
            
        except Exception as e:
            error_info = {
                'talent_id': str(talent_id),
                'talent_name': talent_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            self.errors.append(error_info)
            self.logger.error(f"エラー - {talent_name}: {str(e)}")
            return None
    
    def _extract_name_info(self, soup, profile_data):
        """名前情報を抽出"""
        name_element = soup.find('li', text=re.compile(r'名前：'))
        if name_element:
            name_text = name_element.get_text()
            name_match = re.search(r'名前：\s*(.+?)（(.+?)）', name_text)
            if name_match:
                profile_data['full_name'] = name_match.group(1).strip()
                profile_data['reading'] = name_match.group(2).strip()
    
    def _extract_basic_info(self, soup, profile_data):
        """基本情報を抽出"""
        # 情報要素を検索
        info_element = soup.find('li', string=re.compile(r'情報：'))
        if not info_element:
            info_spans = soup.find_all('span', string=re.compile(r'情報：'))
            if info_spans:
                info_element = info_spans[0].parent
        
        if info_element:
            info_text = info_element.get_text()
            
            # 生年月日
            birth_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', info_text)
            if birth_match:
                year, month, day = birth_match.groups()
                profile_data['birth_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 星座
            zodiac_match = re.search(r'(おひつじ座|おうし座|ふたご座|かに座|しし座|おとめ座|てんびん座|さそり座|いて座|やぎ座|みずがめ座|うお座)', info_text)
            if zodiac_match:
                profile_data['zodiac_sign'] = zodiac_match.group(1)
            
            # 血液型
            blood_match = re.search(r'([ABO]B?)型', info_text)
            if blood_match:
                profile_data['blood_type'] = blood_match.group(1) + '型'
            
            # 身長
            height_match = re.search(r'(\d+)cm', info_text)
            if height_match:
                profile_data['height_cm'] = int(height_match.group(1))
            
            # 出身地
            birthplace_match = re.search(r'([^0-9]+?)出身', info_text)
            if birthplace_match:
                profile_data['birthplace'] = birthplace_match.group(1).strip()
    
    def _extract_profile_details(self, soup, profile_data):
        """ジャンル、特技、趣味、芸歴を抽出"""
        
        # ジャンル
        genre_element = soup.find('p', id='ジャンル')
        if not genre_element:
            genre_spans = soup.find_all('span', string=re.compile(r'ジャンル：'))
            if genre_spans:
                genre_element = genre_spans[0].find_next('p')
        
        if genre_element:
            genre_text = genre_element.get_text().strip()
            genres = [g.strip() for g in re.split(r'[\s\u3000\n]+', genre_text) if g.strip()]
            profile_data['genres'] = genres
        
        # 特技
        skill_element = soup.find('p', id='特技')
        if not skill_element:
            skill_spans = soup.find_all('span', string=re.compile(r'特技：'))
            if skill_spans:
                skill_element = skill_spans[0].find_next('p')
        
        if skill_element:
            skill_text = skill_element.get_text().strip()
            skills = [s.strip() for s in re.split(r'[\s\u3000\n]+', skill_text.replace('　', ' ')) if s.strip()]
            profile_data['skills'] = skills
        
        # 趣味
        hobby_element = soup.find('p', id='趣味')
        if not hobby_element:
            hobby_spans = soup.find_all('span', string=re.compile(r'趣味：'))
            if hobby_spans:
                hobby_element = hobby_spans[0].find_next('p')
        
        if hobby_element:
            hobby_text = hobby_element.get_text().strip()
            hobbies = [h.strip() for h in re.split(r'[\s\u3000\n]+', hobby_text.replace('　', ' ')) if h.strip()]
            profile_data['hobbies'] = hobbies
        
        # 芸歴
        career_element = soup.find('p', id='芸歴')
        if not career_element:
            career_spans = soup.find_all('span', string=re.compile(r'芸歴：'))
            if career_spans:
                career_element = career_spans[0].find_next('p')
        
        if career_element:
            profile_data['career_history'] = career_element.get_text().strip()
    
    def _calculate_completeness(self, profile_data: Dict) -> float:
        """プロフィール完成度を計算"""
        score = 0.0
        max_score = 10.0
        
        if profile_data.get('full_name'): score += 1.0
        if profile_data.get('reading'): score += 0.5
        if profile_data.get('birth_date'): score += 1.5
        if profile_data.get('birthplace'): score += 1.0
        if profile_data.get('profile_image_url'): score += 0.5
        if profile_data.get('genres'): score += 2.0
        if profile_data.get('skills'): score += 1.0
        if profile_data.get('hobbies'): score += 1.0
        if profile_data.get('career_history'): score += 1.5
        
        return min(1.0, score / max_score)
    
    def save_profile(self, profile_data: Dict) -> bool:
        """プロフィールをデータベースに保存"""
        
        try:
            result = supabase.table('talent_profiles').upsert(profile_data).execute()
            
            # タグ生成と保存
            tags = self._generate_tags(profile_data)
            if tags:
                self._save_tags(tags)
            
            self.logger.info(f"保存成功: ID {profile_data['talent_id']} (完成度: {profile_data.get('profile_completeness', 0):.2f})")
            return True
            
        except Exception as e:
            self.logger.error(f"保存エラー: ID {profile_data['talent_id']} - {str(e)}")
            return False
    
    def _generate_tags(self, profile_data: Dict) -> List[Dict]:
        """プロフィールからタグを生成"""
        tags = []
        talent_id = str(profile_data['talent_id'])  # 文字列として扱う
        
        # ジャンルからタグ生成
        if 'genres' in profile_data:
            for genre in profile_data['genres']:
                tag_name = self._normalize_genre_tag(genre)
                if tag_name:
                    tags.append({
                        'talent_id': talent_id,
                        'tag_name': tag_name,
                        'tag_category': 'profession',
                        'confidence_score': 1.0
                    })
        
        return tags
    
    def _normalize_genre_tag(self, genre: str) -> Optional[str]:
        """ジャンルをタグに正規化"""
        
        mapping = {
            '女優': 'actress',
            '俳優': 'actor',
            'タレント': 'talent',
            '歌手': 'singer',
            '声優': 'voice_actor',
            'アナウンサー': 'announcer',
            'NHKアナウンサー': 'nhk_announcer',
            '政治家': 'politician',
            'お笑い芸人': 'comedian',
            'モデル': 'model'
        }
        
        return mapping.get(genre)
    
    def _save_tags(self, tags: List[Dict]):
        """タグを保存"""
        # タグ保存の実装
        # 実際の実装ではtalent_tagsテーブルも必要
        pass
    
    def send_discord_notification(self):
        """Discord通知を送信"""
        
        if not DISCORD_WEBHOOK_URL:
            return
        
        try:
            embed = {
                "title": "🎭 タレントプロフィール取得完了",
                "color": 0x00ff00 if self.stats['failed'] == 0 else 0xff9900,
                "fields": [
                    {"name": "📊 処理結果", "value": f"```成功: {self.stats['success']}件\n失敗: {self.stats['failed']}件\n合計: {self.stats['total']}件```"},
                    {"name": "📈 成功率", "value": f"{(self.stats['success'] / max(1, self.stats['total'])) * 100:.1f}%"}
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            requests.post(DISCORD_WEBHOOK_URL, json=payload)
            
        except Exception as e:
            self.logger.error(f"Discord通知エラー: {str(e)}")
    
    def save_error_log(self):
        """エラーログを保存"""
        
        if not self.errors:
            return
        
        filename = f"talent_scraping_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'total_errors': len(self.errors),
            'stats': self.stats,
            'errors': self.errors
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"エラーログ保存: {filename}")
    
    def process_talents(self, offset: int = 0, limit: int = 50):
        """メイン処理"""
        
        start_time = datetime.now()
        self.logger.info(f"タレントプロフィール取得開始 (オフセット: {offset}, 件数: {limit})")
        
        # 処理対象を取得
        talents = self.get_talents_to_process(offset, limit)
        self.stats['total'] = len(talents)
        
        # 各タレントを処理
        for i, talent in enumerate(talents):
            talent_id = talent['talent_id']
            talent_name = talent['name']
            talent_link = talent['link']
            
            self.logger.info(f"[{i + 1}/{len(talents)}] 処理中: {talent_name}")
            
            # プロフィール取得
            profile_data = self.scrape_talent_profile(talent_id, talent_link, talent_name)
            
            if profile_data:
                # データベース保存
                if self.save_profile(profile_data):
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1
            else:
                self.stats['failed'] += 1
            
            # レート制限
            time.sleep(1.5)
        
        # 完了処理
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() / 60
        
        self.logger.info(f"処理完了: {execution_time:.1f}分")
        self.logger.info(f"結果: 成功 {self.stats['success']}件, 失敗 {self.stats['failed']}件")
        
        # エラーログ保存
        self.save_error_log()
        
        # Discord通知
        self.send_discord_notification()

def main():
    """メイン実行関数"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='タレントプロフィール取得')
    parser.add_argument('--mode', choices=['test', 'batch', 'full'], default='test',
                       help='実行モード')
    parser.add_argument('--offset', type=int, default=0,
                       help='処理開始オフセット')
    
    args = parser.parse_args()
    
    # 処理件数を決定
    if args.mode == 'test':
        limit = 10
    elif args.mode == 'batch':
        limit = 50
    else:  # full
        limit = 1000  # 大量処理時の上限
    
    # 処理実行
    scraper = TalentProfileScraper()
    scraper.process_talents(offset=args.offset, limit=limit)

if __name__ == "__main__":
    main()
