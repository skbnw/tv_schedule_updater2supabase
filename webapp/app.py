# -*- coding: utf-8 -*-
"""
T-Clip 出演トラッカー / 番組検索 UI（Streamlit）

機能:
  1) 人物から探す   : タレント（政治家など）を選ぶ → 出演番組一覧 → 番組詳細
  2) キーワードで探す : pgroonga 全文検索で番組表・番組詳細を横断検索（政治関連の抽出など）

接続方式:
  Supabase API（PostgREST）経由。DBパスワード不要。サーバ用の secret キーで RPC を呼ぶ。
  必要な環境変数 / secrets:
    SUPABASE_URL         = https://<ref>.supabase.co
    SUPABASE_SECRET_KEY  = sb_secret_...   （無ければ SUPABASE_KEY でも可）

前提（Supabase 側にセットアップ済み）:
  - 拡張 pgroonga ＋ 式インデックス、ビュー v_program_search / v_talent_appearances
  - RPC: app_categories() / app_talents(p_tag) / app_appearances(p_talent_id) /
         app_search(p_query, p_politician_only, p_limit)
"""

import os
import datetime as dt

import pandas as pd
import streamlit as st
from supabase import create_client, Client

# ------------------------------------------------------------------
# 設定
# ------------------------------------------------------------------
st.set_page_config(page_title="TV Appearance Tracker (Beta)", page_icon="📺", layout="wide")

# キーワード検索の例示（クリックで投入）
KEYWORD_EXAMPLES = ["消費税", "国会", "選挙", "党首討論", "内閣改造", "防衛", "外交", "物価高", "憲法", "解散"]

# 「番組から探す」用カタログ（label, pgroongaクエリ）。クエリは番組名がタイトルに含まれる回を拾う。
PROGRAM_CATALOG = {
    "政治討論・報道番組": [
        ("日曜討論（NHK）", "日曜討論"),
        ("プライムニュース（BSフジ）", "プライムニュース"),
        ("深層NEWS（BS日テレ）", "深層NEWS"),
        ("報道1930（BS-TBS）", "報道1930"),
        ("インサイドOUT（BS11）", "インサイドOUT"),
        ("日曜サロン（BSテレ東）", "日曜サロン"),
        ("日曜報道 THE PRIME（フジ）", "日曜報道"),
        ("報道特集（TBS）", "報道特集"),
    ],
    "情報・ワイド番組": [
        ("サンデーモーニング（TBS）", "サンデーモーニング"),
        ("サンデー・ジャポン（TBS）", "サンデー ジャポン"),
        ("情報7daysニュースキャスター（TBS）", "情報7days"),
    ],
}

# 政治関連抽出のデフォルトキーワード（pgroonga クエリ構文: 空白= AND, OR で論理和）
POLITICAL_KEYWORDS = (
    "政治 OR 国会 OR 選挙 OR 内閣 OR 首相 OR 総理 OR 与党 OR 野党 OR 政権 OR "
    "自民 OR 立憲 OR 維新 OR 国民民主 OR 公明 OR 共産 OR れいわ OR 参政 OR "
    "議員 OR 大臣 OR 官房長官 OR 解散 OR 法案 OR 予算 OR 外交 OR 防衛"
)


def _secret(name: str, default: str = "") -> str:
    """環境変数優先。無ければ secrets.toml（未作成時の例外は握りつぶす）。"""
    val = os.environ.get(name, "")
    if not val:
        try:
            val = st.secrets.get(name, "")
        except Exception:
            val = ""
    return val or default


@st.cache_resource
def get_client() -> Client:
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_SECRET_KEY") or _secret("SUPABASE_KEY")
    if not url or not key:
        st.error(
            "SUPABASE_URL / SUPABASE_SECRET_KEY が未設定です。"
            "環境変数か .streamlit/secrets.toml に設定してください。"
        )
        st.stop()
    return create_client(url, key)


def rpc(fn: str, params: dict | None = None) -> pd.DataFrame:
    res = get_client().rpc(fn, params or {}).execute()
    return pd.DataFrame(res.data or [])


# ------------------------------------------------------------------
# データ取得（キャッシュ）
# ------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_categories() -> pd.DataFrame:
    return rpc("app_categories")


@st.cache_data(ttl=600)
def load_talents(tag_name: str) -> pd.DataFrame:
    return rpc("app_talents", {"p_tag": tag_name})


@st.cache_data(ttl=300)
def search_talents(name_query: str) -> pd.DataFrame:
    """タグ未付与でも出演実績のある全タレントを名前で検索。"""
    return rpc("app_talent_search", {"p_query": name_query, "p_limit": 60})


@st.cache_data(ttl=600)
def load_politicians() -> pd.DataFrame:
    """国会議員名簿のうちテレビ登場（政治文脈）のある議員。"""
    return rpc("app_politicians", {"p_min_hits": 1})


@st.cache_data(ttl=300)
def politician_programs(name: str, appearance_only: bool = False) -> pd.DataFrame:
    """議員名＋政治文脈で登場番組を取得。appearance_only=Trueで氏名近接に出演語を要求。"""
    return rpc("app_politician_programs",
               {"p_name": name, "p_limit": 300, "p_appearance_only": appearance_only})


@st.cache_data(ttl=300)
def load_appearances(talent_id: str) -> pd.DataFrame:
    return rpc("app_appearances", {"p_talent_id": talent_id})


@st.cache_data(ttl=300)
def search_programs(query: str, politician_only: bool, limit: int = 300) -> pd.DataFrame:
    return rpc(
        "app_search",
        {"p_query": query, "p_politician_only": politician_only, "p_limit": limit},
    )


# ------------------------------------------------------------------
# 表示ヘルパー
# ------------------------------------------------------------------
DOW = ["月", "火", "水", "木", "金", "土", "日"]
GENRE_ICON = {"報道": "🗞️", "ニュース": "🗞️", "バラエティ": "🎭", "ワイド": "📣", "情報": "📣"}


def fmt_when(start_time: str, broadcast_date: str) -> str:
    """'202607241930' → '2026-07-24（金）19:30'。失敗時は放送日にフォールバック。"""
    try:
        d = dt.datetime.strptime(str(start_time)[:12], "%Y%m%d%H%M")
        return f"{d:%Y-%m-%d}（{DOW[d.weekday()]}）{d:%H:%M}"
    except (ValueError, TypeError):
        return str(broadcast_date or "")


def genre_icon(genre: str) -> str:
    for k, v in GENRE_ICON.items():
        if genre and k in genre:
            return v
    return "📺"


def render_results(df: pd.DataFrame, key: str):
    """結果表示にツールバー（今後の放送のみ / 放送月フィルタ / CSV）を付けて描画。"""
    if df.empty:
        st.info("該当する番組はありません。")
        return
    d = df.copy()
    d["_date"] = pd.to_datetime(d["broadcast_date"], errors="coerce")
    # 結果セットが変わるとフィルタが持ち越されないよう、キーにデータ署名を付与
    sig = f"{key}_{d['event_id'].iloc[0]}_{len(d)}"
    today = pd.Timestamp(dt.date.today())

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        upcoming = st.checkbox("今後の放送のみ", key=f"{sig}_up")
    with c2:
        genres = sorted({g for g in d["genre"].dropna().unique() if g})
        picked_genres = st.multiselect(
            "ジャンルで絞り込み", genres, key=f"{sig}_ge",
            help="ドラマ等を外したいときに『ニュース／報道』などを選択（未選択＝すべて）。",
        )
    with c3:
        months = sorted({t.strftime("%Y-%m") for t in d["_date"].dropna()}, reverse=True)
        picked_months = st.multiselect("放送月で絞り込み", months, key=f"{sig}_mo")

    if upcoming:
        d = d[d["_date"] >= today]
    if picked_genres:
        d = d[d["genre"].isin(picked_genres)]
    if picked_months:
        d = d[d["_date"].dt.strftime("%Y-%m").isin(picked_months)]

    left, right = st.columns([3, 1])
    with left:
        st.caption(f"表示 {len(d)} 件")
    with right:
        csv = d.drop(columns=["_date"]).to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ CSV", csv, file_name=f"{key}.csv",
                           mime="text/csv", key=f"{sig}_dl", use_container_width=True)

    render_program_rows(d.drop(columns=["_date"]))


def render_program_rows(df: pd.DataFrame):
    if df.empty:
        st.info("該当する番組はありません。")
        return
    for _, r in df.iterrows():
        icon = genre_icon(r["genre"])
        head = f"{icon}  {fmt_when(r['start_time'], r['broadcast_date'])}　|　{r['channel']}　|　{r['program_title']}"
        with st.expander(head):
            kubun = "放送済み(アーカイブ)" if r["source"] == "archive" else "直近"
            st.markdown(f"**ジャンル**: {r['genre'] or '—'}　　**区分**: {kubun}")
            detail = (r["description_detail"] or "").strip() or (r["description"] or "").strip()
            st.write(detail if detail else "（番組内容の登録なし）")
            if r["official_website"]:
                st.markdown(f"[🔗 公式サイトを開く]({r['official_website']})")
            st.caption(f"event_id: {r['event_id']}")


# ------------------------------------------------------------------
# 画面
# ------------------------------------------------------------------
st.markdown("# 📺 TV Appearance Tracker :red-badge[BETA]")
st.caption("政治家・有識者のテレビ出演を追う／番組表・詳細のキーワード検索")

mode = st.sidebar.radio("表示", ["人物から探す", "番組から探す", "キーワードで探す"], index=0)

# ---- モード1: 人物から探す ----
if mode == "人物から探す":
    cats = load_categories()
    if cats.empty:
        st.warning("カテゴリを取得できませんでした。")
        st.stop()

    # カテゴリ先頭に「国会議員名簿」と「全タレント名前検索」を用意
    POL_LABEL = "🏛️ 国会議員（名簿）"
    ALL_LABEL = "🔍 すべて（名前で検索）"
    cat_labels = {f"{row['description']}（{int(row['n'])}）": row["tag_name"] for _, row in cats.iterrows()}
    labels = [POL_LABEL, ALL_LABEL] + list(cat_labels.keys())
    picked_label = st.sidebar.selectbox("カテゴリ", labels, index=0)

    # ===== 国会議員（名簿）: 特別国会時点の議員×番組表を政治文脈で照合 =====
    if picked_label == POL_LABEL:
        st.sidebar.caption("国会議員名簿（711名）× 番組表を政治文脈で照合")
        pols = load_politicians()
        kw = st.sidebar.text_input("議員名で絞り込み", "")
        if kw and not pols.empty:
            pols = pols[pols["name"].str.contains(kw, na=False)]
        if pols.empty:
            st.warning("該当する議員がいません。")
            st.stop()
        popts = {
            f"{r['name']}　（{int(r['tv_hits'])}件 / {r['party']}・{r['chamber']}）": r["name"]
            for _, r in pols.iterrows()
        }
        picked = st.sidebar.radio("議員", list(popts.keys()), index=0)
        pol_name = popts[picked]
        appearance_only = st.sidebar.checkbox(
            "出演の可能性が高いものだけ", value=False,
            help="氏名のすぐ近くに『出演・生出演・ゲスト・直撃・生直言』等がある番組に限定。"
                 "首相など『話題として言及されただけ』の番組を除きます（試験的・取りこぼしもあり）。",
        )
        st.subheader(f"🏛️ {pol_name} の登場番組")
        if appearance_only:
            st.caption("氏名の近接に出演を示す語がある番組のみ（話題としての言及を除外）。")
        else:
            st.caption("氏名＋政治文脈で照合。出演・言及の両方を含みます。")
        progs = politician_programs(pol_name, appearance_only)
        st.caption(f"{len(progs)} 件（新しい順・最大300件）")
        render_results(progs, "politician")
        st.stop()

    if picked_label == ALL_LABEL:
        st.sidebar.caption(f"出演実績のある全タレントから検索（タグ付与は現状ごく一部）")
        name_q = st.sidebar.text_input("名前で検索", "", placeholder="例: 玉木 / 池上 / 大谷")
        if not name_q.strip():
            st.info("左の「名前で検索」に人物名を入力してください（部分一致）。")
            st.stop()
        talents = search_talents(name_q.strip())
    else:
        tag_name = cat_labels[picked_label]
        talents = load_talents(tag_name)
        kw = st.sidebar.text_input("名前で絞り込み", "")
        if kw and not talents.empty:
            talents = talents[talents["name"].str.contains(kw, na=False)]

    if talents.empty:
        st.warning("該当するタレントがいません。")
        st.stop()

    options = {
        f"{row['name']}　（{int(row['appearances'])}件 / 最新 {row['latest_date'] or '—'}）": row["talent_id"]
        for _, row in talents.iterrows()
    }
    picked = st.sidebar.radio("タレント", list(options.keys()), index=0)
    talent_id = options[picked]
    talent_name = picked.split("　")[0]

    st.subheader(f"🧑‍💼 {talent_name} の出演番組")
    apps = load_appearances(talent_id)

    genres = ["すべて"] + sorted({g for g in apps["genre"].dropna().unique()}) if not apps.empty else ["すべて"]
    gsel = st.selectbox("ジャンル", genres, index=0)
    view = apps if gsel == "すべて" else apps[apps["genre"] == gsel]

    st.caption(f"出演 {len(view)} 件（出演者データに登録された分）")
    render_results(view, "talent")

    # 出演リンクは自由文の告知を取りこぼすため、説明文の名前言及も補完表示する
    st.divider()
    mentions = search_programs(talent_name, False)
    linked_ids = set(apps["event_id"]) if not apps.empty else set()
    extra = mentions[~mentions["event_id"].isin(linked_ids)] if not mentions.empty else mentions
    with st.expander(
        f"🔎 番組表で「{talent_name}」に言及している番組（出演・話題を含む）: {len(mentions)} 件",
        expanded=(len(view) == 0),
    ):
        st.caption(
            "※ 番組説明に名前が含まれる番組。出演確定ではなく話題としての言及や、"
            "同名の別人を含む場合があります。上の「出演」に無い分のみ表示。"
        )
        render_program_rows(extra)

# ---- モード2: 番組から探す ----
elif mode == "番組から探す":
    st.subheader("📻 番組から探す（政治討論・報道・情報番組）")
    st.caption("放送回を新しい順に一覧。各回を開くと出演者・内容が見られます。")

    cat = st.sidebar.selectbox("番組カテゴリ", list(PROGRAM_CATALOG.keys()))
    progs = PROGRAM_CATALOG[cat]
    picked = st.sidebar.radio("番組", [p[0] for p in progs])
    query = dict(progs)[picked]

    st.markdown(f"### {picked}")
    eps = search_programs(query, False)
    st.caption(f"放送回 {len(eps)} 件（新しい順・最大300件）")
    render_results(eps, "series")

# ---- モード3: キーワードで探す ----
else:
    st.subheader("🔎 キーワード検索（番組表・番組詳細を横断）")
    st.caption("空白区切りは AND、`OR` で論理和。例: `国会 消費税` / `選挙 OR 内閣改造`")

    # 政治関連キーワードの例示（クリックで投入）
    st.write("政治関連キーワードの例（クリックで入力）:")
    ex_cols = st.columns(len(KEYWORD_EXAMPLES))
    for i, ex in enumerate(KEYWORD_EXAMPLES):
        if ex_cols[i].button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state["kw_input"] = ex

    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("キーワード", key="kw_input")
    with col2:
        use_pol = st.checkbox("政治プリセット", value=False, help="政治関連キーワードを一括投入")

    politician_only = st.checkbox("政治家が出演した番組に限定", value=False)

    query = POLITICAL_KEYWORDS if use_pol else (q or "").strip()
    if not query:
        st.info("キーワードを入力するか「政治プリセット」を有効にしてください。")
        st.stop()

    res = search_programs(query, politician_only)
    st.caption(f"ヒット {len(res)} 件（最大300件表示）")
    render_results(res, "keyword")
