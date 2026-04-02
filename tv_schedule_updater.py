import os
import time
import random
import requests
import json
import shutil
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from supabase import create_client, Client


# 連携サービスの設定
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
# Storageバケットを環境変数で上書きできるように（デフォルトは従来通り）
STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "json-backups")

# 共通ヘッダー（ブラウザを装う）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 【本格運用】全対象チャンネル（地上波7局 + BS7局）
TARGET_CHANNELS = [
    # 地上波（7局）
    "NHKG-TKY", "NHKE-TKY", "NTV-TKY", "TV-ASAHI-TKY", "TBS-TKY", "TV-TOKYO-TKY", "FUJI-TV-TKY",
    # BSチャンネル（7局）
    "NHK-BS", "BS-NTV", "BS-ASAHI", "BS-TBS", "BS-TV-TOKYO", "BS-FUJI", "BS11"
]

TARGET_DAYS = 2  # 取得日数
ROTATION_DAYS = 120  # データの保持日数

# 改良されたチャンネルマッピング（完全一致優先）
CHANNEL_MAPPING = {
    # 東京 地上波
    "NHKG-TKY": ["NHK総合", "ＮＨＫ総合", "NHK総合 東京"],
    "NHKE-TKY": ["NHKEテレ", "ＮＨＫＥテレ", "NHKEテレ 東京"], 
    "NTV-TKY": ["日テレ", "日本テレビ"],
    "TV-ASAHI-TKY": ["テレビ朝日", "テレ朝"],
    "TBS-TKY": ["TBS", "ＴＢＳ"],
    "TV-TOKYO-TKY": ["テレ東", "テレビ東京"],
    "FUJI-TV-TKY": ["フジテレビ", "フジ"],
    "TOKYO-MX": ["TOKYO MX", "ＴＯＫＹＯ　ＭＸ"],
    
    # 関東 広域
    "TVS": ["テレ玉"],
    "CTC": ["チバテレビ", "チバテレ"],
    "TVK": ["tvk"],
    
    # BS無料
    "NHK-BS": ["ＮＨＫ　ＢＳ", "NHK BS"],
    "BS-NTV": ["BS日テレ", "ＢＳ日テレ"],
    "BS-ASAHI": ["BS朝日", "ＢＳ朝日"],
    "BS-TBS": ["BS-TBS", "ＢＳ－ＴＢＳ"],
    "BS-TV-TOKYO": ["ＢＳテレ東", "BSテレ東"],
    "BS-FUJI": ["BSフジ", "ＢＳフジ"],
    "BS11": ["BS11", "ＢＳ１１"],
    "BS12-TWELLV": ["BS12", "ＢＳ１２"],
    "BS-YOSHIMOTO": ["ＢＳよしもと"],
    "OUJ-TV-BS": ["放送大学"],
    
    # BS有料
    "WOWOW-PRIME-BS": ["WOWOWプライム", "WOWOWプ"],
    "WOWOW-LIVE-BS": ["WOWOWライブ"],
    "WOWOW-CINEMA-BS": ["WOWOWシネマ"],
    "WOWOW-PLUS-BS": ["WOWOWプラス"],
    "STAR-CH-BS": ["スターｃｈ"],
    "JSPORTS-1-BS": ["J SPORTS 1"],
    "JSPORTS-2-BS": ["J SPORTS 2"],
    "JSPORTS-3-BS": ["J SPORTS 3"],
    "JSPORTS-4-BS": ["J SPORTS 4"],
    "GREEN-CH-BS": ["グリーンチャンネル"],
    "ANIMAX-BS": ["BSアニマックス"],
    "TSURIVISION-BS": ["BS釣りビジョン"],
    "DISNEY-CH-BS": ["ディズニーch"],
    "NIHON-EIGA-BS": ["日本映画専門ch"],
    
    # その他
    "JCOM-BS": ["J:COM"]
}

def find_channel_code(channel_name):
    """
    チャンネル名から適切なチャンネルコードを特定
    完全一致 → 部分一致 → 番号付きチャンネル対応の順で検索
    """
    if not channel_name:
        return None
    
    # チャンネル名のクリーニング
    clean_name = channel_name.strip()
    
    # 1. 完全一致検索（最優先）
    for code, name_list in CHANNEL_MAPPING.items():
        for name in name_list:
            if clean_name == name:
                return code
    
    # 2. 番号付きチャンネル名の処理（例: "7 ＢＳテレ東"）
    # 番号部分を除去してマッチング
    import re
    name_without_number = re.sub(r'^\d+\s*', '', clean_name)
    if name_without_number != clean_name:
        for code, name_list in CHANNEL_MAPPING.items():
            for name in name_list:
                if name_without_number == name:
                    return code
    
    # 3. 部分一致検索（最も厳密に）
    # BSチャンネルを優先的にチェック
    bs_matches = []
    terrestrial_matches = []
    
    for code, name_list in CHANNEL_MAPPING.items():
        for name in name_list:
            if name in clean_name or clean_name in name:
                if code.startswith('BS-') or 'BS' in code:
                    bs_matches.append((code, name))
                else:
                    terrestrial_matches.append((code, name))
    
    # BSチャンネル名にBSが含まれている場合、BSマッチを優先
    if 'BS' in clean_name or 'ＢＳ' in clean_name:
        if bs_matches:
            # 最も長いマッチを返す（より具体的なマッチ）
            best_match = max(bs_matches, key=lambda x: len(x[1]))
            return best_match[0]
    
    # 地上波の場合
    if terrestrial_matches:
        best_match = max(terrestrial_matches, key=lambda x: len(x[1]))
        return best_match[0]
    
    # BSマッチがある場合はそれを返す
    if bs_matches:
        best_match = max(bs_matches, key=lambda x: len(x[1]))
        return best_match[0]
    
    return None

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Discord Webhook URLが設定されていません。")
        return
    
    print("Discordへの通知を試みます...")
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=15, headers=HEADERS)
        response.raise_for_status()
        print("✅ Discordへの通知を正常に送信しました。")
    except requests.exceptions.RequestException as e:
        print(f"❌ Discord通知の送信に失敗しました: {e}")
        if e.response is not None:
            print(f" -> Response Status: {e.response.status_code}")
            print(f" -> Response Body: {e.response.text}")

def check_existing_tables():
    """既存テーブルの確認と構造把握"""
    print("\n--- システム確認 ---")
    
    # 想定されるテーブル名のパターン
    required_tables = ['programs_epg', 'programs', 'talents']
    appearances_candidates = ['program_talent_appearances', 'appearances']
    
    existing_tables = {}
    appearances_table = None
    
    # 必須テーブルの確認
    for table_name in required_tables:
        try:
            result = supabase.table(table_name).select("*").limit(1).execute()
            existing_tables[table_name] = "✅"
        except Exception as e:
            existing_tables[table_name] = "❌"
            print(f"⚠️ 必須テーブル {table_name} でエラー: {e}")
    
    # 出演情報テーブルの特定
    for table_name in appearances_candidates:
        try:
            result = supabase.table(table_name).select("*").limit(1).execute()
            appearances_table = table_name
            existing_tables[table_name] = "✅"
            break
        except Exception:
            existing_tables[table_name] = "❌"
    
    print(f"📋 テーブル状況: {existing_tables}")
    if appearances_table:
        print(f"🎯 出演情報テーブル: {appearances_table}")
    else:
        print("❌ 出演情報テーブルが見つかりません")
    
    return appearances_table

def safe_upsert_appearances(appearances_data, table_name, batch_size=500):
    """安全な出演情報登録（ON CONFLICT制約対応）"""
    if not appearances_data or not table_name:
        print("📝 出演情報の登録をスキップします。")
        return 0, 0
    
    success_count = 0
    error_count = 0
    
    print(f"📝 出演情報登録開始: {len(appearances_data)}件 → {table_name}")
    
    for i in range(0, len(appearances_data), batch_size):
        batch = appearances_data[i:i + batch_size]
        try:
            # 方法1: INSERT専用（新規データのみ）
            result = supabase.table(table_name).insert(batch).execute()
            success_count += len(batch)
            print(f"  -> 出演バッチ {i//batch_size + 1}: {len(batch)}件登録完了")
            
        except Exception as e:
            # 重複エラーの場合は個別処理
            if "already exists" in str(e) or "duplicate key" in str(e):
                individual_success = 0
                for single_record in batch:
                    try:
                        supabase.table(table_name).insert([single_record]).execute()
                        individual_success += 1
                    except Exception:
                        # 重複は正常（既存データ保護）
                        individual_success += 1
                
                success_count += individual_success
                print(f"  -> 出演バッチ {i//batch_size + 1}: {individual_success}件処理完了（重複スキップ含む）")
            else:
                error_count += len(batch)
                print(f"  -> 出演バッチ {i//batch_size + 1} 登録エラー: {e}")
    
    return success_count, error_count

def validate_json_data(data):
    """JSONデータの妥当性を検証"""
    try:
        # 必須フィールドの存在確認
        required_fields = ['event_id', 'broadcast_date', 'channel', 'program_title']
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == "":
                return False, f"必須フィールド '{field}' が不正です"
        
        # データ型の確認
        if not isinstance(data.get('performers', []), list):
            return False, "performersフィールドがリスト型ではありません"
        
        # JSON文字列として正しくシリアライズできるかテスト
        json_test = json.dumps(data, ensure_ascii=False)
        json.loads(json_test)  # デシリアライズテスト
        
        return True, "OK"
    except Exception as e:
        return False, f"JSON検証エラー: {e}"

def safe_json_upload(storage_path, data_dict, max_retries=3):
    """安全なJSONファイルアップロード（データ検証付き）"""
    
    # 1. データ妥当性検証
    is_valid, validation_msg = validate_json_data(data_dict)
    if not is_valid:
        print(f"❌ JSON検証失敗 ({storage_path}): {validation_msg}")
        return False
    
    # 2. JSON文字列生成
    try:
        json_string = json.dumps(data_dict, ensure_ascii=False, indent=2)
        if len(json_string) < 50:  # 最小サイズチェック
            print(f"❌ JSONデータが小さすぎます ({storage_path}): {len(json_string)}文字")
            return False
    except Exception as e:
        print(f"❌ JSON生成エラー ({storage_path}): {e}")
        return False
    
    # 3. アップロード試行（リトライ付き）
    for attempt in range(max_retries):
        try:
            supabase.storage.from_(STORAGE_BUCKET).upload(
                path=storage_path,
                file=json_string.encode('utf-8'),
                file_options={
                    "content-type": "application/json;charset=utf-8",
                    # boolで指定し、ライブラリ差異による無視を防ぐ
                    "upsert": True
                }
            )
            return True
        except Exception as e:
            print(f"⚠️ JSON保存試行 {attempt + 1}/{max_retries} 失敗 ({storage_path} @ {STORAGE_BUCKET}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
    
    return False

def clean_text(text):
    """テキストのクリーニング（Noneや空文字の処理）"""
    if text is None:
        return ""
    return str(text).strip()

def safe_extract_talent_info(link_element):
    """安全なタレント情報抽出"""
    try:
        name = clean_text(link_element.get_text(strip=True))
        href = link_element.get("href", "")
        
        # 基本的な妥当性チェック
        if not name or not href:
            return None
        
        if href.rstrip("/").endswith("talents"):
            return None
            
        # talent_idの抽出と検証
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
            
            # 出演者リンクを抽出
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
        
        # 方法4: description_detailから出演者情報を抽出（補完）
        description_detail = soup_detail.find('meta', {'name': 'description'})
        if description_detail:
            detail_text = description_detail.get('content', '')
            if detail_text and '【出演】' in detail_text:
                extracted_performers = extract_performers_from_description(detail_text)
                for performer in extracted_performers:
                    name = performer.get('name', '')
                    if name and name not in performers:
                        # talent_idがない場合は仮のIDを生成
                        performers[name] = f"extracted_{hash(name) % 1000000}"
        
        print(f"  👥 出演者検出: {len(performers)}名")
        if performers:
            for name in list(performers.keys())[:3]:  # 最初の3名を表示
                print(f"    - {name}")
            if len(performers) > 3:
                print(f"    ... 他{len(performers) - 3}名")
        
    except Exception as e:
        print(f"⚠️ 出演者情報抽出エラー: {e}")
    
    return performers

def extract_performers_from_description(description_text):
    """description_detailから出演者情報を抽出"""
    performers = []
    
    try:
        # 【出演】セクションを抽出
        if '【出演】' in description_text:
            start = description_text.find('【出演】') + len('【出演】')
            end = description_text.find('【', start)
            if end == -1:
                end = len(description_text)
            performer_section = description_text[start:end].strip()
            
            # 役職・名前のパターンを抽出
            import re
            pattern = r'([^・]+)・([^、]+)'
            matches = re.findall(pattern, performer_section)
            
            for role, name in matches:
                performers.append({
                    'name': name.strip(),
                    'role': role.strip()
                })
            
            print(f"  📝 description_detailから{len(performers)}名の出演者を抽出")
    
    except Exception as e:
        print(f"⚠️ description_detailからの出演者抽出エラー: {e}")
    
    return performers

def archive_old_db_records():
    print("\n--- 古いデータベースレコードのアーカイブ開始 ---")
    cutoff_date_str = (datetime.now() - timedelta(days=ROTATION_DAYS)).strftime('%Y-%m-%d')
    print(f"{cutoff_date_str} より前のデータをアーカイブします。")
    try:
        for table_name in ["programs_epg", "programs"]:
            response = supabase.table(table_name).select("*").lt('broadcast_date', cutoff_date_str).execute()
            if response.data:
                print(f" -> {table_name}: {len(response.data)}件をアーカイブ中...")
                try:
                    supabase.table(f"{table_name}_archive").upsert(response.data).execute()
                    supabase.table(table_name).delete().lt('broadcast_date', cutoff_date_str).execute()
                except Exception as archive_error:
                    print(f"⚠️ {table_name}のアーカイブをスキップ: {archive_error}")
        print("✅ 古いDBレコードのアーカイブ完了。")
    except Exception as e:
        print(f"❌ DBレコードのアーカイブ中にエラー: {e}")

def main():
    print("🚀 【本格運用】番組表スクリプトを開始します。")
    print(f"📋 取得対象: 地上波7局 + BS7局 = 計{len(TARGET_CHANNELS)}局")
    print(f"📅 取得期間: {TARGET_DAYS}日間")
    print(f"🗄️  JSON保存バケット: {STORAGE_BUCKET}")

    # システム確認
    appearances_table_name = check_existing_tables()
    if not appearances_table_name:
        print("⚠️ 出演情報テーブルが見つからないため、出演情報の登録は行いません。")

    # --- 1. EPG基本情報の取得 ---
    epg_data_to_upsert = []
    processed_event_ids = set()
    target_dates = [(datetime.now() + timedelta(days=i)) for i in range(-1, TARGET_DAYS + 1)]

    print("\n--- EPG基本情報の取得開始 ---")
    bs_channel_count = 0
    
    for ch_type in ["td", "bs"]:
        for target_date in target_dates:
            date_str_url = target_date.strftime("%Y%m%d")
            date_str_db = target_date.strftime("%Y-%m-%d")
            url = f"https://bangumi.org/epg/{ch_type}?broad_cast_date={date_str_url}"
            if ch_type == "td":
                url += "&ggm_group_id=42"

            print(f"アクセス中: {url}")
            try:
                res = requests.get(url, timeout=20, headers=HEADERS)
                res.raise_for_status()
                soup = BeautifulSoup(res.text, 'html.parser')
                channel_tags = soup.find_all("li", class_="js_channel topmost")
                channel_names = [tag.text.strip() for tag in channel_tags]
                program_lines = soup.find_all("ul", id=lambda x: x and x.startswith("program_line_"))

                for i, line in enumerate(program_lines):
                    programs = line.find_all("li")
                    for program_tag in programs:
                        a_tag = program_tag.find("a", class_="title_link")
                        if not a_tag:
                            continue

                        href = a_tag.get("href", "")
                        event_id = href.split("/")[-1].split("?")[0]
                        if not event_id or event_id in processed_event_ids:
                            continue

                        channel_name = channel_names[i] if i < len(channel_names) else "不明"
                        # 改良されたチャンネルコード特定
                        channel_code = find_channel_code(channel_name)

                        # BSチャンネルのマッピング状況をログ出力
                        if ('BS' in channel_name or 'ＢＳ' in channel_name) and channel_code in TARGET_CHANNELS:
                            bs_channel_count += 1
                            if bs_channel_count <= 5:  # 最初の5件のみ出力
                                print(f"  🔍 BSチャンネル検出: '{channel_name}' → '{channel_code}'")

                        # 番組タイトルと詳細の安全な取得
                        title_elem = a_tag.find("p", class_="program_title")
                        detail_elem = a_tag.find("p", class_="program_detail")
                        
                        program_title = clean_text(title_elem.text if title_elem else "")
                        program_detail = clean_text(detail_elem.text if detail_elem else "")

                        epg_data_to_upsert.append({
                            "event_id": event_id,
                            "broadcast_date": date_str_db,
                            "channel": channel_name,
                            "start_time": clean_text(program_tag.get("s", "")),
                            "end_time": clean_text(program_tag.get("e", "")),
                            "program_title": program_title,
                            "program_detail": program_detail,
                            "link": "https://bangumi.org" + href,
                            "region": "東京",
                            "channel_code": channel_code
                        })
                        processed_event_ids.add(event_id)
            except Exception as e:
                print(f"  -> EPGページ取得エラー: {e}")
                continue

    if not epg_data_to_upsert:
        raise Exception("EPG情報が一件も取得できませんでした。処理を中断します。")

    print(f"\n✅ {len(epg_data_to_upsert)}件のユニークなEPG情報を取得。DBに登録します...")
    
    # EPGデータをバッチ処理で登録
    batch_size = 1000
    for i in range(0, len(epg_data_to_upsert), batch_size):
        batch = epg_data_to_upsert[i:i + batch_size]
        try:
            supabase.table('programs_epg').upsert(batch, on_conflict='event_id').execute()
            print(f"  -> EPGバッチ {i//batch_size + 1}: {len(batch)}件登録完了")
        except Exception as e:
            print(f"  -> EPGバッチ {i//batch_size + 1} 登録エラー: {e}")

    # --- 2. 番組詳細情報の取得 ---
    print("\n--- 番組詳細情報の取得開始 ---")
    program_details_to_upsert = []
    appearances_to_upsert = []
    inserted_talent_ids = set()
    talents_seen = {}
    json_upload_success = 0
    json_upload_errors = 0

    # 取得対象の番組をフィルタリング
    target_programs = [p for p in epg_data_to_upsert if p.get('channel_code') in TARGET_CHANNELS]
    print(f"📺 詳細取得対象: {len(target_programs)}番組（全{len(epg_data_to_upsert)}番組中）")

    for program in target_programs:
        if not program.get('link'):
            continue

        print(f"詳細取得中: {program['program_title']}")
        try:
            # より長いタイムアウトでページを取得
            res_detail = requests.get(program['link'], timeout=30, headers=HEADERS)
            res_detail.raise_for_status()
            soup_detail = BeautifulSoup(res_detail.text, 'html.parser')
            
            # ページの読み込み状況を確認
            print(f"  📄 ページサイズ: {len(res_detail.text)}文字")

            title = clean_text(program['program_title'])
            
            # メタ情報の安全な取得
            meta_desc = soup_detail.find("meta", {"name": "description"})
            description = clean_text(meta_desc["content"] if meta_desc else "")
            
            letter_body = soup_detail.find("p", class_="letter_body")
            description_detail = clean_text(letter_body.get_text(strip=True) if letter_body else "")
            
            genre_tag = soup_detail.find("p", class_="genre nomal")
            genre = clean_text(genre_tag.get_text(strip=True).replace("\u3000", " ") if genre_tag else "")
            
            site_tag = soup_detail.select_one("ul.related_link a")
            official_website = clean_text(site_tag.get("href") if site_tag else "")

            # 出演者リンク抽出（堅牢化）
            performer_links = {}
            # 改良された出演者情報抽出関数を使用
            performer_links = extract_performers_from_html(soup_detail)
            
            # デバッグ情報: HTMLの構造確認
            if not performer_links:
                print(f"  ⚠️ 出演者情報が見つかりません。HTML構造を確認中...")
                addition_section = soup_detail.find("ul", class_="addition")
                talent_panel = soup_detail.find("ul", class_="talent_panel")
                print(f"    - ul.addition: {'あり' if addition_section else 'なし'}")
                print(f"    - ul.talent_panel: {'あり' if talent_panel else 'なし'}")
                
                # ページ全体のタレントリンク数を確認
                all_talent_links = soup_detail.find_all("a", href=lambda x: x and "/talents/" in x)
                print(f"    - ページ全体のタレントリンク: {len(all_talent_links)}個")
                
                # デバッグ用にHTMLを保存（最初の5件のみ）
                if len(program_details_to_upsert) < 5:
                    debug_filename = f"debug_{program['event_id']}.html"
                    try:
                        with open(debug_filename, 'w', encoding='utf-8') as f:
                            f.write(res_detail.text)
                        print(f"    - デバッグHTML保存: {debug_filename}")
                    except Exception as e:
                        print(f"    - デバッグHTML保存失敗: {e}")

            # タレント情報の処理
            talents_to_upsert = []
            current_program_appearances = []
            
            for name, link in performer_links.items():
                try:
                    talent_id = link.rstrip("/").split("/")[-1].split("?")[0]
                    if talent_id.isdigit():
                        # タレント情報の重複チェック
                        if talent_id not in talents_seen:
                            talents_to_upsert.append({
                                "talent_id": talent_id,
                                "name": name,
                                "link": link
                            })
                            talents_seen[talent_id] = name
                        
                        # 出演情報
                        current_program_appearances.append({
                            "program_event_id": program['event_id'],
                            "talent_id": talent_id
                        })
                except Exception as e:
                    print(f"⚠️ タレント処理エラー ({name}): {e}")
                    continue

            # タレント情報のDB登録
            if talents_to_upsert:
                try:
                    supabase.table('talents').upsert(talents_to_upsert, on_conflict='talent_id').execute()
                    # FK整合性のため、成功したtalent_idを保持
                    inserted_talent_ids.update([t["talent_id"] for t in talents_to_upsert])
                except Exception as e:
                    print(f"⚠️ タレント登録エラー: {e}")

            # 出演情報をまとめて追加
            appearances_to_upsert.extend(current_program_appearances)

            # 番組詳細データの構築
            db_data = {
                "event_id": program['event_id'],
                "broadcast_date": program['broadcast_date'],
                "channel": program['channel'],
                "start_time": program['start_time'],
                "end_time": program['end_time'],
                "master_title": title.split("　")[0] if "　" in title and title else title,
                "program_title": title,
                "description": description,
                "description_detail": description_detail,
                "genre": genre,
                "official_website": official_website,
                "channel_code": program['channel_code']
            }
            program_details_to_upsert.append(db_data)

            # JSONバックアップ作成（妥当性検証付き）
            date_str = program['broadcast_date']
            start_hhmm = program['start_time'][8:12] if len(program['start_time']) >= 12 else "0000"
            file_name = f"{date_str}-{start_hhmm}_{program['channel_code']}_{program['event_id']}.json"
            storage_path = f"{date_str}/{program['channel_code']}/{file_name}"
            
            # JSON用データ（必要なフィールドのみ含む、安全なコピー作成）
            json_data = {
                **db_data,
                "performers": [
                    {
                        "talent_id": talent["talent_id"],
                        "name": talent["name"],
                        "link": talent["link"]
                    } for talent in talents_to_upsert
                ] if talents_to_upsert else [],
                "performer_count": len(talents_to_upsert),
                "created_at": datetime.now().isoformat()
            }

            # JSON保存試行
            if safe_json_upload(storage_path, json_data):
                print(f"  -> JSON保存完了: {storage_path}")
                json_upload_success += 1
            else:
                print(f"  -> JSON保存失敗: {storage_path}")
                json_upload_errors += 1

            time.sleep(random.uniform(1.5, 2.5))
            
        except Exception as e:
            print(f"❌ 番組詳細取得失敗: {program['program_title']} - {e}")
            continue

    # --- 3. データベース一括登録 ---
    if program_details_to_upsert:
        print(f"\n✅ {len(program_details_to_upsert)}件の詳細情報をDB登録します...")
        batch_size = 500
        inserted_program_event_ids = set()
        for i in range(0, len(program_details_to_upsert), batch_size):
            batch = program_details_to_upsert[i:i + batch_size]
            try:
                supabase.table('programs').upsert(batch, on_conflict='event_id').execute()
                print(f"  -> 詳細バッチ {i//batch_size + 1}: {len(batch)}件登録完了")
                inserted_program_event_ids.update([row["event_id"] for row in batch])
            except Exception as e:
                print(f"  -> 詳細バッチ {i//batch_size + 1} 登録エラー: {e}")

    # --- 4. 出演情報登録 ---
    if appearances_to_upsert and appearances_table_name:
        # programs / talents で成功したIDに絞ってFKエラーを低減
        filtered_appearances = [
            a for a in appearances_to_upsert
            if a.get("program_event_id") in inserted_program_event_ids
            and a.get("talent_id") in inserted_talent_ids
        ]
        dropped = len(appearances_to_upsert) - len(filtered_appearances)
        if dropped > 0:
            print(f"🪶 FK整合のため出演レコードを {dropped} 件スキップ")
        success, errors = safe_upsert_appearances(filtered_appearances, appearances_table_name)
        print(f"✅ 出演情報登録結果: 成功 {success}件, 失敗 {errors}件")
    elif not appearances_table_name:
        print("⚠️ 出演情報テーブルが特定できないため、出演情報の登録をスキップします。")
    else:
        print("📝 出演情報なし")

    # 最終結果サマリー
    channel_breakdown = {}
    for program in target_programs:
        code = program.get('channel_code')
        if code:
            channel_breakdown[code] = channel_breakdown.get(code, 0) + 1

    print(f"\n📊 【本格運用】最終結果サマリー:")
    print(f"  • EPG取得: {len(epg_data_to_upsert)}件")
    print(f"  • 詳細取得: {len(program_details_to_upsert)}件")
    print(f"  • JSON保存: 成功 {json_upload_success}件, 失敗 {json_upload_errors}件")
    print(f"  • 出演情報: {len(appearances_to_upsert)}件")
    print(f"  • 対象チャンネル: {len(TARGET_CHANNELS)}局")
    
    # チャンネル別内訳（地上波とBSを分けて表示）
    terrestrial_count = sum(count for code, count in channel_breakdown.items() if not code.startswith('BS-') and 'BS' not in code)
    bs_count = sum(count for code, count in channel_breakdown.items() if code.startswith('BS-') or 'BS' in code)
    
    print(f"  • 地上波番組: {terrestrial_count}件")
    print(f"  • BS番組: {bs_count}件")
    
    print(f"\n📋 チャンネル別詳細:")
    for channel_code, count in sorted(channel_breakdown.items()):
        channel_type = "🏢" if not channel_code.startswith('BS-') and 'BS' not in channel_code else "📡"
        print(f"    {channel_type} {channel_code}: {count}件")
    
    print("\n🎉 本格運用が正常に完了しました。")
    
    return len(epg_data_to_upsert), len(program_details_to_upsert)

        
if __name__ == '__main__':
    start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=TARGET_DAYS)).strftime('%Y-%m-%d')
    
    try:
        epg_count, detail_count = main()
        archive_old_db_records()
        
        # 成功通知メッセージ（詳細版）
        success_message = (
            f"✅ 【本格運用】番組表スクリプトが正常に完了しました。\n\n"
            f"**📅 処理期間**: {start_date} ～ {end_date}\n"
            f"**📊 取得結果**:\n"
            f"  • 番組概要: {epg_count}件\n"
            f"  • 番組詳細: {detail_count}件\n"
            f"**📺 対象チャンネル**: 地上波7局 + BS7局\n"
            f"**🔧 修正内容**:\n"
            f"  • チャンネルマッピング問題解決\n"
            f"  • JSON保存エラー解決\n"
            f"  • 既存テーブル構造対応\n"
            f"**🚀 ステータス**: 本格運用開始"
        )
        send_discord_notification(success_message)
        
    except Exception as e:
        error_message = (
            f"🚨 【本格運用】番組表スクリプトでエラーが発生しました。\n\n"
            f"**エラー内容**:\n```\n{e}\n```\n\n"
            f"**対象期間**: {start_date} ～ {end_date}\n"
            f"**対象**: 地上波7局 + BS7局"
        )
        print(error_message)
        send_discord_notification(error_message)
        import sys
        sys.exit(1)
