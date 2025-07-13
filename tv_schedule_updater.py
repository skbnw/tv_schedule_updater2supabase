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

# スクレイピング対象
TARGET_CHANNELS = ["NHKG-TKY", "NHKE-TKY", "NTV-TKY", "TV-ASAHI-TKY", "TBS-TKY", "TV-TOKYO-TKY", "FUJI-TV-TKY"]
TARGET_DAYS = 2 # 取得日数
ROTATION_DAYS = 120 # データの保持日数

CHANNEL_MAPPING = {
    # 東京 地上波
    "NHKG-TKY": "NHK総合", "NHKE-TKY": "NHKEテレ", "NTV-TKY": "日テレ",
    "TV-ASAHI-TKY": "テレビ朝日", "TBS-TKY": "TBS", "TV-TOKYO-TKY": "テレ東",
    "FUJI-TV-TKY": "フジテレビ", "TOKYO-MX": "TOKYO",
    # 関東 広域
    "TVS": "テレ玉", "CTC": "チバテレ", "TVK": "tvk",
    # BS無料
    "NHK-BS": "ＮＨＫ　ＢＳ", "BS-NTV": "BS日テレ", "BS-ASAHI": "BS朝日",
    "BS-TBS": "BS-TBS", "BS-TV-TOKYO": "ＢＳテレ東", "BS-FUJI": "BSフジ",
    "BS11": "BS11", "BS12-TWELLV": "BS12", "BS-YOSHIMOTO": "ＢＳよしもと",
    "OUJ-TV-BS": "放送大学",
    # BS有料
    "WOWOW-PRIME-BS": "WOWOWプ", "WOWOW-LIVE-BS": "WOWOWライブ",
    "WOWOW-CINEMA-BS": "WOWOWシネマ", "WOWOW-PLUS-BS": "WOWOWプラス",
    "STAR-CH-BS": "スターｃｈ",
    "JSPORTS-1-BS": "J SPORTS 1", "JSPORTS-2-BS": "J SPORTS 2",
    "JSPORTS-3-BS": "J SPORTS 3", "JSPORTS-4-BS": "J SPORTS 4",
    "GREEN-CH-BS": "グリーンチャンネル", "ANIMAX-BS": "BSアニマックス",
    "TSURIVISION-BS": "BS釣りビジョン", "DISNEY-CH-BS": "ディズニーch",
    "NIHON-EIGA-BS": "日本映画専門ch",
    # その他
    "JCOM-BS": "J:COM"
}

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Discord Webhook URLが設定されていません。")
        return
    
    print("Discordへの通知を試みます...")
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=15)
        # HTTPステータスコードが2xx（成功）でない場合に例外を発生させる
        response.raise_for_status()
        print("✅ Discordへの通知を正常に送信しました。")
    except requests.exceptions.RequestException as e:
        # 通信エラーやHTTPエラーをキャッチして詳細を出力
        print(f"❌ Discord通知の送信に失敗しました: {e}")
        if e.response is not None:
            print(f" -> Response Status: {e.response.status_code}")
            print(f" -> Response Body: {e.response.text}")

def archive_old_db_records():
    print("\n--- 古いデータベースレコードのアーカイブ開始 ---")
    cutoff_date_str = (datetime.now() - timedelta(days=ROTATION_DAYS)).strftime('%Y-%m-%d')
    print(f"{cutoff_date_str} より前のデータをアーカイブします。")
    try:
        for table_name in ["programs_epg", "programs"]:
            response = supabase.table(table_name).select("*").lt('broadcast_date', cutoff_date_str).execute()
            if response.data:
                print(f" -> {table_name}: {len(response.data)}件をアーカイブ中...")
                supabase.table(f"{table_name}_archive").upsert(response.data).execute()
                supabase.table(table_name).delete().lt('broadcast_date', cutoff_date_str).execute()
        print("✅ 古いDBレコードのアーカイブ完了。")
    except Exception as e:
        print(f"❌ DBレコードのアーカイブ中にエラー: {e}")

def archive_old_files():
    print("\n--- 古いJSONファイルのアーカイブ開始 ---")
    cutoff_date = datetime.now() - timedelta(days=ROTATION_DAYS)
    os.makedirs(JSON_ARCHIVE_DIR, exist_ok=True)
    try:
        for folder_name in os.listdir(JSON_BACKUP_DIR):
            try:
                folder_date = datetime.strptime(folder_name, '%Y-%m-%d')
                if folder_date < cutoff_date:
                    source_path = os.path.join(JSON_BACKUP_DIR, folder_name)
                    destination_path = os.path.join(JSON_ARCHIVE_DIR, folder_name)
                    if os.path.exists(destination_path): shutil.rmtree(destination_path)
                    shutil.move(source_path, destination_path)
                    print(f"移動しました: {source_path}")
            except (ValueError, FileNotFoundError): continue
        print("✅ 古いファイルのアーカイブ完了。")
    except Exception as e:
        print(f"❌ ファイルのアーカイブ中にエラー: {e}")

def main():
    print("🚀 スクリプトを開始します。")

    # --- 1. EPG基本情報の取得 ---
    epg_data_to_upsert = []
    processed_event_ids = set()
    target_dates = [(datetime.now() + timedelta(days=i)) for i in range(-1, 8)]

    print("\n--- EPG基本情報の取得開始 ---")
    for ch_type in ["td", "bs"]:
        for target_date in target_dates:
            date_str_url = target_date.strftime("%Y%m%d")
            date_str_db = target_date.strftime("%Y-%m-%d")
            url = f"https://bangumi.org/epg/{ch_type}?broad_cast_date={date_str_url}"
            if ch_type == "td":
                url += "&ggm_group_id=42"

            print(f"アクセス中: {url}")
            try:
                res = requests.get(url, timeout=20)
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
                        channel_code = next(
                            (code for code, name in CHANNEL_MAPPING.items() if name in channel_name), None
                        )

                        epg_data_to_upsert.append({
                            "event_id": event_id,
                            "broadcast_date": date_str_db,
                            "channel": channel_name,
                            "start_time": str(program_tag.get("s", "")),
                            "end_time": str(program_tag.get("e", "")),
                            "program_title": a_tag.find("p", class_="program_title").text.strip(),
                            "program_detail": a_tag.find("p", class_="program_detail").text.strip(),
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
    supabase.table('programs_epg').upsert(epg_data_to_upsert, on_conflict='event_id').execute()

    # --- 2. 番組詳細情報の取得 ---
    print("\n--- 番組詳細情報の取得開始 ---")
    program_details_to_upsert = []
    appearances_to_upsert = []
    talents_seen = {}

    for program in epg_data_to_upsert:
        if not program.get('link') or program.get('channel_code') not in TARGET_CHANNELS:
            continue

        print(f"詳細取得中: {program['program_title']}")
        try:
            res_detail = requests.get(program['link'], timeout=20)
            res_detail.raise_for_status()
            soup_detail = BeautifulSoup(res_detail.text, 'html.parser')

            title = program['program_title']
            meta_desc = soup_detail.find("meta", {"name": "description"})
            description = meta_desc["content"].strip() if meta_desc else ""
            letter_body = soup_detail.find("p", class_="letter_body")
            description_detail = letter_body.get_text(strip=True) if letter_body else ""
            genre_tag = soup_detail.find("p", class_="genre nomal")
            genre = genre_tag.get_text(strip=True).replace("\u3000", " ") if genre_tag else ""
            site_tag = soup_detail.select_one("ul.related_link a")
            official_website = site_tag.get("href") if site_tag else ""

            # 出演者リンク抽出
            performer_links = {}
            for a in soup_detail.select("a[href*='/talents/']"):
                name = a.get_text(strip=True)
                href = a.get("href", "")
                if name and href and not href.rstrip("/").endswith("talents"):
                    performer_links[name] = "https://bangumi.org" + href if href.startswith("/") else href

            talents_to_upsert = []
            for name, link in performer_links.items():
                try:
                    if not name or not link:
                        continue
                    talent_id = link.rstrip("/").split("/")[-1].split("?")[0]
                    if talent_id.isdigit():
                        if talent_id not in talents_seen:
                            talents_to_upsert.append({
                                "talent_id": talent_id,
                                "name": name,
                                "link": link
                            })
                            talents_seen[talent_id] = name
                        appearances_to_upsert.append({
                            "program_event_id": program['event_id'],
                            "talent_id": talent_id
                        })
                except Exception as e:
                    print(f"⚠️ タレント処理エラー: {name} - {e}")
                    continue

            if talents_to_upsert:
                supabase.table('talents').upsert(talents_to_upsert, on_conflict='talent_id').execute()

            db_data = {
                "event_id": program['event_id'],
                "broadcast_date": program['broadcast_date'],
                "channel": program['channel'],
                "start_time": program['start_time'],
                "end_time": program['end_time'],
                "master_title": title.split("　")[0] if "　" in title else title,
                "program_title": title,
                "description": description,
                "description_detail": description_detail,
                "genre": genre,
                "official_website": official_website,
                "channel_code": program['channel_code']
            }
            program_details_to_upsert.append(db_data)

            # JSONバックアップ保存
            date_str = program['broadcast_date']
            start_hhmm = program['start_time'][8:12] if len(program['start_time']) >= 12 else "0000"
            file_name = f"{date_str}-{start_hhmm}_{program['channel_code']}_{program['event_id']}.json"
            storage_path = f"{date_str}/{program['channel_code']}/{file_name}"
            json_string = json.dumps({**db_data, "performers": talents_to_upsert}, ensure_ascii=False, indent=2)

            try:
                supabase.storage.from_('json-backups').upload(
                    path=storage_path,
                    file=json_string.encode('utf-8'),
                    file_options={"content-type": "application/json;charset=utf-8", "upsert": "true"}
                )
                print(f"  -> JSON保存完了: {storage_path}")
            except Exception as storage_e:
                print(f"⚠️ JSON保存失敗: {storage_e}")

            time.sleep(random.uniform(1.5, 2.5))
        except Exception as e:
            print(f"❌ 番組詳細取得失敗: {program['program_title']} - {e}")
            continue

    if program_details_to_upsert:
        print(f"\n✅ {len(program_details_to_upsert)}件の詳細情報をDB登録します...")
        supabase.table('programs').upsert(program_details_to_upsert, on_conflict='event_id').execute()

    if appearances_to_upsert:
        print(f"✅ {len(appearances_to_upsert)}件の出演情報をappearancesテーブルに登録します...")
        supabase.table('appearances').upsert(appearances_to_upsert, on_conflict=["program_event_id", "talent_id"]).execute()

    print("\n🎉 全ての処理が正常に完了しました。")
    return len(epg_data_to_upsert), len(program_details_to_upsert)

        
if __name__ == '__main__':
    # 処理対象の日付範囲を先に定義
    start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    try:
        # main関数から処理件数を受け取る
        epg_count, detail_count = main()
        
        # アーカイブ処理
        # archive_old_files()
        archive_old_db_records()
        
        # 成功通知メッセージを作成
        success_message = (
            f"✅ 番組表スクリプトは正常に完了しました。\n\n"
            f"**処理期間**: {start_date} ～ {end_date}\n"
            f"**番組概要**: {epg_count}件 取得\n"
            f"**番組詳細**: {detail_count}件 取得"
        )
        send_discord_notification(success_message)
        

    except Exception as e:
        error_message = f"🚨 番組表スクリプトでエラーが発生しました。\n\n**エラー内容**:\n```\n{e}\n```"
        print(error_message)
        send_discord_notification(error_message)
