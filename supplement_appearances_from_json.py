import os
import json
from supabase import create_client, Client
from datetime import datetime

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

# 1回のバッチで処理する最大件数
MAX_PROGRAMS = 10000


def get_all_json_files():
    """
    json-backupsストレージ内の全JSONファイルパスを再帰的に取得
    """
    files = []
    # ルートの日付ディレクトリ一覧
    date_dirs = supabase.storage.from_(STORAGE_BUCKET).list(path="")
    for date_dir in date_dirs:
        if date_dir.get('name') and date_dir.get('type') == 'folder':
            date_path = date_dir['name']
            # チャンネルディレクトリ一覧
            channel_dirs = supabase.storage.from_(STORAGE_BUCKET).list(path=date_path)
            for ch_dir in channel_dirs:
                if ch_dir.get('name') and ch_dir.get('type') == 'folder':
                    ch_path = f"{date_path}/{ch_dir['name']}"
                    # JSONファイル一覧
                    json_files = supabase.storage.from_(STORAGE_BUCKET).list(path=ch_path)
                    for jf in json_files:
                        if jf.get('name', '').endswith('.json'):
                            files.append(f"{ch_path}/{jf['name']}")
    return files


def supplement_appearances_from_json():
    print("\n=== JSON performers補完バッチ 開始 ===")
    files = get_all_json_files()
    print(f"JSONファイル総数: {len(files)}件")
    supplement_count = 0
    skip_count = 0
    error_count = 0
    checked_pairs = set()

    for idx, file_path in enumerate(files):
        try:
            res = supabase.storage.from_(STORAGE_BUCKET).download(file_path)
            data = json.loads(res.decode('utf-8'))
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
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                # 既にDBに登録済みかチェック
                check = supabase.table(table_name).select("program_event_id", "talent_id") \
                    .eq("program_event_id", event_id).eq("talent_id", talent_id).execute()
                if not check.data:
                    # talentsテーブルにも補完（なければ）
                    t_check = supabase.table('talents').select('talent_id').eq('talent_id', talent_id).execute()
                    if not t_check.data:
                        try:
                            supabase.table('talents').insert({
                                'talent_id': talent_id,
                                'name': performer.get('name', ''),
                                'link': performer.get('link', '')
                            }).execute()
                        except Exception as e:
                            print(f"talents補完エラー: {talent_id} {e}")
                    # program_talent_appearances補完
                    try:
                        supabase.table(table_name).insert({
                            "program_event_id": event_id,
                            "talent_id": talent_id
                        }).execute()
                        supplement_count += 1
                        print(f"補完登録: {event_id} {talent_id} {performer.get('name', '')}")
                    except Exception as e:
                        print(f"補完登録エラー: {event_id} {talent_id} {e}")
                        error_count += 1
        except Exception as e:
            print(f"JSON読込エラー: {file_path} {e}")
            error_count += 1
        if idx + 1 >= MAX_PROGRAMS:
            print(f"最大処理件数({MAX_PROGRAMS})に到達したため中断")
            break
    print(f"\n=== JSON performers補完バッチ 終了 ===")
    print(f"  • 補完登録: {supplement_count}件")
    print(f"  • スキップ: {skip_count}件 (出演者なし等)")
    print(f"  • エラー: {error_count}件")

if __name__ == "__main__":
    supplement_appearances_from_json() 