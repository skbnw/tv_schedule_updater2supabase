"""
出演者情報補完スクリプト v1.1
- 処理済みデータを一括取得してスキップ（個別チェックを削減）
- 日付ごとに処理を分割可能
- バッチサイズを制限してタイムアウトを回避
"""
import os
import json
from supabase import create_client, Client
from datetime import datetime, timedelta

# 環境変数から設定を取得
def get_env(key, default=None):
    v = os.environ.get(key)
    if v is None:
        return default
    return v

SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_KEY")

# Supabase接続
table_name = "program_talent_appearances"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# JSONバックアップストレージ名
STORAGE_BUCKET = "json-backups"

# 1回のバッチで処理する最大件数（タイムアウト回避のため削減）
MAX_PROGRAMS = int(get_env("MAX_PROGRAMS", "5000"))

# 処理対象日付範囲（環境変数で指定可能、デフォルトは過去7日間）
TARGET_DAYS_BACK = int(get_env("TARGET_DAYS_BACK", "7"))


def get_all_json_files(target_dates=None):
    """
    json-backupsストレージ内のJSONファイルパスを取得
    target_datesが指定された場合はその日付のみ、Noneの場合は全ファイル
    """
    files = []
    
    # ルートの日付ディレクトリ一覧
    date_dirs = supabase.storage.from_(STORAGE_BUCKET).list(path="")
    
    # 対象日付をフィルタリング
    if target_dates:
        target_dates_set = set(target_dates)
    
    for date_dir in date_dirs:
        if date_dir.get('name'):
            date_path = date_dir['name']
            
            # 日付フィルタリング
            if target_dates and date_path not in target_dates_set:
                continue
            
            # チャンネルディレクトリ一覧
            try:
                channel_dirs = supabase.storage.from_(STORAGE_BUCKET).list(path=date_path)
                for ch_dir in channel_dirs:
                    if ch_dir.get('name'):
                        ch_path = f"{date_path}/{ch_dir['name']}"
                        # JSONファイル一覧
                        try:
                            json_files = supabase.storage.from_(STORAGE_BUCKET).list(path=ch_path)
                            for jf in json_files:
                                if jf.get('name', '').endswith('.json'):
                                    files.append(f"{ch_path}/{jf['name']}")
                        except Exception as e:
                            print(f"⚠️ {ch_path}のファイル一覧取得エラー: {e}")
            except Exception as e:
                print(f"⚠️ {date_path}のディレクトリ取得エラー: {e}")
    
    return files


def get_existing_pairs_batch(event_ids):
    """
    既存のprogram_event_id + talent_idペアを一括取得
    """
    existing_pairs = set()
    
    # バッチサイズを制限（Supabaseの制限を考慮）
    batch_size = 100
    for i in range(0, len(event_ids), batch_size):
        batch = event_ids[i:i+batch_size]
        try:
            result = supabase.table(table_name).select("program_event_id,talent_id").in_("program_event_id", batch).execute()
            for row in result.data:
                existing_pairs.add((row['program_event_id'], row['talent_id']))
        except Exception as e:
            print(f"⚠️ 既存ペア取得エラー: {e}")
    
    return existing_pairs


def supplement_appearances_from_json(target_dates=None):
    """
    出演者情報を補完するメイン処理
    target_dates: 処理対象の日付リスト（YYYY-MM-DD形式）、Noneの場合は全ファイル
    """
    print("\n=== JSON performers補完バッチ 開始 ===")
    
    # 対象日付を決定
    if target_dates is None:
        # 過去N日間の日付を生成
        today = datetime.now().date()
        target_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(TARGET_DAYS_BACK)]
        print(f"📅 対象期間: {target_dates[-1]} 〜 {target_dates[0]} ({len(target_dates)}日)")
    else:
        print(f"📅 対象日付: {', '.join(target_dates)}")
    
    files = get_all_json_files(target_dates)
    print(f"📋 JSONファイル総数: {len(files)}件")
    
    if not files:
        print("⚠️ 処理対象のファイルが見つかりません")
        return
    
    # まず全event_idを収集して既存ペアを一括取得
    print("🔍 既存データを確認中...")
    all_event_ids = []
    file_data_map = {}
    
    for file_path in files[:MAX_PROGRAMS]:  # 最大件数まで
        try:
            res = supabase.storage.from_(STORAGE_BUCKET).download(file_path)
            data = json.loads(res.decode('utf-8'))
            event_id = data.get('event_id')
            if event_id:
                all_event_ids.append(event_id)
                file_data_map[file_path] = data
        except Exception as e:
            print(f"⚠️ JSON読込エラー: {file_path} {e}")
    
    print(f"📊 収集したevent_id: {len(all_event_ids)}件")
    
    # 既存ペアを一括取得
    existing_pairs = get_existing_pairs_batch(list(set(all_event_ids)))
    print(f"✅ 既存ペア数: {len(existing_pairs)}件")
    
    # 処理開始
    supplement_count = 0
    skip_count = 0
    error_count = 0
    processed_count = 0
    
    # 処理対象のタレントIDを収集
    print("🔍 処理対象タレントIDを収集中...")
    target_talent_ids = set()
    for data in file_data_map.values():
        performers = data.get('performers', [])
        for performer in performers:
            talent_id = performer.get('talent_id')
            if talent_id:
                target_talent_ids.add(talent_id)
    
    print(f"📊 処理対象タレントID: {len(target_talent_ids)}件")
    
    # 既存タレントを一括取得（処理対象のみ）
    existing_talents = set()
    if target_talent_ids:
        try:
            # バッチサイズを制限
            batch_size = 100
            talent_ids_list = list(target_talent_ids)
            for i in range(0, len(talent_ids_list), batch_size):
                batch = talent_ids_list[i:i+batch_size]
                result = supabase.table('talents').select('talent_id').in_('talent_id', batch).execute()
                if result.data:
                    existing_talents.update([t['talent_id'] for t in result.data])
            print(f"✅ 既存タレント数: {len(existing_talents)}件")
        except Exception as e:
            print(f"⚠️ 既存タレント取得エラー: {e}")
    
    # バッチ挿入用のリスト
    talents_to_insert = []
    appearances_to_insert = []
    batch_size = 100
    
    for idx, (file_path, data) in enumerate(file_data_map.items()):
        try:
            event_id = data.get('event_id')
            performers = data.get('performers', [])
            
            if not event_id or not performers:
                skip_count += 1
                continue
            
            for performer in performers:
                talent_id = performer.get('talent_id')
                if not talent_id:
                    continue
                
                pair_key = (event_id, talent_id)
                
                # 既存ペアをスキップ
                if pair_key in existing_pairs:
                    continue
                
                # talentsテーブルに追加（なければ）
                if talent_id not in existing_talents:
                    talents_to_insert.append({
                        'talent_id': talent_id,
                        'name': performer.get('name', ''),
                        'link': performer.get('link', '')
                    })
                    existing_talents.add(talent_id)
                
                # program_talent_appearancesに追加
                appearances_to_insert.append({
                    "program_event_id": event_id,
                    "talent_id": talent_id
                })
                existing_pairs.add(pair_key)  # 重複防止
                
                # バッチサイズに達したら一括挿入
                if len(appearances_to_insert) >= batch_size:
                    # talentsを一括挿入
                    if talents_to_insert:
                        try:
                            supabase.table('talents').insert(talents_to_insert).execute()
                            print(f"✅ タレント一括登録: {len(talents_to_insert)}件")
                            talents_to_insert = []
                        except Exception as e:
                            print(f"⚠️ タレント一括登録エラー: {e}")
                    
                    # appearancesを一括挿入
                    try:
                        supabase.table(table_name).insert(appearances_to_insert).execute()
                        supplement_count += len(appearances_to_insert)
                        print(f"✅ 出演情報一括登録: {len(appearances_to_insert)}件 (累計: {supplement_count}件)")
                        appearances_to_insert = []
                    except Exception as e:
                        print(f"⚠️ 出演情報一括登録エラー: {e}")
                        error_count += len(appearances_to_insert)
                        appearances_to_insert = []
            
            processed_count += 1
            if (idx + 1) % 100 == 0:
                print(f"📊 進捗: {idx + 1}/{len(file_data_map)}件処理済み")
                
        except Exception as e:
            print(f"❌ JSON処理エラー: {file_path} {e}")
            error_count += 1
        
        if processed_count >= MAX_PROGRAMS:
            print(f"⚠️ 最大処理件数({MAX_PROGRAMS})に到達したため中断")
            break
    
    # 残りのデータを挿入
    if talents_to_insert:
        try:
            supabase.table('talents').insert(talents_to_insert).execute()
            print(f"✅ タレント最終登録: {len(talents_to_insert)}件")
        except Exception as e:
            print(f"⚠️ タレント最終登録エラー: {e}")
    
    if appearances_to_insert:
        try:
            supabase.table(table_name).insert(appearances_to_insert).execute()
            supplement_count += len(appearances_to_insert)
            print(f"✅ 出演情報最終登録: {len(appearances_to_insert)}件")
        except Exception as e:
            print(f"⚠️ 出演情報最終登録エラー: {e}")
            error_count += len(appearances_to_insert)
    
    print(f"\n=== JSON performers補完バッチ 終了 ===")
    print(f"  ✅ 補完登録: {supplement_count}件")
    print(f"  ⏭️ スキップ: {skip_count}件 (出演者なし等)")
    print(f"  ❌ エラー: {error_count}件")
    print(f"  📊 処理ファイル数: {processed_count}件")

if __name__ == "__main__":
    # 環境変数で特定日付を指定可能（カンマ区切り）
    target_dates_env = get_env("TARGET_DATES")
    target_dates = None
    if target_dates_env:
        target_dates = [d.strip() for d in target_dates_env.split(",")]
    
    supplement_appearances_from_json(target_dates) 