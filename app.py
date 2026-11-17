# ============================================================================
# 檔案名稱：app.py (Microsoft SQL Server / SSMS 22 完整優化版)
# 專案名稱：JLPT 日語能力測驗模擬題庫與作答分析系統
# 執行指令：streamlit run app.py
# ============================================================================

from datetime import datetime
import pandas as pd
import pyodbc
import streamlit as st

st.set_page_config(
    page_title="JLPT 日語能力測驗模擬題庫與作答分析系統",
    page_icon="🎌",
    layout="wide",
)


# ----------------------------------------------------------------------------
# 快取 ODBC 驅動偵測（避免每次點擊按鈕都重新掃描系統驅動）
# ----------------------------------------------------------------------------
@st.cache_resource
def detect_sql_driver():
  installed = pyodbc.drivers()
  preferred = [
      "ODBC Driver 18 for SQL Server",
      "ODBC Driver 17 for SQL Server",
      "ODBC Driver 13 for SQL Server",
      "SQL Server Native Client 11.0",
      "SQL Server",
  ]
  for drv in preferred:
    if drv in installed:
      return drv
  return installed[0] if installed else "ODBC Driver 18 for SQL Server"


# ----------------------------------------------------------------------------
# 側邊欄：SQL Server (SSMS 22) 連線設定（預設 .\SQLEXPRESS）
# ----------------------------------------------------------------------------
st.sidebar.title("⚙️ SQL Server 連線設定")
st.sidebar.caption("對應 SQL Server Management Studio 22 (SSMS) 登入設定")

default_driver = detect_sql_driver()
db_server = st.sidebar.text_input(
    "伺服器名稱 (Server Name)",
    value=r".\SQLEXPRESS",
    help="預設已設為 .\\SQLEXPRESS，若不同請填寫與 SSMS 登入視窗相同的名稱",
)
db_name = st.sidebar.text_input("資料庫名稱 (Database)", value="jlpt_db")
auth_mode = st.sidebar.radio(
    "驗證方式 (Authentication)",
    ["Windows 驗證 (SSMS 預設免密碼)", "SQL Server 驗證 (帳號密碼)"],
)

db_user = ""
db_password = ""
if auth_mode == "SQL Server 驗證 (帳號密碼)":
  db_user = st.sidebar.text_input("登入帳號 (Login)", value="sa")
  db_password = st.sidebar.text_input(
      "密碼 (Password)", value="", type="password"
  )


def get_connection():
  """建立並回傳 SQL Server (pyodbc) 連線（附帶 5 秒逾時保護）"""
  if auth_mode.startswith("Windows"):
    conn_str = (
        f"DRIVER={{{default_driver}}};"
        f"SERVER={db_server};"
        f"DATABASE={db_name};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
  else:
    conn_str = (
        f"DRIVER={{{default_driver}}};"
        f"SERVER={db_server};"
        f"DATABASE={db_name};"
        f"UID={db_user};"
        f"PWD={db_password};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
  return pyodbc.connect(conn_str, timeout=5, autocommit=False)


def run_query(sql, params=None):
  """執行 SELECT 查詢並回傳 List of Dicts"""
  conn = get_connection()
  try:
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
  finally:
    conn.close()


# ----------------------------------------------------------------------------
# 檢查資料庫連線與讀取頂部 KPI
# ----------------------------------------------------------------------------
try:
  kpi_data = run_query("""
        SELECT
            (SELECT COUNT(*) FROM dbo.Users) AS user_count,
            (SELECT COUNT(*) FROM dbo.Questions) AS question_count,
            (SELECT COUNT(*) FROM dbo.Tests) AS test_count,
            (SELECT COUNT(*) FROM dbo.Test_Details) AS detail_count,
            (SELECT ROUND(AVG(CAST(is_correct AS FLOAT)) * 100, 1) FROM dbo.Test_Details) AS overall_acc
    """)[0]
  st.sidebar.success(
      f"✅ 已連線至 `{db_name}`\n\n驅動：`{default_driver}`"
  )
except Exception as e:
  st.title("🎌 JLPT 日語能力測驗模擬題庫與作答分析系統 (SQL Server 版)")
  st.error(
      f"⚠️ 無法連線至 SQL Server 資料庫：{e}\n\n"
      "**請檢查以下兩點：**\n"
      "1. 已在 **SSMS 22** 執行 `schema.sql` 與 `seed.sql` 建立 `jlpt_db`。\n"
      "2. 左側邊欄的 **「伺服器名稱」** 需與 SSMS 登入畫面相同（例如"
      " `.\\SQLEXPRESS` 或 `localhost`）。"
  )
  st.stop()

# ----------------------------------------------------------------------------
# 頁首標題與 KPI 指標卡
# ----------------------------------------------------------------------------
st.title("🎌 JLPT 日語能力測驗模擬題庫與作答分析系統")
st.markdown(
    "**資工系「資料庫系統」期末專題 DEMO (MS SQL Server / SSMS 22)** ｜"
    " 3NF 正規化架構 ‧ 題庫池動態抽樣 (`ORDER BY NEWID()`) ‧ 多表 JOIN 聚合統計"
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("👤 註冊考生數 (Users)", f"{kpi_data['user_count']} 人")
col2.metric("📚 題庫母體數 (Questions)", f"{kpi_data['question_count']} 題")
col3.metric("📝 累計測驗場次 (Tests)", f"{kpi_data['test_count']} 場")
col4.metric("🗂️ 作答明細數 (Test_Details)", f"{kpi_data['detail_count']} 筆")
col5.metric("🎯 全系統平均正確率", f"{kpi_data['overall_acc'] or 0}%")

st.divider()

# ----------------------------------------------------------------------------
# 獨立分頁導覽列（每次只執行目前所在分頁的 SQL，徹底避免多頁同時查詢卡頓）
# ----------------------------------------------------------------------------
page = st.radio(
    "請選擇展示功能模組：",
    [
        "📊 1. 歷史統計與錯題分析報表（開場展示）",
        "✏️ 2. 線上隨機抽題測驗（現場即時寫入）",
        "🗄️ 3. 題庫母體與 3NF 架構檢視",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

st.write("")

# ============================================================================
# 頁面 1: 歷史統計與錯題分析報表
# ============================================================================
if page.startswith("📊 1."):
  st.subheader("🔥 全系統 TOP 5 高頻錯題排行（Questions JOIN Test_Details）")

  top5_sql = """
        SELECT TOP 5
            q.question_id AS [題號],
            q.level AS [級別],
            q.category AS [題型分類],
            q.question_text AS [日文題目],
            COUNT(td.detail_id) AS [總作答次數],
            SUM(CASE WHEN td.is_correct = 0 THEN 1 ELSE 0 END) AS [答錯次數],
            CAST(ROUND(SUM(CASE WHEN td.is_correct = 0 THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(td.detail_id), 1) AS FLOAT) AS [錯誤率(%)],
            q.correct_answer AS [正確答案],
            q.explanation AS [繁體中文詳解]
        FROM dbo.Questions q
        JOIN dbo.Test_Details td ON q.question_id = td.question_id
        GROUP BY q.question_id, q.level, q.category, q.question_text, q.correct_answer, q.explanation
        HAVING COUNT(td.detail_id) >= 3
        ORDER BY [錯誤率(%)] DESC, [答錯次數] DESC;
    """

  with st.expander("🔍 點擊展開：檢視「TOP 5 高頻錯題排行」底層 T-SQL 聚合查詢"):
    st.code(top5_sql, language="sql")

  top5_rows = run_query(top5_sql)
  if top5_rows:
    df_top5 = pd.DataFrame(top5_rows)

    chart_col, table_col = st.columns([1, 2])
    with chart_col:
      chart_df = df_top5.copy()
      chart_df["題目標籤"] = chart_df.apply(
          lambda r: f"#{r['題號']} ({r['級別']}-{r['題型分類']})", axis=1
      )
      st.bar_chart(
          chart_df.set_index("題目標籤")["錯誤率(%)"],
          color="#E63946",
      )
    with table_col:
      st.dataframe(
          df_top5[[
              "題號",
              "級別",
              "題型分類",
              "日文題目",
              "總作答次數",
              "答錯次數",
              "錯誤率(%)",
              "正確答案",
              "繁體中文詳解",
          ]],
          use_container_width=True,
          hide_index=True,
      )

  st.divider()

  st.subheader(
      "🎯 特定學生弱點題型分析與歷史成績（Users ➔ Tests ➔ Test_Details ➔"
      " Questions 四表 JOIN）"
  )

  users_list = run_query(
      "SELECT user_id, username, email, target_level FROM dbo.Users ORDER BY"
      " user_id"
  )
  user_options = {
      f"#{u['user_id']} {u['username']} (目標：{u['target_level']} /"
      f" {u['email']})": u["user_id"]
      for u in users_list
  }

  selected_user_label = st.selectbox(
      "請選擇要分析的考生：", list(user_options.keys())
  )
  selected_user_id = user_options[selected_user_label]

  weakness_sql = """
        SELECT 
            q.category AS [題型分類],
            COUNT(td.detail_id) AS [總作答題數],
            SUM(CASE WHEN td.is_correct = 1 THEN 1 ELSE 0 END) AS [答對題數],
            SUM(CASE WHEN td.is_correct = 0 THEN 1 ELSE 0 END) AS [答錯題數],
            CAST(ROUND(AVG(CAST(td.is_correct AS FLOAT)) * 100.0, 1) AS FLOAT) AS [正確率(%)]
        FROM dbo.Users u
        JOIN dbo.Tests t ON u.user_id = t.user_id
        JOIN dbo.Test_Details td ON t.test_id = td.test_id
        JOIN dbo.Questions q ON td.question_id = q.question_id
        WHERE u.user_id = ?
        GROUP BY q.category
        ORDER BY [正確率(%)] ASC;
    """

  history_sql = """
        SELECT 
            t.test_id AS [測驗編號],
            t.test_level AS [測驗級別],
            t.total_score AS [測驗總分],
            COUNT(td.detail_id) AS [作答題數],
            SUM(CAST(td.is_correct AS INT)) AS [答對題數],
            CONVERT(VARCHAR(19), t.end_time, 120) AS [完考時間]
        FROM dbo.Tests t
        LEFT JOIN dbo.Test_Details td ON t.test_id = td.test_id
        WHERE t.user_id = ?
        GROUP BY t.test_id, t.test_level, t.total_score, t.end_time
        ORDER BY t.test_id DESC;
    """

  with st.expander("🔍 點擊展開：檢視「學生弱點題型四表 JOIN」底層 T-SQL 查詢"):
    st.code(weakness_sql, language="sql")

  col_w1, col_w2 = st.columns(2)
  with col_w1:
    st.markdown("##### 📌 各題型正確率與弱點診斷")
    weakness_rows = run_query(weakness_sql, (selected_user_id,))
    if weakness_rows:
      df_weak = pd.DataFrame(weakness_rows)
      st.dataframe(df_weak, use_container_width=True, hide_index=True)
      worst_cat = df_weak.iloc[0]
      st.warning(
          f"💡 **診斷建議**：該生在「**{worst_cat['題型分類']}**」正確率最低"
          f"（僅 **{worst_cat['正確率(%)']}%**，累計答錯 {worst_cat['答錯題數']} 題），建議優先加強！"
      )
    else:
      st.info("該考生尚無作答紀錄，完成測驗後即會顯示分析結果。")

  with col_w2:
    st.markdown("##### 📈 歷次測驗紀錄與明細")
    history_rows = run_query(history_sql, (selected_user_id,))
    if history_rows:
      df_hist = pd.DataFrame(history_rows)
      st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
      st.info("尚無歷次測驗紀錄。")

# ============================================================================
# 頁面 2: 線上隨機抽題測驗（現場即時寫入，選項預設全空白不預選）
# ============================================================================
elif page.startswith("✏️ 2."):
  st.subheader("✏️ 題庫池隨機抽樣測驗（Pool Sampling & 即時交易寫入）")
  st.caption(
      "透過 SQL Server `SELECT TOP (?) * FROM dbo.Questions WHERE level = ?"
      " ORDER BY NEWID()` 從母體隨機抽題；交卷時以 Transaction 同步寫入"
      " `Tests` 與 `Test_Details`。"
  )

  users_list = run_query(
      "SELECT user_id, username, email, target_level FROM dbo.Users ORDER BY"
      " user_id"
  )
  user_options = {
      f"#{u['user_id']} {u['username']} (目標：{u['target_level']} /"
      f" {u['email']})": u["user_id"]
      for u in users_list
  }

  with st.expander("➕ 新增現場 DEMO 測試考生（選填）"):
    with st.form("add_user_form"):
      nu_col1, nu_col2, nu_col3 = st.columns(3)
      new_username = nu_col1.text_input("考生姓名", placeholder="例如：評審教授")
      new_email = nu_col2.text_input(
          "Email (UNIQUE)", placeholder="prof@csie.edu.tw"
      )
      new_target = nu_col3.selectbox(
          "目標級別", ["N5", "N4", "N3", "N2", "N1"], index=2
      )
      if st.form_submit_button("建立考生帳號"):
        if new_username.strip() and new_email.strip():
          try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO dbo.Users (username, email, target_level) VALUES"
                " (?, ?, ?)",
                (new_username.strip(), new_email.strip(), new_target),
            )
            conn.commit()
            conn.close()
            st.success(f"🎉 已成功新增考生：{new_username}！")
            st.rerun()
          except Exception as ex:
            st.error(f"新增失敗（請確認 Email 是否重複）：{ex}")
        else:
          st.warning("請填寫完整的姓名與 Email。")

  # 預設自動選取最後一位新增的考生
  option_labels = list(user_options.keys())
  default_idx = len(option_labels) - 1 if len(option_labels) > 10 else 0

  q_col1, q_col2, q_col3, q_col4 = st.columns([2, 1, 1, 1])
  quiz_user_label = q_col1.selectbox(
      "應考學生身分", option_labels, index=default_idx, key="quiz_user"
  )
  quiz_user_id = user_options[quiz_user_label]
  quiz_level = q_col2.selectbox(
      "選擇測驗難度", ["N5", "N4", "N3", "N2", "N1"], index=0
  )
  quiz_limit = q_col3.selectbox(
      "抽題數量",
      options=[3, 6, 10],
      index=0,
      format_func=lambda x: f"{x} 題 (現場快速 DEMO)"
      if x == 3
      else f"{x} 題 (標準模擬)",
  )

  if q_col4.button(
      "🎲 隨機抽題開始測驗", type="primary", use_container_width=True
  ):
    sampled_questions = run_query(
        f"SELECT TOP ({int(quiz_limit)}) * FROM dbo.Questions WHERE level = ?"
        " ORDER BY NEWID()",
        (quiz_level,),
    )
    st.session_state["active_quiz"] = sampled_questions
    st.session_state["quiz_level"] = quiz_level
    st.session_state["quiz_user_id"] = quiz_user_id
    st.session_state["quiz_start_time"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    st.session_state.pop("last_quiz_result", None)

  if "active_quiz" in st.session_state and st.session_state["active_quiz"]:
    questions = st.session_state["active_quiz"]
    st.info(
        f"📌 目前進行：**{st.session_state['quiz_level']} 級隨機測驗** "
        f"（共 {len(questions)} 題，開考時間：{st.session_state['quiz_start_time']}）"
    )

    with st.form("quiz_submission_form"):
      user_answers = {}
      for idx, q in enumerate(questions, start=1):
        st.markdown(
            f"**第 {idx} 題 【{q['level']} - {q['category']}】"
            f" (題庫編號 #{q['question_id']})**"
        )
        st.markdown(f"#### {q['question_text']}")
        choice = st.radio(
            f"請選擇第 {idx} 題答案：",
            options=["A", "B", "C", "D"],
            index=None,
            format_func=lambda opt, q=q: f"{opt}. {q[f'option_{opt.lower()}']}",
            key=f"q_radio_{q['question_id']}",
        )
        user_answers[q["question_id"]] = choice
        st.divider()

      submitted = st.form_submit_button(
          "📤 交卷並即時寫入 SQL Server (Tests & Test_Details)",
          type="primary",
          use_container_width=True,
      )

      if submitted:
        if None in user_answers.values():
          st.warning("⚠️ 尚有題目未作答，請完成所有題目後再按交卷！")
        else:
          correct_count = 0
          detail_records = []
          for q in questions:
            qid = q["question_id"]
            u_choice = user_answers[qid]
            is_corr = 1 if u_choice == q["correct_answer"] else 0
            correct_count += is_corr
            detail_records.append((qid, u_choice, is_corr))

          total_score = round((correct_count / len(questions)) * 100)
          end_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          conn = get_connection()
          try:
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO dbo.Tests (user_id, test_level, total_score, start_time, end_time)
                            OUTPUT INSERTED.test_id
                            VALUES (?, ?, ?, ?, ?);
                            """,
                (
                    st.session_state["quiz_user_id"],
                    st.session_state["quiz_level"],
                    total_score,
                    st.session_state["quiz_start_time"],
                    end_time_str,
                ),
            )
            new_test_id = int(cursor.fetchone()[0])

            for qid, u_choice, is_corr in detail_records:
              cursor.execute(
                  """
                                INSERT INTO dbo.Test_Details (test_id, question_id, user_choice, is_correct)
                                VALUES (?, ?, ?, ?);
                                """,
                  (new_test_id, qid, u_choice, is_corr),
              )
            conn.commit()
            st.session_state["last_quiz_result"] = {
                "test_id": new_test_id,
                "total_score": total_score,
                "correct_count": correct_count,
                "total_q": len(questions),
                "questions": questions,
                "user_answers": user_answers,
            }
            del st.session_state["active_quiz"]
            st.rerun()
          except Exception as e:
            conn.rollback()
            st.error(f"寫入資料庫失敗，已執行 Transaction Rollback：{e}")
          finally:
            conn.close()

  if "last_quiz_result" in st.session_state:
    res = st.session_state["last_quiz_result"]
    st.success(
        f"✅ **交卷成功！已即時寫入 SQL Server** ➔ 新增測驗總表 `Tests.test_id = {res['test_id']}`，"
        f"並寫入 {res['total_q']} 筆明細至 `Test_Details`！"
    )
    st.metric(
        "🏆 本次測驗得分",
        f"{res['total_score']} 分",
        f"答對 {res['correct_count']} / {res['total_q']} 題",
    )

    st.markdown("### 📖 逐題批改與繁體中文詳解")
    for idx, q in enumerate(res["questions"], start=1):
      qid = q["question_id"]
      u_ans = res["user_answers"][qid]
      c_ans = q["correct_answer"]
      is_ok = u_ans == c_ans
      badge = "✅ 答對" if is_ok else "❌ 答錯"

      with st.expander(
          f"第 {idx} 題 ({badge})：{q['question_text']} ｜ 您的作答：{u_ans} ／"
          f" 正確答案：{c_ans}",
          expanded=True,
      ):
        st.write(
            f"- **A:** {q['option_a']} | **B:** {q['option_b']} | "
            f"**C:** {q['option_c']} | **D:** {q['option_d']}"
        )
        st.info(f"**【繁體中文詳解】**\n{q['explanation']}")

# ============================================================================
# 頁面 3: 題庫母體與 3NF 架構檢視
# ============================================================================
elif page.startswith("🗄️ 3."):
  st.subheader("🗄️ 3NF 正規化資料表架構 (SQL Server T-SQL 版)")
  st.markdown("""
    - **第三正規化 (3NF) 與 SQL Server 實作重點**：
      1. `dbo.Users`：考生基本資料表，主鍵採用 `IDENTITY(1,1)` 自動遞增。
      2. `dbo.Questions`：題庫母體表，日文題目與中文詳解採用 `NVARCHAR` 搭配 `N'...'` Unicode 編碼儲存，與作答紀錄解耦。
      3. `dbo.Tests`：測驗總表（1 對多關聯於 `Users`），交卷時利用 `OUTPUT INSERTED.test_id` 即時取回主鍵。
      4. `dbo.Test_Details`：作答明細中介表，打散 `Tests` 與 `Questions` 的多對多（M:N）關聯，並設定 `ON DELETE CASCADE`。
    """)

  st.divider()
  st.subheader("📚 題庫母體檢索器（共 50 題原創試題）")
  f_col1, f_col2 = st.columns(2)
  filter_level = f_col1.multiselect(
      "篩選級別 (Level)",
      ["N5", "N4", "N3", "N2", "N1"],
      default=["N5", "N4", "N3", "N2", "N1"],
  )
  filter_cat = f_col2.multiselect(
      "篩選題型分類 (Category)",
      ["文字語彙", "文法", "讀解"],
      default=["文字語彙", "文法", "讀解"],
  )

  if filter_level and filter_cat:
    lvl_placeholders = ",".join(["?"] * len(filter_level))
    cat_placeholders = ",".join(["?"] * len(filter_cat))
    q_bank_sql = f"""
            SELECT 
                question_id AS [題號],
                level AS [級別],
                category AS [分類],
                question_text AS [日文題目],
                option_a AS [選項A],
                option_b AS [選項B],
                option_c AS [選項C],
                option_d AS [選項D],
                correct_answer AS [正解],
                explanation AS [繁體中文詳解]
            FROM dbo.Questions
            WHERE level IN ({lvl_placeholders})
              AND category IN ({cat_placeholders})
            ORDER BY question_id ASC;
        """
    bank_rows = run_query(q_bank_sql, tuple(filter_level + filter_cat))
    st.dataframe(
        pd.DataFrame(bank_rows), use_container_width=True, hide_index=True
    )