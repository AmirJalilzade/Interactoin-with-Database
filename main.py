# import os
# import json
# from typing import Dict, Any, List
# from typing_extensions import TypedDict

# # Imports برای مدیریت دیتابیس و نمودارها
# from sqlalchemy import create_engine, text
# import matplotlib
# matplotlib.use('Agg')  # جلوگیری از خطاهای محیط‌های بدون رابط گرافیکی (Headless)
# import matplotlib.pyplot as plt

# # Imports مربوط به LangChain و LangGraph
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import JsonOutputParser
# from langgraph.graph import StateGraph, END

# # وارد کردن سرویس‌های اختصاصی پروژه
# from retrieve import SchemaRetrieveReranker
# from llm import CustomOpenAIChatModel
# from config.settings import settings

# # ==========================================
# # ۱. تعریف اطلاعات ساختاری و متادیتای دیتابیس هدف
# # ==========================================
# DB_META_CONTEXT = {
#     "dialect": "mssql",
#     "driver": "pyodbc",
#     "version": "Microsoft SQL Server 2022 (RTM-CU16)",
#     "target_table": "GoodsExchange"
# }

# # راه اندازی موتور اتصال دیتابیس از روی db_url موجود در تنظیمات
# engine = create_engine(settings.db_url)

# # ==========================================
# # ۲. تعریف ساختار وضعیت عامل (Agent State)
# # ==========================================
# class AgentState(TypedDict):
#     question: str                  # سوال کاربر به زبان طبیعی
#     table_name: str                # نام جدول هدف جهت راهنمایی فرآیند
#     refined_schema: str            # اسکیما فیلتر شده توسط Reranker
#     sql_query: str                 # کوئری SQL نهایی یا اصلاح شده
#     sql_error: str                 # خطای صادر شده از انجین دیتابیس
#     execution_result: Dict[str, Any] # نتایج خام خروجی دیتابیس
#     retry_count: int               # تعداد تلاش‌های چرخه اصلاح خودکار
#     analysis_answer: str           # پاسخ تحلیلی نهایی فارسی + وضعیت نمودار


# # ==========================================
# # ۳. پیاده‌سازی گره‌های گراف (Workflow Nodes)
# # ==========================================

# # نمونه‌سازی از کلاس فیلترینگ و بازیابی برداری مرحله قبل
# reranker_service = SchemaRetrieveReranker()

# # مقداردهی مدل زبانی با تنظیم خلاقیت صفر برای کارهای دقیق ساختاری
# llm = CustomOpenAIChatModel(
#     base_url=settings.llm_base_url,
#     api_key=settings.llm_api_key,
#     model_name=settings.llm_model_name,
#     temperature=0.0
# )

# json_parser = JsonOutputParser()


# def retrieve_schema_node(state: AgentState) -> Dict[str, Any]:
#     """
#     گره ۱: بازیابی اطلاعات اسکیما با تلفیق متد Dense+Sparse و فیلترینگ کاندیداها توسط LLM
#     """
#     print("\n🚀 [Node: Retrieval] Extracting semantic schema layouts...")
#     query = state["question"]
    
#     # استفاده از متد جدید برای هندل کردن سوالات پیچیده و چندبخشی
#     final_cols, refined_context = reranker_service.process_complex_query(query, top_k=15)
    
#     print(f"🎯 [Retrieval Success] Selected Columns: {final_cols}")
    
#     return {
#         "refined_schema": refined_context,
#         "retry_count": 0,
#         "sql_error": ""
#     }


# def generate_sql_node(state: AgentState) -> Dict[str, Any]:
#     """
#     گره ۲: تولید دستورات T-SQL منطبق بر خصوصیات و قواعد مایکروسافت SQL Server 2022
#     """
#     print("✍️ [Node: Generation] Compiling safe MS SQL (T-SQL) statement...")
    
#     # حذف f-string از ساختار JSON برای جلوگیری از تداخل با متغیرهای لانگ‌چین
#     system_prompt = (
#         "You are an expert Senior MS SQL Server Developer.\n"
#         "Your target database environment details are:\n"
#         f"- Dialect: {DB_META_CONTEXT['dialect']}\n"
#         f"- Driver/Engine: {DB_META_CONTEXT['driver']} / {DB_META_CONTEXT['version']}\n\n"
#         "CRITICAL COMPLIANCE RULES:\n"
#         "1. You MUST use strict T-SQL syntax. For example, use 'SELECT TOP n' instead of 'LIMIT n'.\n"
#         "2. Do not use functions like NOW(), use GETDATE() if date filtering is needed.\n"
#         "3. Generate a valid query utilizing ONLY the columns listed in the schema context below.\n"
#         "4. Return strictly a raw JSON object containing the query string. Do not wrap code in markdown or backticks:\n"
#         "{{\n  \"query\": \"SELECT TOP 10 column FROM GoodsExchange WHERE condition\"\n}}"
#     )
    
#     # استفاده امن از متغیرهای لانگ‌چین
#     user_prompt = "User Question: {question}\n\nValid Core Schema Context:\n{refined_schema}"
    
#     invoke_payload = {
#         "question": state["question"],
#         "refined_schema": state["refined_schema"]
#     }
    
#     if state.get("sql_error"):
#         print(f"🔄 [Self-Correction Loop] Attempt {state['retry_count']}/3 | Repairing T-SQL framework...")
#         user_prompt += (
#             "\n\n⚠️ CRITICAL FIX NEEDED:\n"
#             "Your previous query failed execution on MS SQL Server.\n"
#             "Failed Attempt Code: {failed_query}\n"
#             "SQL Server Engine Error: {sql_error}\n"
#             "Analyze the T-SQL specifications, resolve syntax dependencies, fix the bug, and output the corrected query."
#         )
#         invoke_payload["failed_query"] = state["sql_query"]
#         invoke_payload["sql_error"] = state["sql_error"]
        
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", system_prompt),
#         ("user", user_prompt)
#     ])
    
#     chain = prompt | llm | json_parser
#     response = chain.invoke(invoke_payload)
    
#     return {"sql_query": response.get("query", "")}


# def execute_sql_node(state: AgentState) -> Dict[str, Any]:
#     """
#     گره ۳: اجرای کوئری روی پایگاه داده اصلی مایکروسافت به کمک SQLAlchemy.
#     """
#     print(f"🖥️ [Node: Execution] Running SQL on MS SQL Server: {state['sql_query']}")
#     query = state["sql_query"]
    
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(text(query))
#             headers = list(result.keys())
#             records = [list(row) for row in result.fetchall()]
        
#         data_payload = {"headers": headers, "rows": records}
#         return {"execution_result": data_payload, "sql_error": ""}
        
#     except Exception as e:
#         error_log = str(e)
#         print(f"❌ [Database Exception Raised]: {error_log}")
#         return {
#             "sql_error": error_log,
#             "retry_count": state["retry_count"] + 1,
#             "execution_result": {}
#         }


# def analyze_and_visualize_node(state: AgentState) -> Dict[str, Any]:
#     """
#     گره ۴: تحلیل نهایی نتایج به زبان فارسی، تولید اسکریپت رسم نمودار به صورت پویا و اجرای امن آن.
#     """
#     print("📊 [Node: Analysis] Synthesizing records and rendering visualization...")
    
#     data_payload = state["execution_result"]
    
#     if (state.get("sql_error") and state["retry_count"] >= 3) or not data_payload.get("rows"):
#         fail_msg = f"متأسفانه پس از تلاش‌های متوالی سیستم، خطایی در واکشی داده‌ها رخ داد: {state.get('sql_error', 'داده‌ای یافت نشد.')}"
#         return {"analysis_answer": fail_msg}

#     system_prompt = (
#         "You are an expert Data Analyst.\n"
#         "Review the database execution payload and provide a comprehensive, insightful report strictly in Persian (Farsi).\n"
#         "Additionally, provide a clean Python script using matplotlib to visualize this specific data matrix.\n"
#         "Save the plot using `plt.savefig('output_plot.png', bbox_inches='tight')`.\n"
#         "Make sure to clean the labels so they display correctly.\n\n"
#         "Your response must match this JSON template exactly. Do not include markdown wraps or backticks:\n"
#         "{{\n"
#         "  \"persian_analysis\": \"متن تحلیلی عمیق شما به زبان فارسی...\",\n"
#         "  \"python_plotting_code\": \"import matplotlib.pyplot as plt\\n# code to draw data...\\nplt.savefig('output_plot.png')\"\n"
#         "}}"
#     )
    
#     user_prompt = "Question: {question}\nData Matrix: {data_matrix}"
    
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", system_prompt),
#         ("user", user_prompt)
#     ])
    
#     chain = prompt | llm | json_parser
    
#     analysis_res = chain.invoke({
#         "question": state["question"],
#         "data_matrix": json.dumps(data_payload, ensure_ascii=False)
#     })
    
#     persian_report = analysis_res.get("persian_analysis", "تحلیل انجام شد.")
#     plotting_script = analysis_res.get("python_plotting_code", "")
    
#     if plotting_script:
#         try:
#             print("🎨 Executing dynamic python visualization script...")
#             exec_globals = {"data": data_payload, "plt": plt}
#             exec(plotting_script, exec_globals)
#             plt.close('all')  # کلوز کردن بافر جهت آزادسازی رم
            
#             if os.path.exists("output_plot.png"):
#                 persian_report += "\n\n📈 **نمودار آماری ضمیمه شده و با موفقیت در فایل `output_plot.png` ذخیره شد.**"
#         except Exception as plot_err:
#             print(f"⚠️ Visualization rendering skipped: {plot_err}")
            
#     return {"analysis_answer": persian_report}


# # ==========================================
# # ۴. تعریف منطق مسیریابی شرطی (Router)
# # ==========================================
# def should_retry_router(state: AgentState):
#     if state["sql_error"]:
#         if state["retry_count"] < 3:
#             print(f"🔄 Route Check: Directing control flows to Self-Correction Loop [Attempt {state['retry_count']}/3]")
#             return "generate_sql"
#         else:
#             print("🛑 Route Check: Exceeded max loop limits. Directing straight to Analysis Phase.")
#             return "analyze_and_respond"
#     return "analyze_and_respond"


# # ==========================================
# # ۵. پیکربندی و ساخت جریان گراف (Graph Assembly)
# # ==========================================
# workflow = StateGraph(AgentState)

# workflow.add_node("retrieve_schema", retrieve_schema_node)
# workflow.add_node("generate_sql", generate_sql_node)
# workflow.add_node("execute_sql", execute_sql_node)
# workflow.add_node("analyze_and_respond", analyze_and_visualize_node)

# workflow.set_entry_point("retrieve_schema")
# workflow.add_edge("retrieve_schema", "generate_sql")
# workflow.add_edge("generate_sql", "execute_sql")

# workflow.add_conditional_edges(
#     "execute_sql",
#     should_retry_router,
#     {
#         "generate_sql": "generate_sql",
#         "analyze_and_respond": "analyze_and_respond"
#     }
# )

# workflow.add_edge("analyze_and_respond", END)
# text_to_sql_agent = workflow.compile()


# # ==========================================
# # ۶. اجرای پایپلاین هوشمند
# # ==========================================
# if __name__ == "__main__":
#     input_payload = {
#         "question": " کدام تولیدکننده بیشترین تنوع کالا را دارد؟",
#         "table_name": "GoodsExchange"
#     }
    
#     print("Initializing Multi-Agent Text-to-SQL Self-Correction System...")
#     for event in text_to_sql_agent.stream(input_payload):
#         for node_name, state_output in event.items():
#             if "analysis_answer" in state_output:
#                 print("\n=================== گزارش تحلیلی نهایی (گزارش بورس کالا) ===================")
#                 print(state_output["analysis_answer"])
#                 print("==========================================================================")



"""
Text-to-SQL Multi-Agent System — نسخه جراحی‌وار اصلاح‌شده
============================================================
پایه: نسخه کاری اصلی (سند ۲) — که واقعاً کار می‌کند
تغییرات: فقط ۶ patch جراحی دقیق، بدون بازنویسی ساختار

  [FIX-1]  JsonOutputParser  ->  StrOutputParser + safe_parse_json()
  [FIX-2]  Decimal/datetime serialization  ->  SQLServerEncoder + safe_dumps()
  [FIX-3]  حجم بی‌حد ردیف‌ها  ->  MAX_ROWS_FOR_LLM = 50
  [FIX-4]  بدون timeout  ->  SQL_EXEC_TIMEOUT + QUERY_GOVERNOR
  [FIX-5]  مقداردهی ناقص state  ->  input_payload کامل
  [FIX-6]  exec() روی کد LLM  ->  safe_generate_chart()

  دست‌نخورده:  get_refined_schema | ChatPromptTemplate | graph structure | router
"""

import os
import re
import json
import logging
from decimal import Decimal
from datetime import datetime, date
from typing import Any, Dict, List

from typing_extensions import TypedDict

# Database
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Visualization — Agg باید قبل از pyplot import شود
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# LangChain / LangGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser   # [FIX-1]
from langgraph.graph import StateGraph, END

# سرویس‌های اختصاصی پروژه — دست‌نخورده
from retrieve import SchemaRetrieveReranker
from llm import CustomOpenAIChatModel
from config.settings import settings


# =====================================================================
# 0.  Logging
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("text_to_sql_agent")


# =====================================================================
# 1.  ثابت‌ها و متادیتا
# =====================================================================
DB_META_CONTEXT = {
    "dialect":      "mssql",
    "driver":       "pyodbc",
    "version":      "Microsoft SQL Server 2022 (RTM-CU16)",
    "target_table": "GoodsExchange",
}

MAX_ROWS_FOR_LLM = 50   # [FIX-3] جلوگیری از خطاهای 400/504
SQL_EXEC_TIMEOUT = 30   # [FIX-4] ثانیه

# [FIX-4] engine با timeout — جایگزین create_engine ساده
engine = create_engine(
    settings.db_url,
    connect_args={
        "timeout": SQL_EXEC_TIMEOUT,
        "TrustServerCertificate": "yes",
    },
    pool_timeout=SQL_EXEC_TIMEOUT,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)


# =====================================================================
# 2.  AgentState — دست‌نخورده
# =====================================================================
class AgentState(TypedDict):
    question:         str
    table_name:       str
    refined_schema:   str
    sql_query:        str
    sql_error:        str
    execution_result: Dict[str, Any]
    retry_count:      int
    analysis_answer:  str


# =====================================================================
# 3.  Helpers جدید — [FIX-1] و [FIX-2]
# =====================================================================

class SQLServerEncoder(json.JSONEncoder):
    """
    [FIX-2] Custom JSON Encoder برای Decimal، datetime، bytes.
    بدون این کلاس، ستون‌های پولی/تاریخی MSSQL باعث TypeError می‌شوند.
    """
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.hex()
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def safe_dumps(obj: Any, **kwargs) -> str:
    """[FIX-2] json.dumps امن — همیشه به‌جای json.dumps مستقیم استفاده کن."""
    return json.dumps(obj, cls=SQLServerEncoder, ensure_ascii=False, **kwargs)


def safe_parse_json(raw_text: str, context: str = "") -> Dict[str, Any]:
    """
    [FIX-1] جایگزین JsonOutputParser.
    اگر LLM قبل یا بعد از JSON متن اضافه نوشت، آن را حذف می‌کند.
    در صورت شکست کامل، دیکشنری خالی برمی‌گرداند — crash نمی‌کند.
    """
    if not raw_text:
        log.error("[JSON | %s] LLM خروجی خالی داد", context)
        return {}

    text_clean = raw_text.strip()

    # حذف markdown code fences
    text_clean = re.sub(r"```json\s*", "", text_clean, flags=re.IGNORECASE)
    text_clean = re.sub(r"```\s*", "", text_clean).strip()

    # تلاش مستقیم
    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        pass

    # پیدا کردن اولین JSON object کامل در متن (با nested brace support)
    match = re.search(r"\{[\s\S]*\}", text_clean)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    log.error("[JSON | %s] هیچ JSON معتبری یافت نشد. خروجی: %.300s", context, raw_text)
    return {}


# =====================================================================
# 4.  نمونه‌سازی سرویس‌ها — دست‌نخورده
# =====================================================================
reranker_service = SchemaRetrieveReranker()

llm = CustomOpenAIChatModel(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model_name=settings.llm_model_name,
    temperature=0.0,
)

# [FIX-1] StrOutputParser به جای JsonOutputParser
str_parser = StrOutputParser()


# =====================================================================
# 5.  گره‌های گراف
# =====================================================================

def retrieve_schema_node(state: AgentState) -> Dict[str, Any]:
    """
    گره 1: بازیابی اسکیما.
    دقیقاً همان نسخه کاری — get_refined_schema دست‌نخورده.
    فقط try/except اضافه شد تا در صورت شکست reranker، fallback اجرا شود.
    """
    print("\n🚀 [Node: Retrieval] Extracting semantic schema layouts...")
    print(" -> Running full Dense + Sparse Hybrid Search pipeline...")

    try:
        refined_context = reranker_service.get_refined_schema(state["question"], top_k=15)

        if not refined_context or not refined_context.strip():
            log.warning("[Retrieve] context خالی است — fallback به schema مستقیم DB")
            refined_context = _get_db_schema_fallback()

    except Exception as e:
        log.error("[Retrieve] get_refined_schema شکست خورد: %s", e)
        refined_context = _get_db_schema_fallback()

    return {
        "refined_schema":   refined_context,
        "retry_count":      0,
        "sql_error":        "",
        "execution_result": {},
        "sql_query":        "",
        "analysis_answer":  "",
    }


def _get_db_schema_fallback() -> str:
    """اگر reranker شکست خورد، schema را مستقیم از DB می‌خواند."""
    try:
        inspector = inspect(engine)
        cols = inspector.get_columns(DB_META_CONTEXT["target_table"])
        lines = [f"Table: {DB_META_CONTEXT['target_table']}"]
        for c in cols:
            lines.append(f"  - {c['name']} ({c['type']})")
        return "\n".join(lines)
    except Exception as e:
        log.error("[Fallback Schema] خطا: %s", e)
        return f"Table: {DB_META_CONTEXT['target_table']} (schema unavailable)"


def generate_sql_node(state: AgentState) -> Dict[str, Any]:
    """
    گره 2: تولید T-SQL.
    ساختار ChatPromptTemplate کاملاً دست‌نخورده از نسخه کاری.
    [FIX-1]: فقط json_parser -> str_parser + safe_parse_json تغییر کرد.
    """
    print("✍️ [Node: Generation] Compiling safe MS SQL (T-SQL) statement...")

    # system_prompt — دست‌نخورده (f-string + {{}} برای escape در ChatPromptTemplate)
    system_prompt = (
        f"You are an expert Senior MS SQL Server Developer.\n"
        f"Your target database environment details are:\n"
        f"- Dialect: {DB_META_CONTEXT['dialect']}\n"
        f"- Driver/Engine: {DB_META_CONTEXT['driver']} / {DB_META_CONTEXT['version']}\n\n"
        f"CRITICAL COMPLIANCE RULES:\n"
        f"1. You MUST use strict T-SQL syntax. For example, use 'SELECT TOP n' instead of 'LIMIT n'.\n"
        f"2. Do not use functions like NOW(), use GETDATE() if date filtering is needed.\n"
        f"3. Generate a valid query utilizing ONLY the columns listed in the schema context below.\n"
        f"4. [CRITICAL] For ANY Persian/Farsi text search or name filtering, ALWAYS use LIKE with wildcards: WHERE ColumnName LIKE N'%value%'\n"
        f"   NEVER use exact match (=) for Persian string columns. Persian data has variations, prefixes, suffixes.\n"
        f"5. Return strictly a raw JSON object containing the query string. "
        f"Do not wrap code in markdown or backticks:\n"
        "{{\n  \"query\": \"SELECT TOP 10 column FROM GoodsExchange WHERE condition\"\n}}"
    )

    # user_prompt — دست‌نخورده از نسخه کاری
    user_prompt = "User Question: {question}\n\nValid Core Schema Context:\n{refined_schema}"

    invoke_payload = {
        "question":       state["question"],
        "refined_schema": state["refined_schema"],
    }

    if state.get("sql_error"):
        print(f"🔄 [Self-Correction Loop] Attempt {state['retry_count']}/3 | Repairing T-SQL framework...")
        user_prompt += (
            f"\n\n⚠️ CRITICAL FIX NEEDED:\n"
            f"Your previous query failed execution on MS SQL Server.\n"
            f"Failed Attempt Code: {{failed_query}}\n"
            f"SQL Server Engine Error: {{sql_error}}\n"
            f"Analyze the T-SQL specifications, resolve syntax dependencies, "
            f"fix the bug, and output the corrected query."
        )
        invoke_payload["failed_query"] = state["sql_query"]
        invoke_payload["sql_error"]    = state["sql_error"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user",   user_prompt),
    ])

    # [FIX-1] str_parser به جای json_parser — chain ساختار اصلی را حفظ می‌کند
    chain = prompt | llm | str_parser
    raw_response = chain.invoke(invoke_payload)

    # [FIX-1] پارس امن — دیگر crash نمی‌کند
    response  = safe_parse_json(raw_response, context="GenerateSQL")
    sql_query = response.get("query", "").strip()

    if not sql_query:
        log.error("[Generate] LLM هیچ query‌ای برنگرداند. خروجی: %.300s", raw_response)
        sql_query = f"SELECT TOP 10 * FROM {DB_META_CONTEXT['target_table']}"
        log.warning("[Generate] fallback query: %s", sql_query)

    return {"sql_query": sql_query}


def execute_sql_node(state: AgentState) -> Dict[str, Any]:
    """
    گره 3: اجرای SQL.
    [FIX-2]  SQLServerEncoder برای Decimal/datetime
    [FIX-3]  محدودیت MAX_ROWS_FOR_LLM
    [FIX-4]  QUERY_GOVERNOR timeout
    """
    print(f"🖥️ [Node: Execution] Running SQL on MS SQL Server: {state['sql_query']}")

    try:
        with engine.connect() as conn:
            # [FIX-4] محدود کردن هزینه اجرا در سطح SQL Server
            conn.execute(text("SET QUERY_GOVERNOR_COST_LIMIT 50000"))

            result  = conn.execute(text(state["sql_query"]))
            headers = list(result.keys())
            all_rows = result.fetchall()

        total_rows = len(all_rows)
        truncated  = total_rows > MAX_ROWS_FOR_LLM

        # [FIX-3] برش ردیف‌ها
        sampled = all_rows[:MAX_ROWS_FOR_LLM]

        # [FIX-2] سریال‌سازی امن هر سلول — Decimal/datetime/bytes
        safe_rows: List[List[Any]] = []
        for row in sampled:
            safe_row: List[Any] = []
            for cell in row:
                if isinstance(cell, Decimal):
                    safe_row.append(float(cell))
                elif isinstance(cell, (datetime, date)):
                    safe_row.append(cell.isoformat())
                elif isinstance(cell, bytes):
                    safe_row.append(cell.hex())
                else:
                    safe_row.append(cell)
            safe_rows.append(safe_row)

        data_payload = {
            "headers":    headers,
            "rows":       safe_rows,
            "total_rows": total_rows,
            "truncated":  truncated,
        }

        if truncated:
            log.warning(
                "[Execute] نتیجه برش خورد: %d -> %d ردیف ارسال به LLM",
                total_rows, MAX_ROWS_FOR_LLM,
            )

        return {"execution_result": data_payload, "sql_error": ""}

    except SQLAlchemyError as e:
        err = str(e).split("\n")[0]
        log.error("[Execute] SQLAlchemy error: %s", err)
        return {
            "sql_error":        err,
            "retry_count":      state["retry_count"] + 1,
            "execution_result": {},
        }
    except Exception as e:
        err = str(e)
        log.error("[Execute] خطای غیرمنتظره: %s", err)
        return {
            "sql_error":        err,
            "retry_count":      state["retry_count"] + 1,
            "execution_result": {},
        }


def analyze_and_visualize_node(state: AgentState) -> Dict[str, Any]:
    """
    گره 4: تحلیل فارسی + رسم نمودار.
    [FIX-1]  str_parser + safe_parse_json به جای json_parser
    [FIX-2]  safe_dumps به جای json.dumps
    [FIX-6]  safe_generate_chart به جای exec(plotting_script)
    """
    print("📊 [Node: Analysis] Synthesizing records and rendering visualization...")

    data_payload = state.get("execution_result", {})
    rows         = data_payload.get("rows", [])
    headers      = data_payload.get("headers", [])
    total_rows   = data_payload.get("total_rows", 0)
    truncated    = data_payload.get("truncated", False)

    # پیام‌های شکست دوستانه فارسی
    if state.get("sql_error") and state["retry_count"] >= 3:
        msg = (
            f"متاسفانه پس از ۳ تلاش متوالی، سیستم موفق به اجرای کوئری نشد.\n\n"
            f"آخرین کوئری:\n```sql\n{state.get('sql_query', 'N/A')}\n```\n\n"
            f"آخرین خطا:\n{state.get('sql_error', 'خطای ناشناخته')}"
        )
        return {"analysis_answer": msg}

    if not rows:
        msg = (
            "کوئری با موفقیت اجرا شد اما هیچ رکوردی یافت نشد.\n\n"
            f"کوئری اجراشده:\n```sql\n{state.get('sql_query', '')}\n```\n\n"
            "پیشنهاد: شرایط WHERE را بررسی کنید یا سوال را با جزئیات بیشتر مطرح کنید."
        )
        return {"analysis_answer": msg}

    # [FIX-2] safe_dumps به جای json.dumps — Decimal/datetime دیگر crash نمی‌کند
    try:
        data_matrix_str = safe_dumps(data_payload, indent=2)
    except Exception as e:
        log.error("[Analyze] حتی safe_dumps شکست خورد: %s", e)
        data_matrix_str = str(data_payload)[:3000]

    truncation_note = ""
    if truncated:
        truncation_note = (
            f"\n\nNote: Full result had {total_rows:,} rows. "
            f"Only first {MAX_ROWS_FOR_LLM} rows are shown. "
            f"Please mention this limitation in your Persian analysis."
        )

    # system_prompt — ساختار دست‌نخورده از نسخه کاری
    # python_plotting_code حذف شد زیرا دیگر exec() نداریم [FIX-6]
    system_prompt = (
        "You are an expert Data Analyst.\n"
        "Review the database execution payload and provide a comprehensive, "
        "insightful report strictly in Persian (Farsi).\n\n"
        "Your response must match this JSON template exactly. "
        "Do not include markdown wraps or backticks:\n"
        "{{\n"
        "  \"persian_analysis\": \"متن تحلیلی عمیق شما به زبان فارسی...\"\n"
        "}}"
    )

    user_prompt = "Question: {question}\nData Matrix: {data_matrix}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user",   user_prompt),
    ])

    # [FIX-1] str_parser + safe_parse_json
    chain = prompt | llm | str_parser
    raw_response = chain.invoke({
        "question":    state["question"],
        "data_matrix": data_matrix_str + truncation_note,
    })

    analysis_res   = safe_parse_json(raw_response, context="Analyze")
    persian_report = analysis_res.get(
        "persian_analysis",
        "تحلیل داده‌ها انجام شد. لطفاً نتایج را در جدول بررسی کنید.",
    )

    # [FIX-6] safe_generate_chart به جای exec(plotting_script)
    chart_path    = "output_plot.png"
    chart_success = safe_generate_chart(
        headers=headers,
        rows=rows,
        question=state["question"],
        output_path=chart_path,
    )

    if chart_success:
        persian_report += (
            f"\n\n📈 **نمودار آماری ضمیمه شده و با موفقیت در فایل `{chart_path}` ذخیره شد.**"
        )

    if truncated:
        persian_report += (
            f"\n\n⚠️ **توجه:** نتایج کامل شامل **{total_rows:,} ردیف** بود. "
            f"تحلیل بر اساس **{MAX_ROWS_FOR_LLM} ردیف اول** انجام شده است."
        )

    return {"analysis_answer": persian_report}


# =====================================================================
# 6.  [FIX-6] رسم نمودار امن — بدون exec()
# =====================================================================

def safe_generate_chart(
    headers: List[str],
    rows: List[List[Any]],
    question: str,
    output_path: str,
) -> bool:
    """
    نمودار را مستقیماً با matplotlib می‌کشد.
    هیچ کد LLM‌ای اجرا نمی‌شود — امن و قابل پیش‌بینی.
    نوع نمودار (پای / افقی / عمودی) بر اساس تعداد ردیف‌ها انتخاب می‌شود.
    """
    if not rows or not headers:
        return False

    try:
        label_col = headers[0] if headers else "Label"
        value_col = headers[1] if len(headers) > 1 else headers[0]

        labels: List[str]   = []
        values: List[float] = []

        for row in rows[:30]:
            if not row:
                continue
            label = str(row[0])[:40] if row[0] is not None else "N/A"
            val = 0.0
            for cell in row[1:]:
                try:
                    val = float(cell)
                    break
                except (TypeError, ValueError):
                    continue
            labels.append(label)
            values.append(val)

        if not values:
            log.warning("[Chart] هیچ مقدار عددی‌ای یافت نشد.")
            return False

        n   = len(labels)
        fig, ax = plt.subplots(figsize=(12, max(5, n * 0.5)))

        if n <= 6:
            # نمودار پای برای مجموعه‌های کوچک
            wedges, texts, autotexts = ax.pie(
                values, labels=labels,
                autopct="%1.1f%%", startangle=140,
                colors=plt.cm.Set3.colors,
            )
            for t in autotexts:
                t.set_fontsize(9)
            ax.set_title(f"{value_col}  |  {label_col}", fontsize=13, pad=15)

        elif n > 15:
            # نمودار افقی برای مجموعه‌های بزرگ — خوانایی بیشتر
            colors = plt.cm.viridis([i / n for i in range(n)])
            bars   = ax.barh(labels, values, color=colors, edgecolor="white", linewidth=0.4)
            ax.set_xlabel(value_col, fontsize=11)
            ax.set_title(f"{value_col}  به‌ازای  {label_col}", fontsize=13, pad=15)
            ax.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
            )
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_width() * 1.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:,.0f}", va="center", ha="left", fontsize=8,
                )

        else:
            # نمودار عمودی برای مجموعه‌های متوسط
            x_pos  = range(n)
            colors = plt.cm.Blues([0.4 + 0.5 * i / max(n, 1) for i in range(n)])
            bars   = ax.bar(x_pos, values, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_xticks(list(x_pos))
            ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
            ax.set_ylabel(value_col, fontsize=11)
            ax.set_title(f"{value_col}  به‌ازای  {label_col}", fontsize=13, pad=15)
            ax.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
            )
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    f"{val:,.0f}", ha="center", va="bottom", fontsize=8,
                )

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.patch.set_facecolor("#FAFAFA")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close("all")
        log.info("[Chart] ذخیره شد: %s", output_path)
        return True

    except Exception as e:
        log.error("[Chart] خطا در رسم: %s", e)
        plt.close("all")
        return False


# =====================================================================
# 7.  Router — دست‌نخورده از نسخه کاری
# =====================================================================

def should_retry_router(state: AgentState) -> str:
    if state["sql_error"]:
        if state["retry_count"] < 3:
            print(f"🔄 Route Check: Directing control flows to Self-Correction Loop [Attempt {state['retry_count']}/3]")
            return "generate_sql"
        else:
            print("🛑 Route Check: Exceeded max loop limits. Directing straight to Analysis Phase.")
            return "analyze_and_respond"
    return "analyze_and_respond"


# =====================================================================
# 8.  Graph Assembly — دست‌نخورده از نسخه کاری
# =====================================================================

workflow = StateGraph(AgentState)

workflow.add_node("retrieve_schema",     retrieve_schema_node)
workflow.add_node("generate_sql",        generate_sql_node)
workflow.add_node("execute_sql",         execute_sql_node)
workflow.add_node("analyze_and_respond", analyze_and_visualize_node)

workflow.set_entry_point("retrieve_schema")
workflow.add_edge("retrieve_schema", "generate_sql")
workflow.add_edge("generate_sql",    "execute_sql")

workflow.add_conditional_edges(
    "execute_sql",
    should_retry_router,
    {
        "generate_sql":        "generate_sql",
        "analyze_and_respond": "analyze_and_respond",
    },
)

workflow.add_edge("analyze_and_respond", END)

text_to_sql_agent = workflow.compile()


# =====================================================================
# 9.  Entry Point — [FIX-5] مقداردهی کامل state
# =====================================================================

if __name__ == "__main__":
    # [FIX-5] تمام فیلدهای AgentState مقداردهی شده‌اند — بدون KeyError
    input_payload: AgentState = {
        "question":         " توزیع نوع قراردادها برای کالای «سیمان پرتلند» چگونه است؟ ",
        "table_name":       "GoodsExchange",
        "refined_schema":   "",
        "sql_query":        "",
        "sql_error":        "",
        "execution_result": {},
        "retry_count":      0,
        "analysis_answer":  "",
    }

    print("Initializing Multi-Agent Text-to-SQL Self-Correction System...")

    for event in text_to_sql_agent.stream(input_payload):
        for node_name, state_output in event.items():
            if "sql_query" in state_output and state_output["sql_query"]:
                print(f"\n[SQL | {node_name}]")
                print(state_output["sql_query"])
            if "sql_error" in state_output and state_output["sql_error"]:
                print(f"\n[Error | {node_name}]")
                print(state_output["sql_error"])
            if "analysis_answer" in state_output and state_output["analysis_answer"]:
                print("\n=================== گزارش تحلیلی نهایی (گزارش بورس کالا) ===================")
                print(state_output["analysis_answer"])
                print("==========================================================================")