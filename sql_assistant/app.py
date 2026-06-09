"""
app.py — SQL Assistant · Main Application
──────────────────────────────────────────
AI-powered SQL Server BI assistant supporting Arabic (Egyptian dialect)
and English questions powered by Google Gemini.

Run with:
    streamlit run app.py
"""

import os
import sys
import logging
import socket
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ── .env loading ──────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_ROOT = _HERE.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_HERE / ".env")   # standalone fallback

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(_HERE))

# ── Internal imports ──────────────────────────────────────────────────────────
from utils import (
    setup_logging, init_session_state, format_elapsed,
    confidence_badge, render_export_buttons, ensure_exports_dir,
)
from database import create_db_engine, run_query
from schema import discover_schema, build_schema_context
from ai_service import generate_sql, generate_explanation
from security import validate_sql
from visualization import render_visualization, detect_chart_type

# ── Logging ───────────────────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SQL Assistant | مساعد SQL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "SQL Assistant — AI-Powered SQL BI Assistant",
    },
)

# ── CSS injection ─────────────────────────────────────────────────────────────
_css_path = _HERE / "styles.css"
if _css_path.exists():
    st.markdown(f"<style>{_css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
init_session_state()
ensure_exports_dir()

if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "last_run_question" not in st.session_state:
    st.session_state.last_run_question = ""
if "last_error" not in st.session_state:
    st.session_state.last_error = None


# ═══════════════════════════════════════════════════════════════════════════════
# Language helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _is_arabic(text: str) -> bool:
    """True if text contains significant Arabic characters."""
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    return arabic_chars > len(text) * 0.2

def _lang_badge(lang: str) -> str:
    if lang == "arabic":
        return '<span class="lang-badge lang-badge-ar">🇪🇬 عربي</span>'
    return '<span class="lang-badge lang-badge-en">🇺🇸 English</span>'

def _dir_class(text: str) -> str:
    return "chat-bubble-ar" if _is_arabic(text) else "chat-bubble-en"

def _connection_badge() -> str:
    if st.session_state.db_connected:
        db = st.session_state.db_config.get("database", "")
        srv = st.session_state.db_config.get("server", "")
        return f'<span class="badge badge-connected">{srv} / {db} — gold schema</span>'
    return '<span class="badge badge-disconnected">غير متصل / Not Connected</span>'


# ═══════════════════════════════════════════════════════════════════════════════
# Schema explorer sidebar
# ═══════════════════════════════════════════════════════════════════════════════

def _schema_explorer_sidebar() -> None:
    schema = st.session_state.schema
    if not schema:
        st.sidebar.info("🔌 اتصل بقاعدة البيانات أولاً / Connect to the database first.")
        return

    tables  = schema.get("tables", [])
    pk_map  = schema.get("pk", {})
    fk_list = schema.get("fk", [])
    cols_map = schema.get("columns", {})

    st.sidebar.markdown(
        "<div class='section-title'>Gold Schema Explorer / مستكشف الجداول</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(f"**{len(tables)}** جداول · **{len(fk_list)}** علاقات")

    with st.sidebar.expander("gold schema", expanded=True):
        for tbl in tables:
            sch  = tbl["schema_name"]
            name = tbl["table_name"]
            ttype = tbl["table_type"]
            rc   = tbl.get("row_count")
            rc_str = f" ({rc:,} rows)" if rc is not None else ""
            key  = f"{sch}.{name}"
            pks  = pk_map.get(key, [])

            with st.expander(f"{name}{rc_str}", expanded=False):
                for col in cols_map.get(key, []):
                    cn = col["column_name"]
                    dt = col["data_type"]
                    pk_icon = " [PK]" if cn in pks else ""
                    st.markdown(
                        f"<small style='color:#94a3b8'>`{cn}` "
                        f"<span style='color:#475569'>{dt}</span>{pk_icon}</small>",
                        unsafe_allow_html=True,
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

st.sidebar.markdown(
    """
<div class="brand-logo">
  <div class="brand-logo-icon">SQL</div>
  <div class="brand-logo-text">
    <div class="brand-name">SQL Assistant</div>
    <div class="brand-tagline">AI-Powered BI Assistant</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.sidebar.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Developer Settings ──
dev_mode = st.sidebar.toggle("Developer Mode / وضع المطورين", value=False, key="dev_mode")
st.sidebar.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Connection form ───────────────────────────────────────────────────────────
with st.sidebar.expander("اتصال بقاعدة البيانات / DB Connection",
                          expanded=not st.session_state.db_connected):
    server_val = st.session_state.db_config.get("server", os.getenv("DEST_DB_HOST", socket.gethostname()))
    db_name_val = st.session_state.db_config.get("database", os.getenv("DEST_DB_NAME", "BI_AI").strip())

    server   = st.text_input("اسم السيرفر / Server Name", value=server_val,
                             placeholder="DESKTOP-UCKMQTL", key="input_server")
    instance = st.text_input("الـ Instance (اختياري / optional)", value="",
                             placeholder="SQLEXPRESS", key="input_instance")
    database = st.text_input("اسم قاعدة البيانات / Database", value=db_name_val,
                             placeholder="BI_AI", key="input_db")

    auth_choices = ["Windows Authentication", "SQL Server Authentication"]
    auth_default = 0 if os.getenv("DEST_DB_TRUSTED_CONNECTION", "yes").lower() == "yes" else 1
    auth_type = st.selectbox("نوع الاتصال / Auth Type", auth_choices,
                             index=auth_default, key="input_auth")

    username = password = ""
    if auth_type == "SQL Server Authentication":
        username = st.text_input("اسم المستخدم / Username",
                                 value=os.getenv("DEST_DB_USER", ""), key="input_user")
        password = st.text_input("كلمة المرور / Password", type="password", key="input_pass")

    col_conn, col_disc = st.columns(2)
    connect_clicked    = col_conn.button("اتصال / Connect", use_container_width=True, key="btn_connect")
    disconnect_clicked = col_disc.button("قطع الاتصال / Disconnect", use_container_width=True, key="btn_disconnect",
                                         type="secondary")

    # ── Diagnostics (Only in Developer Mode) ──────────────────────────────────
    if dev_mode:
        with st.expander("تشخيص / Diagnostics", expanded=False):
            import pyodbc as _pyodbc
            drivers = [d for d in _pyodbc.drivers() if "SQL Server" in d]
            if drivers:
                st.success(f"ODBC Drivers: `{'`, `'.join(drivers)}`")
            else:
                st.error("لا يوجد ODBC Driver مثبّت / ODBC Driver not found!")
            hostname = socket.gethostname()
            st.info(
                f"اسم الجهاز / Hostname: **`{hostname}`**\n\n"
                "استخدمه في حقل Server Name إذا كان SQL Server على جهازك.\n\n"
                "اترك Instance فارغاً إلا إذا كان SSMS يعرض `HOSTNAME\\INSTANCE`."
            )

# ── Connect logic ─────────────────────────────────────────────────────────────
if connect_clicked:
    config = {
        "server":    server,
        "instance":  instance,
        "database":  database,
        "auth_type": "windows" if auth_type == "Windows Authentication" else "sql",
        "username":  username,
        "password":  password,
    }
    with st.spinner("🔌 جارٍ الاتصال… / Connecting…"):
        engine, err = create_db_engine(config)

    if err:
        st.sidebar.error(err)
        st.session_state.db_connected = False
    else:
        st.session_state.db_engine  = engine
        st.session_state.db_config  = config
        st.session_state.db_connected = True
        with st.spinner("📐 اكتشاف الـ gold schema… / Discovering schema…"):
            try:
                schema = discover_schema(engine)
                st.session_state.schema        = schema
                st.session_state.schema_context = build_schema_context(schema)
                n = len(schema.get("tables", []))
                st.sidebar.success(f"تم الاتصال! {n} جداول في gold schema / Connected! {n} tables found")
            except Exception as e:
                st.sidebar.warning(f"اتصل لكن فشل اكتشاف الـ schema / Connected, but schema discovery failed: {e}")

if disconnect_clicked:
    for k in ["db_connected","db_engine","db_config","schema","schema_context"]:
        st.session_state[k] = None if k in ("db_engine","schema") else (False if k=="db_connected" else {} if k=="db_config" else "")
    st.sidebar.info("تم قطع الاتصال / Disconnected.")

st.sidebar.markdown(_connection_badge(), unsafe_allow_html=True)
st.sidebar.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)
if dev_mode:
    _schema_explorer_sidebar()

# ── AI Settings ───────────────────────────────────────────────────────────────
st.sidebar.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='section-title'>إعدادات الذكاء الاصطناعي / AI Settings</div>",
                    unsafe_allow_html=True)
ai_model = st.sidebar.selectbox(
    "نموذج Gemini / Model",
    [
        "models/gemini-2.5-flash-lite",
        "models/gemini-2.5-flash",
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.5-flash",
    ],
    index=0, key="ai_model",
)
auto_explain = st.sidebar.toggle("شرح تلقائي / Auto-explain", value=False, key="auto_explain")

if st.sidebar.button("مسح المحادثة / Clear Chat", use_container_width=True):
    st.session_state.chat_history  = []
    st.session_state.last_sql      = ""
    st.session_state.last_df       = None
    st.session_state.last_ai_result = None
    st.session_state.search_query  = ""
    st.session_state.last_run_question = ""
    st.session_state.last_error    = None
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
<div class="page-header">
  <h1>SQL Assistant</h1>
  <p>
    اسأل أي سؤال عن بياناتك بالعربي أو الإنجليزي — والذكاء الاصطناعي يحوّله لـ SQL ويجيبك.<br>
    Ask any business question in Arabic or English — AI converts it to SQL and answers you.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

# ── If not connected, show the connection prompt card ───────────────────────
if not st.session_state.db_connected:
    st.markdown(
        """
<div class="glass-card" style="text-align:center; padding:3.5rem 1.5rem; margin-top:1rem;">
  <div class="brand-logo-icon" style="margin: 0 auto 1.5rem; width: 52px; height: 52px; font-size: 1.2rem;">DB</div>
  <div style="font-family:'Cairo',sans-serif; font-size:1.25rem; font-weight:600;
              color:#e2e8f0; margin-bottom:0.75rem;">
    الرجاء الاتصال بقاعدة البيانات للبدء<br>
    <span style="font-size:0.95rem; color:#94a3b8;">Please connect to the database in the sidebar to start</span>
  </div>
  <div style="color:#94a3b8; font-size:0.9rem; max-width:480px; margin:0 auto; line-height:1.75;">
    افتح نموذج الاتصال في القائمة الجانبية (DB Connection)، وأدخل بيانات سيرفر SQL Server لتفعيل المساعد الذكي.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
else:
    # ── Connected workspace ───────────────────────────────────────────────────

    # Search Bar (acts like browser URL input)
    question = st.text_input(
        "سؤالك / Your Question",
        value=st.session_state.search_query,
        placeholder="اسأل سؤالك هنا بالعربي أو الإنجليزي...  |  Ask your question here in Arabic or English...",
        label_visibility="collapsed",
        key="question_input_bar",
    )

    # Trigger run when question changes
    if question and question.strip() != st.session_state.get("last_run_question", ""):
        st.session_state.last_run_question = question.strip()
        st.session_state.search_query = question.strip()
        st.session_state.last_error = None
        st.session_state.last_df = None
        st.session_state.last_ai_result = None

        ts_now = datetime.now().strftime("%H:%M:%S")
        q_lang = "arabic" if _is_arabic(question) else "english"
        st.session_state.chat_history.append(
            {"role": "user", "content": question.strip(), "ts": ts_now, "lang": q_lang}
        )

        with st.spinner("🤖 جارٍ توليد SQL… / Generating SQL…"):
            ai_result = generate_sql(
                question=question.strip(),
                schema_context=st.session_state.schema_context,
                model=ai_model,
                chat_history=st.session_state.chat_history,
            )

        if ai_result.get("error"):
            err_msg = ai_result["error"]
            st.session_state.last_error = f"🤖 خطأ في توليد الاستعلام / AI Generation Failure:\n{err_msg}"
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"⚠️ خطأ: {err_msg}",
                "ts": datetime.now().strftime("%H:%M:%S"),
                "lang": q_lang,
            })
        else:
            sql        = ai_result.get("sql", "").strip()
            biz_exp    = ai_result.get("business_explanation", "")
            confidence = ai_result.get("confidence", 0)
            ai_lang    = ai_result.get("detected_language", q_lang)

            st.session_state.last_sql       = sql
            st.session_state.last_ai_result = ai_result

            # Security check
            validation = validate_sql(sql)
            if not validation.is_safe:
                st.session_state.last_error = f"🔒 انتهاك قواعد الحماية / Security Validation Failed:\n{validation.message}"
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": validation.message,
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "lang": ai_lang,
                })
            else:
                # Execute
                with st.spinner("⚡ تنفيذ الاستعلام… / Running query…"):
                     df, elapsed, err = run_query(st.session_state.db_engine, sql)

                ts_done = datetime.now().strftime("%H:%M:%S")

                if err:
                    st.session_state.last_error = f"⚠️ فشل تنفيذ الاستعلام على قاعدة البيانات / SQL Execution Error:\n{err}"
                    reply = f"⚠️ فشل الاستعلام / Query failed:\n{err}\n\n```sql\n{sql}\n```"
                    st.session_state.chat_history.append({
                        "role": "assistant", "content": reply,
                        "ts": ts_done, "lang": ai_lang,
                    })
                else:
                    st.session_state.last_df      = df
                    st.session_state.last_elapsed = elapsed
                    st.session_state.query_count  += 1

                    badge = confidence_badge(confidence)
                    meta  = (
                        f"<br><small style='color:#475569;direction:ltr;display:block'>"
                        f"{badge} دقة: {confidence}% · ⚡ {format_elapsed(elapsed)} · 📋 {len(df):,} صف"
                        f"</small>"
                    )
                    reply = (biz_exp or "") + meta
                    st.session_state.chat_history.append({
                        "role": "assistant", "content": reply,
                        "ts": ts_done, "lang": ai_lang,
                    })
        st.rerun()

    # ── Quick Starts (only if no query has been run yet) ──────────────────────
    if not st.session_state.last_sql:
        st.markdown(
            "<div class='section-title' style='text-align:center; margin-top:1rem;'>أسئلة مقترحة / Suggested Questions</div>",
            unsafe_allow_html=True
        )
        prompts = [
            "وريني الجداول الموجودة في الـ gold schema وعدد الصفوف في كل جدول",
            "ايه أعلى 10 منتجات من حيث المبيعات؟",
            "Show total revenue by month for the current year",
            "Which customers have the highest lifetime value?",
        ]
        cols = st.columns(2)
        for i, p in enumerate(prompts):
            if cols[i % 2].button(p, key=f"quick_{i}", use_container_width=True):
                st.session_state.search_query = p
                st.session_state.last_run_question = ""
                st.session_state.last_error = None
                st.rerun()

    # ── Error display (if any) ────────────────────────────────────────────────
    if st.session_state.last_error:
        st.markdown(
            f"""
<div class="glass-card" style="border-left: 4px solid var(--accent-rose); margin-top: 1.5rem;">
  <div class="section-title" style="color: var(--accent-rose);">خطأ / Error</div>
  <div style="font-size: 1rem; line-height: 1.75; color: var(--text-primary);" class="bidi-text" dir="auto">
    {st.session_state.last_error.replace(chr(10), '<br>')}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    # ── Results display ───────────────────────────────────────────────────────
    if st.session_state.last_ai_result:
        ai_r = st.session_state.last_ai_result
        biz_exp = ai_r.get("business_explanation", "")
        confidence = ai_r.get("confidence", 0)
        badge = confidence_badge(confidence)
        ai_lang = ai_r.get("detected_language", "english")
        elapsed = st.session_state.last_elapsed
        df = st.session_state.last_df

        # 1. AI Business Explanation Card (only if successful and text exists)
        if df is not None and biz_exp:
            if dev_mode:
                st.markdown(
                    f"""
<div class="glass-card" style="margin-top: 1.5rem;">
  <div class="section-title">AI Insights / تحليلات المساعد الذكي</div>
  <div style="font-size: 1.1rem; line-height: 1.7; margin-bottom: 1rem;" class="bidi-text" dir="auto">
    {biz_exp}
  </div>
  <div style="display: flex; gap: 1.2rem; align-items: center; border-top: 1px solid var(--border); padding-top: 0.8rem; font-size: 0.82rem; color: var(--text-secondary);">
    <span>{badge} <strong>{confidence}%</strong> دقة / Confidence</span>
    <span>⚡ <strong>{format_elapsed(elapsed)}</strong> زمن التنفيذ / Executed in</span>
    <span>🤖 <strong>{ai_r.get('model_used', 'Gemini')}</strong></span>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
<div class="glass-card" style="margin-top: 1.5rem;">
  <div class="section-title">Business Insights / تحليلات الأعمال</div>
  <div style="font-size: 1.1rem; line-height: 1.7; color: var(--text-primary);" class="bidi-text" dir="auto">
    {biz_exp}
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

        # 2. Collapsible SQL Workshop & Editor (Only shown in Developer Mode)
        if dev_mode:
            with st.expander("تفاصيل الاستعلام الفنية / SQL Query & Technical Details", expanded=False):
                sql_input = st.text_area(
                    "استعلام SQL (قابل للتعديل / Editable SQL)",
                    value=st.session_state.last_sql,
                    height=220,
                    key="sql_editor",
                )

                col_run, col_validate, col_explain = st.columns(3)
                run_clicked      = col_run.button("Run / تشغيل", use_container_width=True, key="btn_run_sql")
                validate_clicked = col_validate.button("Validate / تحقق", use_container_width=True, key="btn_validate")
                explain_clicked  = col_explain.button("Explain / شرح", use_container_width=True, key="btn_explain")

                if validate_clicked and sql_input.strip():
                    res = validate_sql(sql_input.strip())
                    if res.is_safe:
                        st.success(res.message)
                    else:
                        st.error(res.message)

                if run_clicked and sql_input.strip():
                    v = validate_sql(sql_input.strip())
                    if not v.is_safe:
                        st.error(v.message)
                    else:
                        with st.spinner("⚡ تشغيل… / Running…"):
                            new_df, new_elapsed, err = run_query(st.session_state.db_engine, sql_input.strip())
                        if err:
                            st.session_state.last_error = f"⚠️ فشل استعلام قاعدة البيانات / Database Query Failed:\n\n{err}"
                            st.session_state.last_df = None
                            st.success("تم إرسال الخطأ للشاشة الرئيسية / Error outputted to main dashboard.")
                            st.rerun()
                        else:
                            st.session_state.last_df      = new_df
                            st.session_state.last_elapsed = new_elapsed
                            st.session_state.last_sql     = sql_input.strip()
                            st.session_state.last_error   = None
                            st.success(f"✅ {len(new_df):,} صف في {format_elapsed(new_elapsed)}")
                            st.rerun()

                if explain_clicked and sql_input.strip():
                    preview = df.head(5).to_string(index=False) if df is not None else ""
                    with st.spinner("🤖 شرح الاستعلام… / Generating explanation…"):
                        exp = generate_explanation(sql_input.strip(), preview,
                                                   st.session_state.schema_context, ai_lang)
                    st.markdown(
                        f"""<div class="glass-card" style="margin-top: 1rem;">
  <div class="section-title">شرح فني / Technical Explanation</div>
  <div class="bidi-text" dir="auto">{exp}</div>
</div>""",
                        unsafe_allow_html=True,
                    )

                sql_exp = ai_r.get("sql_explanation", "")
                if sql_exp:
                    st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)
                    st.markdown(
                        f"""<div class="bidi-text" dir="auto" style="font-size: 0.9rem; line-height: 1.7; color: var(--text-secondary);">
  <strong>كيف يعمل هذا الاستعلام؟ / How does this query work?</strong><br>
  {sql_exp.replace(chr(10), '<br>')}
</div>""",
                        unsafe_allow_html=True,
                    )

        # 3. Output Elements (only if df is not None)
        if df is not None:
            # 3a. Data Table & Export
            st.markdown("<div class='section-title' style='margin-top: 1.5rem;'>جدول البيانات / Data Table</div>", unsafe_allow_html=True)

            if dev_mode:
                # Only show technical row counts / timing bar in developer mode
                rows, cols_count = df.shape
                st.markdown(
                    f"""
<div class="conn-status-bar">
  <strong>{rows:,}</strong> صف / {rows:,} rows &nbsp;·&nbsp;
  <strong>{cols_count}</strong> عمود / {cols_count} columns &nbsp;·&nbsp;
  Executed in: {format_elapsed(elapsed)} &nbsp;·&nbsp;
  Query #{st.session_state.query_count}
</div>
""",
                    unsafe_allow_html=True,
                )

            st.dataframe(df, use_container_width=True, height=350)
            render_export_buttons(df, label="query")

            # 3b. Visualization (Chart below Table)
            st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>الرسم البياني / Visualization</div>", unsafe_allow_html=True)

            chart_hint = ai_r.get("chart_suggestion", "table")
            auto_type = detect_chart_type(df, chart_hint)
            chart_options = ["auto", "bar", "line", "pie", "scatter", "table", "kpi"]

            col_sel, _ = st.columns([2, 4])
            selected_chart = col_sel.selectbox(
                "نوع الرسم / Chart Type", chart_options,
                index=chart_options.index(auto_type) if auto_type in chart_options else 0,
                key="chart_type_select",
            )
            final_chart = auto_type if selected_chart == "auto" else selected_chart

            if final_chart != "table":
                render_visualization(
                    df, chart_type=final_chart,
                    title=f"تمثيل بياني للبيانات / Visualized Data",
                )
            else:
                st.info("تم تحديد الجدول كأفضل تمثيل لهذه البيانات. اختر نوعاً آخر من القائمة أعلاه إذا أردت رسمها. / The table has been selected as the best representation of this data. Choose another chart type from the list above if you want to plot it.")

    # ── Past Questions History (collapsible at the bottom - Developer Mode only) ──
    if dev_mode and len(st.session_state.chat_history) > 1:
        st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)
        with st.expander("سجل الأسئلة السابقة / View Past Questions", expanded=False):
            # Show history except the very last turn which is currently active
            for turn in st.session_state.chat_history[:-2]:
                role    = turn["role"]
                content = turn["content"]
                ts      = turn.get("ts", "")
                lang    = turn.get("lang", "english")
                dir_cls = _dir_class(content)

                if role == "user":
                    st.markdown(
                        f"""
<div class="chat-bubble-user {dir_cls}">
  <div class="chat-meta">👤 · {ts} {_lang_badge(lang)}</div>
  {content}
</div>
""",
                        unsafe_allow_html=True,
                    )
                else:
                    ai_html = content.replace("\n", "<br>")
                    st.markdown(
                        f"""
<div class="chat-bubble-ai {dir_cls}">
  <div class="chat-meta">🤖 SQL Assistant · {ts} {_lang_badge(lang)}</div>
  {ai_html}
</div>
""",
                        unsafe_allow_html=True,
                    )

    # ── Database Schema Details (collapsible at the bottom) ──────────────────
    if dev_mode and st.session_state.schema:
        st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)
        with st.expander("مواصفات قاعدة البيانات والـ Schema / View Database Schema & Relationships", expanded=False):
            import pandas as pd
            schema   = st.session_state.schema
            tables   = schema.get("tables", [])
            fk_list  = schema.get("fk", [])
            pk_map   = schema.get("pk", {})
            cols_map = schema.get("columns", {})

            n_base  = sum(1 for t in tables if t["table_type"] == "BASE TABLE")
            n_views = sum(1 for t in tables if t["table_type"] == "VIEW")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("جداول / Tables", n_base)
            m2.metric("Views", n_views)
            m3.metric("علاقات / Relationships", len(fk_list))
            m4.metric("أعمدة / Columns", sum(len(v) for v in cols_map.values()))

            search = st.text_input("بحث في الجداول / Search Tables", placeholder="اسم جدول أو عمود…", key="schema_search_main")

            for tbl in tables:
                sname = tbl["schema_name"]
                tname = tbl["table_name"]
                ttype = tbl["table_type"]
                key   = f"{sname}.{tname}"
                pks   = pk_map.get(key, [])
                cols  = cols_map.get(key, [])
                rc    = tbl.get("row_count")

                if search and (
                    search.lower() not in tname.lower()
                    and not any(search.lower() in c["column_name"].lower() for c in cols)
                ):
                    continue

                icon   = "📋" if ttype == "BASE TABLE" else "👁"
                rc_str = f" ({rc:,} rows)" if rc is not None else ""
                with st.expander(f"gold.{tname}{rc_str}", expanded=False):
                    if cols:
                        col_data = [{
                            "العمود / Column": c["column_name"],
                            "النوع / Type":    c["data_type"],
                            "NULL?":           c["is_nullable"],
                            "PK":              "PK" if c["column_name"] in pks else "",
                        } for c in cols]
                        st.dataframe(pd.DataFrame(col_data), use_container_width=True, hide_index=True)

            if fk_list:
                st.markdown("<div class='section-title'>العلاقات / Relationships</div>",
                            unsafe_allow_html=True)
                fk_df = pd.DataFrame(fk_list).rename(columns={
                    "from_table": "من / From", "from_column": "عمود / Col",
                    "to_table":   "إلى / To",  "to_column":   "عمود / Col ",
                })
                st.dataframe(fk_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    """
<div class="app-footer">
  SQL Assistant &nbsp;·&nbsp; مدعوم بـ Google Gemini و SQL Server<br>
  Powered by Google Gemini &amp; Microsoft SQL Server &nbsp;·&nbsp; Built with Python &amp; Streamlit
</div>
""",
    unsafe_allow_html=True,
)
