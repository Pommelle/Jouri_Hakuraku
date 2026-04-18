import streamlit as st
import sys
import os
import sqlite3
import base64
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.crud import (
    get_daily_summaries,
    get_center_intel_today,
    get_memory_by_team,
    insert_memory,
    delete_memory,
    update_memory,
    get_all_source_confidence,
    upsert_source_confidence,
    delete_source_confidence,
)

load_dotenv(override=True)
LOGIN_CODE = os.getenv("LOGIN_CODE", "")

# ─────────────────────────────────────────────────────────────────────
# 翻译系统
# ─────────────────────────────────────────────────────────────────────
TRANSLATIONS = {
    "zh": {
        # auth
        "auth_title": "系统访问验证",
        "auth_pwd_label": "请输入访问密码：",
        "auth_submit": "登录",
        "auth_error": "访问被拒绝。",
        # sidebar memory
        "sidebar_memory_title": "今日情报流",
        "sidebar_add_memory": "➕ 添加情报",
        "sidebar_title_label": "标题",
        "sidebar_source_label": "来源 / Source",
        "sidebar_context_label": "分析 / Context",
        "sidebar_save": "保存",
        "sidebar_save_error": "字段不能为空",
        "sidebar_empty": "记忆库暂时为空。",
        "sidebar_popover_edit": "Edit",
        "sidebar_edit_title": "标题",
        "sidebar_edit_source": "来源",
        "sidebar_edit_context": "分析",
        "sidebar_update": "更新",
        # tracking topic
        "tracking_label": "追踪话题",
        "no_topic": "未设定跟进话题 / No tracking topic set.",
        # team buttons
        "btn_red": "🔴 红队",
        "btn_blue": "🔵 蓝队",
        # headers
        "header_red": "红队 — 7日情报摘要",
        "header_blue": "蓝队 — 7日情报摘要",
        "no_summaries": "暂无每日摘要。系统将在明天凌晨 00:05 自动生成第一份摘要（覆盖今日数据）。",
        "meta_sources": "来源",
        "meta_items": "条数",
        "meta_na": "无",
        # popover menu
        "menu_settings": "🛠️ 系统设置",
        "menu_conf": "⚙️ 置信度名单",
        "menu_lang": "🌐 语言 / Language",
        # conf dialog
        "conf_title": "⚙️ 置信度名单 / Source Confidence",
        "conf_add_expander": "➕ 添加 / 编辑来源",
        "conf_key_label": "来源关键词 (keyword)",
        "conf_key_placeholder": "例如 trump",
        "conf_anchor_label": "置信度锚点",
        "conf_tier_label": "档位",
        "conf_tier_high": "high",
        "conf_tier_medium": "medium",
        "conf_tier_low": "low",
        "conf_notes_label": "备注 / Notes",
        "conf_notes_placeholder": "可选备注",
        "conf_save": "💾 保存 / Save",
        "conf_save_error": "来源关键词不能为空",
        "conf_col_tier": "档位",
        "conf_col_keyword": "关键词",
        "conf_col_anchor": "锚点",
        "conf_col_notes": "备注",
        "conf_col_action": "操作",
        "conf_empty": "名单为空。",
        "conf_close_x": "✕",
        "conf_close_btn": "关闭",
        # date format
        "date_fmt": "%Y年%m月%d日 %A",
    },
    "en": {
        # auth
        "auth_title": "System Access Verification",
        "auth_pwd_label": "Enter System Passcode:",
        "auth_submit": "Authenticate",
        "auth_error": "Access Denied.",
        # sidebar memory
        "sidebar_memory_title": "Today's Intelligence Stream",
        "sidebar_add_memory": "➕ Add Intelligence",
        "sidebar_title_label": "Title",
        "sidebar_source_label": "Source",
        "sidebar_context_label": "Context",
        "sidebar_save": "Save",
        "sidebar_save_error": "Fields cannot be empty.",
        "sidebar_empty": "Memory bank is currently empty.",
        "sidebar_popover_edit": "Edit",
        "sidebar_edit_title": "Title",
        "sidebar_edit_source": "Source",
        "sidebar_edit_context": "Context",
        "sidebar_update": "Update",
        # tracking topic
        "tracking_label": "Tracking Topic",
        "no_topic": "No tracking topic set.",
        # team buttons
        "btn_red": "🔴 RED TEAM",
        "btn_blue": "🔵 BLUE TEAM",
        # headers
        "header_red": "RED TEAM — 7 DAY INTELLIGENCE SUMMARY",
        "header_blue": "BLUE TEAM — 7 DAY INTELLIGENCE SUMMARY",
        "no_summaries": "No daily summaries yet. The first one will be generated automatically at 00:05 tomorrow morning (covering today).",
        "meta_sources": "Sources",
        "meta_items": "Items",
        "meta_na": "N/A",
        # popover menu
        "menu_settings": "🛠️ System Settings",
        "menu_conf": "⚙️ Confidence List",
        "menu_lang": "🌐 Language",
        # conf dialog
        "conf_title": "⚙️ Source Confidence List",
        "conf_add_expander": "➕ Add / Edit Source",
        "conf_key_label": "Source Keyword",
        "conf_key_placeholder": "e.g. trump",
        "conf_anchor_label": "Confidence Anchor",
        "conf_tier_label": "Tier",
        "conf_tier_high": "high",
        "conf_tier_medium": "medium",
        "conf_tier_low": "low",
        "conf_notes_label": "Notes",
        "conf_notes_placeholder": "Optional notes",
        "conf_save": "💾 Save",
        "conf_save_error": "Source keyword cannot be empty.",
        "conf_col_tier": "Tier",
        "conf_col_keyword": "Keyword",
        "conf_col_anchor": "Anchor",
        "conf_col_notes": "Notes",
        "conf_col_action": "Action",
        "conf_empty": "List is empty.",
        "conf_close_x": "✕",
        "conf_close_btn": "Close",
        # date format
        "date_fmt": "%B %d, %Y",
    },
}


def T(key):
    lang = st.session_state.get("lang", "zh")
    return TRANSLATIONS[lang].get(key, key)


st.set_page_config(
    page_title="Jouri Hakuraku | 常理剥落",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3, h4, h5 { color: #ffffff !important; font-family: 'Courier New', Courier, monospace; }

    #MainMenu {visibility: hidden !important; display: none !important;}
    [data-testid="stConnectionStatus"] {display: none !important;}
    .stAppDeployButton {display: none !important;}
    button[title="View fullscreen"] {display: none !important;}
    [data-testid="StyledFullScreenButton"] {visibility: hidden !important; display: none !important;}

    .logo-text { font-size: 2.8rem; font-weight: bold; letter-spacing: 5px; color: #ff1a1a; text-shadow: 0 0 10px rgba(255,26,26,0.6); }
    .logo-text span { color: #800000; }

    .topic-para { text-align: center; font-size: 1.05em; color: #ff4d4d; background: rgba(255,0,0,0.05); padding: 8px 16px; border: 1px dashed #4d0000; max-width: 800px; margin: 0 auto 16px auto; border-radius: 4px; }

    .sidebar-section-title { font-size: 0.85em; font-weight: bold; color: #888888; letter-spacing: 2px; text-transform: uppercase; margin: 12px 0 8px 0; border-bottom: 1px solid #222; padding-bottom: 4px; }

    .memory-box { background: #0a0a0a; border: 1px solid #222; border-radius: 0; padding: 10px; margin-bottom: 10px; }
    .memory-box h5 { margin-top: 0; margin-bottom: 4px; color: #ff4d4d; font-size: 0.95em; }
    .memory-box p { font-size: 0.82em; color: #aaaaaa; margin-bottom: 0; line-height: 1.4; }

    .intel-type-news { color: #4d94ff; font-size: 0.75em; font-weight: bold; }
    .intel-type-chat { color: #ff6b35; font-size: 0.75em; font-weight: bold; }
    .intel-type-mixed { color: #aaaaaa; font-size: 0.75em; font-weight: bold; }

    .today-card { background: #0d0d0d; border: 1px solid #1a1a1a; border-left: 3px solid #444; padding: 10px 12px; margin-bottom: 8px; border-radius: 2px; }
    .today-card h6 { margin: 0 0 4px 0; font-size: 0.9em; color: #dddddd; }
    .today-card .meta { font-size: 0.72em; color: #666; margin-bottom: 4px; }

    .summary-date-header { color: #ffffff; font-size: 1.1em; font-weight: bold; border-bottom: 1px solid #2a2a2a; padding: 6px 0 4px 0; margin: 16px 0 8px 0; }
    .summary-date-header span { color: #888; font-size: 0.8em; font-weight: normal; margin-left: 8px; }
    .summary-card { background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 0; padding: 14px 16px; margin-bottom: 6px; }
    .summary-content { font-size: 0.88em; color: #cccccc; line-height: 1.6; }
    .summary-meta { font-size: 0.72em; color: #555; margin-top: 8px; border-top: 1px solid #1a1a1a; padding-top: 6px; }

    .stTextInput > div > div > input, .stTextArea > div > div > textarea { background: #111 !important; color: #ddd !important; border: 1px solid #333 !important; }
    .stButton > button { background: #1a1a1a; color: #ddd; border: 1px solid #333; }
    .stButton > button:hover { background: #2a2a2a; border-color: #555; }

    .source-high { color: #44cc66 !important; font-weight: bold; }
    .source-medium { color: #ccaa33 !important; font-weight: bold; }
    .source-low { color: #cc4444 !important; font-weight: bold; }
    .source-row { background: #0a0a0a; border-bottom: 1px solid #1a1a1a; padding: 8px 4px; }
    .source-row:hover { background: #111; }
    [data-testid="stPopover"] .stPopover { border: 1px solid #333; background: #0d0d0d; min-width: 320px; }
    [data-testid="stPopover"] .stRadio > label { font-size: 0.85em; }
    [data-testid="stPopover"] .stExpander { border: none !important; }
    [data-testid="stPopover"] .streamlit-expanderHeader { font-size: 0.85em; color: #aaa; }

    [data-testid="stMainContentContainer"] { padding-top: 0 !important; }

    [data-testid="stPopover"] > div:first-child > button {
        background: transparent !important;
        border: none !important;
        color: #888 !important;
        font-size: 1.5rem !important;
        padding: 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stPopover"] > div:first-child > button:hover {
        background: transparent !important;
        color: #ccc !important;
    }
    [data-testid="stPopover"] > div:first-child > button > div > svg {
        display: none !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderToggle"] svg {
        display: none !important;
    }

    /* lang toggle button styles */
    .lang-btn { background: #1a1a1a; color: #888; border: 1px solid #333; }
    .lang-btn.active { background: #2a2a2a; color: #fff; border-color: #555; }
</style>""", unsafe_allow_html=True)


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False if LOGIN_CODE else True

    if not st.session_state.authenticated:
        st.markdown("<div style='min-height: 15vh;'></div>", unsafe_allow_html=True)
        logo_path = os.path.join(os.path.dirname(__file__), "logo_dark.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            col_l1, col_l2, col_l3 = st.columns([1.5, 1.2, 1.5])
            with col_l2:
                st.markdown(f'<img src="data:image/png;base64,{img_b64}" style="width:100%;">', unsafe_allow_html=True)
        else:
            st.markdown("<div class='logo-text'>JOURI <span>HAKURAKU</span></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            with st.form(key="auth_form", border=False):
                pwd = st.text_input(T("auth_pwd_label"), type="password", key="pwd_input")
                btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
                with btn_col2:
                    submitted = st.form_submit_button(T("auth_submit"), use_container_width=True)
                if submitted:
                    if pwd == LOGIN_CODE:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error(T("auth_error"))

        st.markdown("<div style='min-height: 15vh;'></div>", unsafe_allow_html=True)
        return False
    return True


if not check_password():
    st.stop()


TRACKING_TOPIC = os.getenv("TRACKING_TOPIC", "")

# ── Language setup ──────────────────────────────────────────────────
if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "conf_open" not in st.session_state:
    st.session_state.conf_open = False
if "conf_dialog_open" not in st.session_state:
    st.session_state.conf_dialog_open = False

params = st.query_params
if params.get("action") == "open_conf":
    st.session_state.conf_open = True
    st.session_state.conf_dialog_open = True
    params.clear()
if params.get("lang"):
    st.session_state.lang = params.get("lang")
    params.clear()

lang = st.session_state.lang


# ── Language switcher (safe: sets state then reruns) ─────────────────
def switch_lang(new_lang):
    st.session_state.lang = new_lang
    st.rerun()


# ═══════════════════════════════════════════════════════════════════
# Sidebar — shared memory
# ═══════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"<div class='sidebar-section-title'>{T('sidebar_memory_title')}</div>", unsafe_allow_html=True)

    with st.expander(T("sidebar_add_memory")):
        with st.form(key="add_mem_sidebar", clear_on_submit=True):
            new_title = st.text_input(T("sidebar_title_label"))
            new_source = st.text_input(T("sidebar_source_label"), value="Manual")
            new_context = st.text_area(T("sidebar_context_label"))
            if st.form_submit_button(T("sidebar_save")):
                if new_title and new_context:
                    insert_memory("general", new_title, new_context, source=new_source)
                    st.rerun()
                else:
                    st.error(T("sidebar_save_error"))

    memories = get_memory_by_team("general")
    if not memories:
        st.markdown(f"<em style='color:#444;font-size:0.85em;'>{T('sidebar_empty')}</em>", unsafe_allow_html=True)
    else:
        for mem in memories:
            try:
                dt = datetime.strptime(mem['created_at'], '%Y-%m-%d %H:%M:%S')
                ts = dt.strftime('%m/%d %H:%M')
            except:
                ts = mem['created_at']
            st.markdown(f"""
            <div class='memory-box'>
                <div style="display:flex;justify-content:space-between;align-items:baseline;">
                    <h5>{mem['key_concept']}</h5>
                    <span style="font-size:0.68em;color:#555;">{ts}</span>
                </div>
                <div style="font-size:0.72em;color:#666;margin-bottom:4px;font-style:italic;">Source: {mem['source']}</div>
                <p>{mem['context']}</p>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                with st.popover(T("sidebar_popover_edit")):
                    with st.form(key=f"edit_mem_{mem['id']}", clear_on_submit=True):
                        e_t = st.text_input(T("sidebar_edit_title"), value=mem['key_concept'])
                        e_s = st.text_input(T("sidebar_edit_source"), value=mem['source'])
                        e_c = st.text_area(T("sidebar_edit_context"), value=mem['context'])
                        if st.form_submit_button(T("sidebar_update")):
                            update_memory(mem['id'], e_t, e_c, source=e_s)
                            st.rerun()
            with c2:
                if st.button("✖", key=f"del_mem_{mem['id']}"):
                    delete_memory(mem['id'])
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════
# Top-right popover menu
# ═══════════════════════════════════════════════════════════════════

with st.popover("⋮"):
    st.markdown(f"**{T('menu_settings')}**")
    if st.button(T("menu_conf"), key="hdr_conf_btn_popover", use_container_width=True):
        st.session_state.conf_open = True
        st.session_state.conf_dialog_open = True
        st.rerun()

    st.divider()
    st.markdown(f"**{T('menu_lang')}**")

    # Two buttons; active one gets highlighted class via st.markdown trick
    # We use session_state to know which is active
    if st.button("中文", key="hdr_lang_zh_popover", use_container_width=True):
        switch_lang("zh")
    if st.button("EN", key="hdr_lang_en_popover", use_container_width=True):
        switch_lang("en")


# ═══════════════════════════════════════════════════════════════════
# Logo
# ═══════════════════════════════════════════════════════════════════

logo_path = os.path.join(os.path.dirname(__file__), "logo_dark.png")
if os.path.exists(logo_path):
    with open(logo_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    st.markdown(f'<img src="data:image/png;base64,{img_b64}" style="width:180px; display:block; margin:0 auto;">', unsafe_allow_html=True)
else:
    st.markdown("<div style='text-align:center;margin-bottom:8px;'><span class='logo-text' style='font-size:2rem;'>JOURI <span>HAKURAKU</span></span></div>", unsafe_allow_html=True)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# Main content
# ═══════════════════════════════════════════════════════════════════

topic_display = TRACKING_TOPIC if TRACKING_TOPIC else T("no_topic")
st.markdown(f"<div class='topic-para'>{topic_display}</div>", unsafe_allow_html=True)
st.divider()

col_left, col_right = st.columns([1, 1])
with col_left:
    if st.button(T("btn_red"), key="btn_red", use_container_width=True):
        st.session_state.active_view = "red"
        st.rerun()

with col_right:
    if st.button(T("btn_blue"), key="btn_blue", use_container_width=True):
        st.session_state.active_view = "blue"
        st.rerun()

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

view = st.session_state.get("active_view", "red")
header_color = '#ff1a1a' if view == 'red' else '#1a75ff'
header_icon = '🔴' if view == 'red' else '🔵'
header_label = T("header_red") if view == 'red' else T("header_blue")
st.markdown(f"<h2 style='text-align:center;color:{header_color} !important;text-shadow:0 0 8px {'rgba(255,0,0,0.4)' if view=='red' else 'rgba(0,100,255,0.3)'};'>{header_icon} {header_label}</h2>", unsafe_allow_html=True)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

try:
    summaries = get_daily_summaries(days=7)
except sqlite3.OperationalError:
    st.error("Database schema out of sync. Please reset the database.")
    summaries = []
except Exception as e:
    st.error(f"Error loading summaries: {e}")
    summaries = []

if not summaries:
    st.info(T("no_summaries"))
else:
    for s in summaries:
        date_str = s.get('date', 'Unknown date')
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            date_display = dt.strftime(T("date_fmt"))
        except:
            date_display = date_str

        content = s.get('content', '')

        st.markdown(f"<div class='summary-date-header'>{date_display}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='summary-content'>{content}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# Confidence dialog — st.dialog
# ═══════════════════════════════════════════════════════════════════

@st.dialog(T("conf_title"), width="large")
def conf_dialog():
    col_title, col_close = st.columns([6, 1])
    with col_title:
        st.markdown(f"### {T('conf_title')}")
    with col_close:
        if st.button(T("conf_close_x"), key="conf_close_x"):
            st.session_state.conf_open = False
            st.session_state.conf_dialog_open = False
            st.rerun()

    st.markdown("")

    with st.expander(T("conf_add_expander"), expanded=True):
        col_key, col_anchor, col_tier = st.columns([2, 1, 1])
        with col_key:
            new_key = st.text_input(T("conf_key_label"), key="sc_key", placeholder=T("conf_key_placeholder"))
        with col_anchor:
            new_anchor = st.number_input(T("conf_anchor_label"), key="sc_anchor", min_value=0.0, max_value=1.0, value=0.5, step=0.05, format="%.2f")
        with col_tier:
            new_tier = st.selectbox(T("conf_tier_label"), key="sc_tier", options=[T("conf_tier_high"), T("conf_tier_medium"), T("conf_tier_low")])
        new_notes = st.text_input(T("conf_notes_label"), key="sc_notes", placeholder=T("conf_notes_placeholder"))
        if st.button(T("conf_save"), key="sc_save_btn"):
            if new_key.strip():
                upsert_source_confidence(new_key.strip().lower(), new_anchor, new_tier, new_notes)
                import sys as _sys, os as _os
                _sys.path.append(_os.path.join(_os.path.dirname(__file__), '..'))
                from agent.nodes.triage import _invalidate_cache
                _invalidate_cache()
                st.rerun()
            else:
                st.error(T("conf_save_error"))

    st.markdown("")

    try:
        entries = get_all_source_confidence()
    except Exception as e:
        st.error(f"DB error: {e}")
        entries = []

    if not entries:
        st.markdown(f"<em style='color:#444;font-size:0.9em;'>{T('conf_empty')}</em>", unsafe_allow_html=True)
    else:
        hdr_col1, hdr_col2, hdr_col3, hdr_col4, hdr_col5 = st.columns([1, 2, 1, 2, 1])
        with hdr_col1:
            st.markdown(f"<div style='font-weight:600;font-size:0.8em;color:#888;'>{T('conf_col_tier')}</div>", unsafe_allow_html=True)
        with hdr_col2:
            st.markdown(f"<div style='font-weight:600;font-size:0.8em;color:#888;'>{T('conf_col_keyword')}</div>", unsafe_allow_html=True)
        with hdr_col3:
            st.markdown(f"<div style='font-weight:600;font-size:0.8em;color:#888;'>{T('conf_col_anchor')}</div>", unsafe_allow_html=True)
        with hdr_col4:
            st.markdown(f"<div style='font-weight:600;font-size:0.8em;color:#888;'>{T('conf_col_notes')}</div>", unsafe_allow_html=True)
        with hdr_col5:
            st.markdown(f"<div style='font-weight:600;font-size:0.8em;color:#888;text-align:center;'>{T('conf_col_action')}</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin:4px 0;opacity:0.2;'>", unsafe_allow_html=True)

        for entry in entries:
            tier = entry.get('tier', 'medium')
            anchor = entry.get('anchor', 0.5)
            key_val = entry.get('source_key', '')
            notes_val = entry.get('notes', '')
            row_id = entry.get('id')

            tier_badge = {
                "high": "<span style='background:#44cc66;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600;'>HIGH</span>",
                "medium": "<span style='background:#ccaa33;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600;'>MED</span>",
                "low": "<span style='background:#cc4444;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600;'>LOW</span>",
            }.get(tier, "")

            col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 2, 1])
            with col1:
                st.markdown(tier_badge, unsafe_allow_html=True)
            with col2:
                st.markdown(f"<span style='color:#e0e0e0;font-size:0.9em;font-family:monospace;'>{key_val}</span>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<span style='color:#888;font-size:0.85em;'>{anchor:.0%}</span>", unsafe_allow_html=True)
            with col4:
                st.markdown(f"<span style='color:#666;font-size:0.85em;'>{notes_val or '—'}</span>", unsafe_allow_html=True)
            with col5:
                if st.button("🗑", key=f"sc_del_{row_id}", help="delete"):
                    delete_source_confidence(row_id)
                    import sys as _sys2, os as _os2
                    _sys2.path.append(_os2.path.join(_os2.path.dirname(__file__), '..'))
                    from agent.nodes.triage import _invalidate_cache
                    _invalidate_cache()
                    st.rerun()

            st.markdown("<div style='height:2px;background:rgba(255,255,255,0.05);'></div>", unsafe_allow_html=True)

    st.markdown("")
    if st.button(T("conf_close_btn"), key="conf_close_btn", use_container_width=True):
        st.session_state.conf_open = False
        st.session_state.conf_dialog_open = False
        st.rerun()


if st.session_state.get("conf_dialog_open"):
    conf_dialog()
    st.session_state.conf_dialog_open = False
