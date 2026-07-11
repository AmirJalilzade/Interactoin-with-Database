#region 
# import os
# import json
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from decimal import Decimal
# from statistics import median as py_median, pstdev

# # دیتابیس و مدل‌سازی تصویری
# from sqlalchemy import create_engine, inspect, MetaData, Table, select, func, text
# import matplotlib
# matplotlib.use('Agg')  # جلوگیری از خطاهای کرش محیط‌های تصویری در سرور
# import matplotlib.pyplot as plt

# # سیستم عامل متنی و عامل هوشمند
# from langchain_core.messages import HumanMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import JsonOutputParser
# from langgraph.graph import StateGraph, END
# from typing_extensions import TypedDict
# from typing import Dict, Any

# # ماژول‌های امبدینگ و اتصالات میلوس
# from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
# from pymilvus.model.sparse import BM25EmbeddingFunction

# # ایمپورت‌های ماژول‌های داخلی پروژه شما
# from llm import CustomOpenAIChatModel
# from embedding import EmbeddingService
# from retrieve import SchemaRetrieveReranker
# from config.settings import settings

# # تنظیمات استایل و هویت بصری Premium راست‌چین
# st.set_page_config(page_title="AI Text-to-SQL Operator", page_icon="📊", layout="wide")
# st.markdown("""
#     <style>
#     .reportview-container .main .block-container { direction: rtl; text-align: right; }
#     h1, h2, h3 { text-align: right; font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif; }
#     div.stButton > button:first-child { background-color: #2e6f40; color: white; border-radius: 8px; }
#     </style>
# """, unsafe_allow_html=True)

# # ==========================================
# # مدیریت وضعیت نشست‌ها (Session State)
# # ==========================================
# if "db_engine" not in st.session_state:
#     st.session_state.db_engine = None
# if "tables_list" not in st.session_state:
#     st.session_state.tables_list = []
# if "selected_table" not in st.session_state:
#     st.session_state.selected_table = None
# if "indexing_done" not in st.session_state:
#     st.session_state.indexing_done = False

# # ==========================================
# # ۱. ابزارهای کمکی استخراج داده (generate_descriptions)
# # ==========================================
# def convert_value(v):
#     if isinstance(v, Decimal): return float(v)
#     if isinstance(v, (datetime, date)): return v.isoformat()
#     return v

# def clean_dict(d):
#     return {k: convert_value(v) for k, v in d.items()}

# def is_numeric_type(col_type):
#     from sqlalchemy.sql.sqltypes import Integer, Float, Numeric, DECIMAL, REAL
#     return isinstance(col_type, (Integer, Float, Numeric, DECIMAL, REAL))

# def is_datetime_type(col_type):
#     from sqlalchemy.sql.sqltypes import DateTime, Date
#     return isinstance(col_type, (DateTime, Date))

# def is_string_type(col_type):
#     from sqlalchemy.sql.sqltypes import String, Text, VARCHAR, CHAR, Unicode, UnicodeText
#     return isinstance(col_type, (String, Text, VARCHAR, CHAR, Unicode, UnicodeText))

# def get_numeric_stats(engine, table_name, column_name):
#     metadata = MetaData()
#     table = Table(table_name, metadata, autoload_with=engine)
#     col = table.c[column_name]
#     try:
#         with engine.connect() as conn:
#             stmt = select(
#                 func.count().label("total_count"),
#                 func.count(col).label("non_null_count"),
#                 func.avg(col).label("mean"),
#                 func.min(col).label("min"),
#                 func.max(col).label("max"),
#                 func.sum(col).label("sum"),
#             ).select_from(table)
#             result = conn.execute(stmt).first()
#             stats = clean_dict(dict(result._mapping))
#             total = stats["total_count"]
#             stats["null_percentage"] = (total - stats["non_null_count"]) / total * 100 if total else 0
#             return stats
#     except Exception as e:
#         return {"error": str(e)}

# def extract_dynamic_schema(engine, target_table):
#     inspector = inspect(engine)
#     columns = inspector.get_columns(target_table)
#     pk = inspector.get_pk_constraint(target_table)
#     fks = inspector.get_foreign_keys(target_table)

#     table_overview = {
#         "table_name": target_table,
#         "column_count": len(columns),
#         "primary_key": pk.get("constrained_columns"),
#         "foreign_keys": fks
#     }

#     columns_info = []
#     for col in columns:
#         col_name = col["name"]
#         col_type = col["type"]
#         column_doc = {
#             "table": target_table,
#             "column": col_name,
#             "type": str(col_type),
#             "nullable": col["nullable"],
#             "default": str(col.get("default"))
#         }
#         if is_numeric_type(col_type):
#             column_doc["stats"] = get_numeric_stats(engine, target_table, col_name)
#         else:
#             column_doc["stats"] = {"total_count": 100, "null_percentage": 0} # پیش‌فرض متنی/تاریخی برای تسریع فرآیند استریم‌لیت
#         columns_info.append(column_doc)

#     return table_overview, columns_info

# def generate_column_description(llm, column_info: dict) -> str:
#     prompt = f"Describe the following database column in Persian (1-2 sentences summaries) including its type and purpose.\nColumn: {column_info['column']}, Type: {column_info['type']}, Stats: {json.dumps(column_info.get('stats', {}))}"
#     return llm.invoke([HumanMessage(content=prompt)]).content.strip()

# # ==========================================
# # ۲. ابزارهای کمکی ساخت ایندکس میلوس (embed_and_store)
# # ==========================================
# MILVUS_COLLECTION_NAME = "dynamic_column_info_bgem3"

# def ingest_to_milvus(columns_info: list, embedder):
#     connections.connect(alias="default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
    
#     if utility.has_collection(MILVUS_COLLECTION_NAME):
#         utility.drop_collection(MILVUS_COLLECTION_NAME)
        
#     fields = [
#         FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
#         FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=embedder.dim),
#         FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
#         FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=256),
#         FieldSchema(name="column_name", dtype=DataType.VARCHAR, max_length=256),
#         FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
#         FieldSchema(name="metadata_json", dtype=DataType.JSON),
#     ]
#     schema = CollectionSchema(fields, description="Hybrid Custom Collection")
#     collection = Collection(MILVUS_COLLECTION_NAME, schema)
    
#     collection.create_index("vector", {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}})
#     collection.create_index("sparse_vector", {"metric_type": "IP", "index_type": "SPARSE_INVERTED_INDEX", "params": {"drop_ratio_build": 0.0}})
#     collection.load()

#     chunk_texts = [f"Table: {c['table']}, Column: {c['column']}. {c.get('description', '')}" for c in columns_info]
#     dense_vectors = embedder.embed_documents(chunk_texts)
    
#     bm25_ef = BM25EmbeddingFunction(analyzer=None)
#     bm25_ef.fit(chunk_texts)
#     sparse_vectors = bm25_ef.encode_documents(chunk_texts)

#     entities = [
#         dense_vectors,
#         sparse_vectors,
#         [c["table"] for c in columns_info],
#         [c["column"] for c in columns_info],
#         chunk_texts,
#         columns_info,
#     ]
#     collection.insert(entities)
#     collection.flush()

# # ==========================================
# # ۳. تعریف منطق گراف خوداصلاحی تفسیری (LangGraph)
# # ==========================================
# class AgentState(TypedDict):
#     question: str
#     table_name: str
#     refined_schema: str
#     sql_query: str
#     sql_error: str
#     execution_result: Dict[str, Any]
#     retry_count: int
#     analysis_answer: str

# # مقداردهی به انجین‌های پایه‌ سیستم
# llm_agent = CustomOpenAIChatModel(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model_name=settings.llm_model_name, temperature=0.0)
# json_parser = JsonOutputParser()

# def generate_sql_node(state: AgentState) -> Dict[str, Any]:
#     # 🟢 کد اصلاح‌شده و بدون خطا (دقیقاً این دو خط را جایگزین خطوط قبلی کنید)
#     system_prompt = "You are a Senior MS SQL Server Developer. Use strict T-SQL syntax. Output raw JSON object matching: {{\"query\": \"SELECT TOP 10 ...\"}}."
#     user_prompt = f"Question: {state['question']}\nTable Context:\n{state['refined_schema']}"
#     if state.get("sql_error"):
#         user_prompt += f"\n\n⚠️ FIX ERROR:\nPrevious Code: {state['sql_query']}\nMS SQL Error: {state['sql_error']}"
    
#     prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", user_prompt)])
#     res = (prompt | llm_agent | json_parser).invoke({})
#     return {"sql_query": res.get("query", "")}

# def execute_sql_node(state: AgentState) -> Dict[str, Any]:
#     query = state["sql_query"]
#     try:
#         with st.session_state.db_engine.connect() as connection:
#             result = connection.execute(text(query))
#             headers = list(result.keys())
#             records = [list(row) for row in result.fetchall()]
#         return {"execution_result": {"headers": headers, "rows": records}, "sql_error": ""}
#     except Exception as e:
#         return {"sql_error": str(e), "retry_count": state["retry_count"] + 1, "execution_result": {}}

# def analyze_and_visualize_node(state: AgentState) -> Dict[str, Any]:
#     data_payload = state["execution_result"]
#     if state.get("sql_error") and state["retry_count"] >= 3:
#         return {"analysis_answer": f"خطا در واکشی اطلاعات از سرور مایکروسافت: {state['sql_error']}"}
    
#     system_prompt = """
# You are an expert Data Analyst.

# Provide an insightful report strictly in Persian (Farsi).

# Also provide matplotlib Python code to save the chart into 'output_plot.png'.

# Respond strictly in JSON:

# {{"persian_analysis": "...", "python_plotting_code": "..."}}
# """
#     prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", "Question: {question}\nData: {data_matrix}")])
    
#     res = (prompt | llm_agent | json_parser).invoke({
#         "question": state["question"],
#         "data_matrix": json.dumps(data_payload, ensure_ascii=False)
#     })
    
#     persian_report = res.get("persian_analysis", "")
#     plotting_script = res.get("python_plotting_code", "")
    
#     if plotting_script:
#         try:
#             exec_globals = {"data": data_payload, "plt": plt}
#             exec(plotting_script, exec_globals)
#             plt.close('all')
#         except Exception as e:
#             persian_report += f"\n\n(سیستم قادر به ترسیم خودکار نمودار نبود: {e})"
#     return {"analysis_answer": persian_report}

# def should_retry_router(state: AgentState):
#     if state["sql_error"] and state["retry_count"] < 3: return "generate_sql"
#     return "analyze_and_respond"

# # ساخت نهایی عامل لانگ‌گراف
# workflow = StateGraph(AgentState)
# workflow.add_node("generate_sql", generate_sql_node)
# workflow.add_node("execute_sql", execute_sql_node)
# workflow.add_node("analyze_and_respond", analyze_and_visualize_node)
# workflow.set_entry_point("generate_sql")
# workflow.add_edge("generate_sql", "execute_sql")
# workflow.add_conditional_edges("execute_sql", should_retry_router, {"generate_sql": "generate_sql", "analyze_and_respond": "analyze_and_respond"})
# workflow.add_edge("analyze_and_respond", END)
# compiled_agent = workflow.compile()


# # ==========================================
# # ۴. رابط کاربری (Streamlit UI layout)
# # ==========================================
# st.title("📊 داشبورد هوشمند پایگاه داده (Text-to-SQL Analytics)")
# st.caption("سیستم واکشی اطلاعات ساختاریافته بورس کالا مبتنی بر زنجیره خوداصلاحی زنده روی MS SQL Server")
# st.divider() #  اصلاح شد

# # ایجاد سایدبار برای مدیریت تنظیمات اتصال پایگاه داده
# with st.sidebar:
#     st.header("🔑 تنظیمات اتصال دیتابیس")
#     db_type = st.selectbox("انتخاب پایگاه داده هدف:", ["Microsoft SQL Server (T-SQL)", "SQLite"])
    
#     # مقدار اولیه متناظر با کانفیگ شما
#     default_url = "mssql+pyodbc://Sa:Passworddjkn%40Sec\\2\\:1433/AI_db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=no&Encrypt=no&ConnectionTimeout=60&LoginTimeout=60"
#     conn_string = st.text_area("رشته اتصال دیتابیس (SQLAlchemy URL):", value=default_url, height=150)
    
#     if st.button("🔌 برقراری اتصال زنده"):
#         try:
#             with st.spinner("در حال تست کانکشن..."):
#                 engine = create_engine(conn_string)
#                 inspector = inspect(engine)
#                 # دریافت تمام جداول و ویوهای دیتابیس بدون محدودیت
#                 all_tables = inspector.get_table_names() + inspector.get_view_names()
#                 st.session_state.db_engine = engine
#                 st.session_state.tables_list = all_tables
#                 st.success(f"اتصال موفق! {len(all_tables)} جدول/ویو بارگذاری شد.")
#         except Exception as e:
#             st.error(f"خطا در برقراری ارتباط: {e}")

# # بررسی فاز دوم: انتخاب جدول و عملیات استخراج اسکیما و ایندکس
# if st.session_state.db_engine and st.session_state.tables_list:
#     st.header("📁 گام دوم: انتخاب جدول و آماده‌سازی پایگاه برداری (Milvus Vectorization)")
    
#     col1, col2 = st.columns([2, 1])
#     with col1:
#         selected_table = st.selectbox("یک جدول یا ویو جهت تحلیل انتخاب کنید:", st.session_state.tables_list)
#     with col2:
#         st.write("") # هماهنگی عمودی دکمه
#         st.write("")
#         trigger_indexing = st.button("🏗️ استخراج متادیتای آماری و ساخت بردارها")
        
#     if trigger_indexing:
#         with st.spinner("در حال واکشی اطلاعات فیلدها، تحلیل توزیع مقادیر و ترجمه اسکیما به زبان فارسی..."):
#             # ۱. استخراج اطلاعات آماری دقیق
#             table_overview, columns_info = extract_dynamic_schema(st.session_state.db_engine, selected_table)
            
#             # ۲. غنی‌سازی با مدل زبانی
#             llm_desc = CustomOpenAIChatModel(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model_name=settings.llm_model_name, temperature=0.1)
#             for col in columns_info:
#                 col["description"] = generate_column_description(llm_desc, col)
            
#             # ۳. ذخیره‌سازی وکتورها در میلوس به صورت هیبرید Dense+Sparse
#             embedder_service = EmbeddingService(base_url=settings.embedding_base_url, model=settings.embedding_model)
#             ingest_to_milvus(columns_info, embedder_service)
            
#             st.session_state.selected_table = selected_table
#             st.session_state.indexing_done = True
#             st.success(f"عملیات ایندکس ترکیبی جدول '{selected_table}' با موفقیت در Milvus انجام پذیرفت!")

# # فاز سوم: بخش چت و پرسش و پاسخ نهایی کاربران روی دیتای انتخابی
# if st.session_state.indexing_done:
#     st.divider()
#     st.header(f"💬 گام سوم: فضای گفتگوی هوشمند روی جدول [{st.session_state.selected_table}]")
    
#     user_query = st.text_input("سوال یا شاخص تحلیلی مدنظر خود را به زبان فارسی وارد کنید:", 
#                                placeholder="مثال: میانگین مقدار معامله برای قیر ۶۰۷۰ چقدر است؟ مقدار کل آن را حساب کن.")
    
#     if st.button("🚀 تحلیل و اجرای زنده دستور"):
#         if not user_query:
#             st.warning("لطفاً ابتدا سوال خود را بنویسید.")
#         else:
#             with st.spinner("سیستم عامل هوشمند متنی در حال استخراج محتوا و بهینه‌سازی کدهای T-SQL است..."):
#                 # استفاده از Reranker اختصاصی شما برای خواندن بهترین ستون‌های مرتبط از میلوس
#                 reranker_service = SchemaRetrieveReranker()
#                 refined_schema = reranker_service.get_refined_schema(user_query, top_k=15)
                
#                 # فرستادن اطلاعات فیلترشده به زنجیره خوداصلاحی گراف
#                 initial_state = {
#                     "question": user_query,
#                     "table_name": st.session_state.selected_table,
#                     "refined_schema": refined_schema,
#                     "sql_query": "",
#                     "sql_error": "",
#                     "execution_result": {},
#                     "retry_count": 0,
#                     "analysis_answer": ""
#                 }
                
#                 # اجرای به هم پیوسته گره‌های سیستم هوشمند
#                 final_output = compiled_agent.invoke(initial_state)
                
#                 # نمایش خروجی‌های ساختاریافته به کاربر به تفکیک تب‌ها برای جلوه زیباتر مانیتورینگ
#                 tab1, tab2, tab3 = st.tabs(["📊 تحلیل و نمودار آماری", "💻 کد T-SQL تولید شده", "📋 دیتای خام واکشی شده"])
                
#                 with tab1:
#                     st.subheader("📌 گزارش تحلیلی بورس کالا")
#                     st.write(final_output["analysis_answer"])
                    
#                     if os.path.exists("output_plot.png"):
#                         st.image("output_plot.png", caption="نمودار تحلیل توزیع و مقادیر واکشی شده", use_container_width=True)
#                         # حذف فایل بعد از رندر جهت عدم تداخل با تصاویر درخواست بعدی
#                         try: os.remove("output_plot.png")
#                         except: pass
                        
#                 with tab2:
#                     st.subheader("🛠️ دستور نهایی ارسال شده به سرور مایکروسافت")
#                     st.code(final_output["sql_query"], language="sql")
#                     if final_output.get("retry_count", 0) > 0:
#                         st.info(f"💡 سیستم لایه تصحیح، این کوئری را پس از {final_output['retry_count']} بار بازنگری و خطایابی خودکار اصلاح کرده است.")
                        
#                 with tab3:
#                     st.subheader("📦 جدول رکوردهای پایگاه داده")
#                     raw_data = final_output.get("execution_result", {})
#                     if raw_data and "rows" in raw_data and raw_data["rows"]:
#                         df_result = pd.DataFrame(raw_data["rows"], columns=raw_data["headers"])
#                         st.dataframe(df_result, use_container_width=True)
#                     else:
#                         st.info("داده خامی برای نمایش یافت نشد یا دستور فاقد رکورد بازگشتی بود.")
#endregion


import os
import io
import json
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import quote_plus

# دیتابیس
from sqlalchemy import create_engine, inspect, MetaData, Table, select, func, text

# Plotly for interactive plots (no images!)
import plotly.graph_objects as go
import plotly.express as px

# کتابخانه‌های اصلاح متن فارسی
import arabic_reshaper
from bidi.algorithm import get_display

# سیستم عامل متنی و عامل هوشمند
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from typing import Dict, Any

# ماژول‌های امبدینگ و اتصالات میلوس
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from pymilvus.model.sparse import BM25EmbeddingFunction

from llm import CustomOpenAIChatModel
from embedding import EmbeddingService
from retrieve import SchemaRetrieveReranker
from config.settings import settings

# ==========================================
# تنظیمات استایل و هویت بصری Premium راست‌چین
# ==========================================
st.set_page_config(page_title="AI Text-to-SQL Operator", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp, .stApp [data-testid="stHeader"], .stApp [data-testid="stSidebar"], 
    .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stVerticalBlock"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif !important;
    }
    
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        direction: rtl !important;
        text-align: right !important;
    }
    
    div.stButton > button:first-child {
        background-color: #2e6f40;
        color: white;
        border-radius: 8px;
        width: 100%;
    }
    
    footer, #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# مدیریت وضعیت نشست‌ها
# ==========================================
if "db_engine" not in st.session_state:
    st.session_state.db_engine = None
if "tables_list" not in st.session_state:
    st.session_state.tables_list = []
if "selected_table" not in st.session_state:
    st.session_state.selected_table = None
if "indexing_done" not in st.session_state:
    st.session_state.indexing_done = False

# ==========================================
# توابع کمکی
# ==========================================
def convert_value(v):
    if isinstance(v, Decimal): return float(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    return v

def clean_dict(d):
    return {k: convert_value(v) for k, v in d.items()}

def is_numeric_type(col_type):
    from sqlalchemy.sql.sqltypes import Integer, Float, Numeric, DECIMAL, REAL
    return isinstance(col_type, (Integer, Float, Numeric, DECIMAL, REAL))

def get_numeric_stats(engine, table_name, column_name):
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    col = table.c[column_name]
    try:
        with engine.connect() as conn:
            stmt = select(
                func.count().label("total_count"),
                func.count(col).label("non_null_count"),
                func.avg(col).label("mean"),
                func.min(col).label("min"),
                func.max(col).label("max"),
                func.sum(col).label("sum"),
            ).select_from(table)
            result = conn.execute(stmt).first()
            stats = clean_dict(dict(result._mapping))
            total = stats["total_count"]
            stats["null_percentage"] = (total - stats["non_null_count"]) / total * 100 if total else 0
            return stats
    except Exception as e:
        return {"error": str(e)}

def extract_dynamic_schema(engine, target_table):
    inspector = inspect(engine)
    columns = inspector.get_columns(target_table)
    pk = inspector.get_pk_constraint(target_table)
    fks = inspector.get_foreign_keys(target_table)

    table_overview = {
        "table_name": target_table,
        "column_count": len(columns),
        "primary_key": pk.get("constrained_columns"),
        "foreign_keys": fks
    }

    columns_info = []
    for col in columns:
        col_name = col["name"]
        col_type = col["type"]
        column_doc = {
            "table": target_table,
            "column": col_name,
            "type": str(col_type),
            "nullable": col["nullable"],
            "default": str(col.get("default"))
        }
        if is_numeric_type(col_type):
            column_doc["stats"] = get_numeric_stats(engine, target_table, col_name)
        else:
            column_doc["stats"] = {"total_count": 100, "null_percentage": 0}
        columns_info.append(column_doc)

    return table_overview, columns_info

def generate_column_description(llm, column_info: dict) -> str:
    prompt = f"Describe the following database column in Persian (1-2 sentences summaries) including its type and purpose.\nColumn: {column_info['column']}, Type: {column_info['type']}, Stats: {json.dumps(column_info.get('stats', {}))}"
    return llm.invoke([HumanMessage(content=prompt)]).content.strip()

# ==========================================
# ابزارهای میلوس
# ==========================================
MILVUS_COLLECTION_NAME = "dynamic_column_info_bgem3"

def ingest_to_milvus(columns_info: list, embedder):
    connections.connect(alias="default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
    
    if utility.has_collection(MILVUS_COLLECTION_NAME):
        utility.drop_collection(MILVUS_COLLECTION_NAME)
        
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=embedder.dim),
        FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="column_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="metadata_json", dtype=DataType.JSON),
    ]
    schema = CollectionSchema(fields, description="Hybrid Custom Collection")
    collection = Collection(MILVUS_COLLECTION_NAME, schema)
    
    collection.create_index("vector", {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}})
    collection.create_index("sparse_vector", {"metric_type": "IP", "index_type": "SPARSE_INVERTED_INDEX", "params": {"drop_ratio_build": 0.0}})
    collection.load()

    chunk_texts = [f"Table: {c['table']}, Column: {c['column']}. {c.get('description', '')}" for c in columns_info]
    dense_vectors = embedder.embed_documents(chunk_texts)
    
    bm25_ef = BM25EmbeddingFunction(analyzer=None)
    bm25_ef.fit(chunk_texts)
    sparse_vectors = bm25_ef.encode_documents(chunk_texts)

    entities = [
        dense_vectors,
        sparse_vectors,
        [c["table"] for c in columns_info],
        [c["column"] for c in columns_info],
        chunk_texts,
        columns_info,
    ]
    collection.insert(entities)
    collection.flush()

# ==========================================
# تابع اصلاح متن فارسی
# ==========================================
def fa(text):
    """اصلاح حروف فارسی برای نمایش صحیح"""
    if isinstance(text, str):
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text
    return text

# ==========================================
# LangGraph Agent
# ==========================================
class AgentState(TypedDict):
    question: str
    table_name: str
    refined_schema: str
    sql_query: str
    sql_error: str
    execution_result: Dict[str, Any]
    retry_count: int
    analysis_answer: str
    plot_config: Dict[str, Any]

llm_agent = CustomOpenAIChatModel(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model_name=settings.llm_model_name, temperature=0.0)
json_parser = JsonOutputParser()

def generate_sql_node(state: AgentState) -> Dict[str, Any]:
    system_prompt = "You are a Senior MS SQL Server Developer. Use strict T-SQL syntax. Output raw JSON object matching: {{\"query\": \"SELECT TOP 10 ...\"}}."
    user_prompt = f"Question: {state['question']}\nTable Context:\n{state['refined_schema']}"
    if state.get("sql_error"):
        user_prompt += f"\n\n⚠️ FIX ERROR:\nPrevious Code: {state['sql_query']}\nMS SQL Error: {state['sql_error']}"
    
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", user_prompt)])
    res = (prompt | llm_agent | json_parser).invoke({})
    return {"sql_query": res.get("query", "")}

def execute_sql_node(state: AgentState) -> Dict[str, Any]:
    query = state["sql_query"]
    try:
        with st.session_state.db_engine.connect() as connection:
            result = connection.execute(text(query))
            headers = list(result.keys())
            records = [list(row) for row in result.fetchall()]
        return {"execution_result": {"headers": headers, "rows": records}, "sql_error": ""}
    except Exception as e:
        return {"sql_error": str(e), "retry_count": state["retry_count"] + 1, "execution_result": {}}

def analyze_and_visualize_node(state: AgentState) -> Dict[str, Any]:
    data_payload = state["execution_result"]
    if state.get("sql_error") and state["retry_count"] >= 3:
        return {"analysis_answer": f"خطا در واکشی اطلاعات: {state['sql_error']}", "plot_config": None}
    
    system_prompt = """
You are an expert Data Analyst. Provide insights in Persian.

Analyze the data and specify how to visualize it. Return JSON with:
1. "persian_analysis": Your analysis in Persian
2. "chart_type": One of: bar, line, scatter, pie, box, histogram, area
3. "x_column": Column name for x-axis (or null)
4. "y_column": Column name for y-axis (or null for pie)
5. "title": Chart title in Persian
6. "x_title": X-axis label in Persian (or null)
7. "y_title": Y-axis label in Persian (or null)
8. "color_column": Column for coloring (or null)
9. "sort_by": Column to sort by (or null)
10. "sort_ascending": true/false
11. "top_n": Show only top N rows (or null for all)

Example:
{{
  "persian_analysis": "تحلیل شما...",
  "chart_type": "bar",
  "x_column": "product_name",
  "y_column": "sales_amount",
  "title": "فروش محصولات",
  "x_title": "محصول",
  "y_title": "مبلغ فروش",
  "color_column": null,
  "sort_by": "sales_amount",
  "sort_ascending": false,
  "top_n": 10
}}
"""
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", "Question: {question}\nData: {data_matrix}")])
    
    res = (prompt | llm_agent | json_parser).invoke({
        "question": state["question"],
        "data_matrix": json.dumps(data_payload, ensure_ascii=False)
    })
    
    persian_report = res.get("persian_analysis", "")
    plot_config = {
        "chart_type": res.get("chart_type", "bar"),
        "x_column": res.get("x_column"),
        "y_column": res.get("y_column"),
        "title": res.get("title"),
        "x_title": res.get("x_title"),
        "y_title": res.get("y_title"),
        "color_column": res.get("color_column"),
        "sort_by": res.get("sort_by"),
        "sort_ascending": res.get("sort_ascending", True),
        "top_n": res.get("top_n")
    }
            
    return {"analysis_answer": persian_report, "plot_config": plot_config}

def should_retry_router(state: AgentState):
    if state["sql_error"] and state["retry_count"] < 3: 
        return "generate_sql"
    return "analyze_and_respond"

workflow = StateGraph(AgentState)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("execute_sql", execute_sql_node)
workflow.add_node("analyze_and_respond", analyze_and_visualize_node)
workflow.set_entry_point("generate_sql")
workflow.add_edge("generate_sql", "execute_sql")
workflow.add_conditional_edges("execute_sql", should_retry_router, {"generate_sql": "generate_sql", "analyze_and_respond": "analyze_and_respond"})
workflow.add_edge("analyze_and_respond", END)
compiled_agent = workflow.compile()

# ==========================================
# تابع ساخت نمودار Plotly
# ==========================================
def create_plotly_chart(df: pd.DataFrame, config: Dict[str, Any]) -> go.Figure:
    """ساخت نمودار تعاملی Plotly با مدیریت خطای نام ستون‌ها"""
    
    if df.empty:
        return None
        
    chart_df = df.copy()
    
    x_col = config.get("x_column")
    y_col = config.get("y_column")
    sort_by = config.get("sort_by")
    color_col = config.get("color_column")
    
    def find_actual_col(suggested_name):
        if not suggested_name: return None
        if suggested_name in chart_df.columns: return suggested_name
        col_map = {c.lower(): c for c in chart_df.columns}
        if suggested_name.lower() in col_map: return col_map[suggested_name.lower()]
        for col in chart_df.columns:
            if suggested_name.lower() in col.lower(): return col
        return None

    x_col = find_actual_col(x_col)
    y_col = find_actual_col(y_col)
    sort_by = find_actual_col(sort_by)
    color_col = find_actual_col(color_col)
    
    if not x_col:
        x_col = chart_df.columns[0]
        
    if sort_by:
        try:
            chart_df = chart_df.sort_values(by=sort_by, ascending=config.get("sort_ascending", True))
        except Exception:
            pass
    
    if config.get("top_n"):
        chart_df = chart_df.head(config["top_n"])
    
    title = fa(config.get("title", "")) if config.get("title") else ""
    x_title = fa(config.get("x_title", "")) if config.get("x_title") else ""
    y_title = fa(config.get("y_title", "")) if config.get("y_title") else ""
    
    chart_type = config.get("chart_type", "bar")
    labels = {x_col: x_title}
    if y_col: labels[y_col] = y_title
        
    try:
        if chart_type == "bar": fig = px.bar(chart_df, x=x_col, y=y_col, color=color_col, title=title, labels=labels)
        elif chart_type == "line": fig = px.line(chart_df, x=x_col, y=y_col, color=color_col, title=title, labels=labels)
        elif chart_type == "scatter": fig = px.scatter(chart_df, x=x_col, y=y_col, color=color_col, title=title, labels=labels)
        elif chart_type == "pie": fig = px.pie(chart_df, names=x_col, values=y_col, title=title)
        elif chart_type == "area": fig = px.area(chart_df, x=x_col, y=y_col, color=color_col, title=title, labels=labels)
        else: fig = px.bar(chart_df, x=x_col, y=y_col, title=title, labels=labels)
    except Exception:
        fig = px.bar(chart_df, x=x_col, y=y_col, title=title, labels=labels)
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Vazirmatn, Tahoma, sans-serif", size=12),
        title_font=dict(size=16, family="Vazirmatn, Tahoma, sans-serif"),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode='x unified',
        showlegend=True if color_col else False,
    )
    
    fig.update_xaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)', zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)', zeroline=False)
    
    return fig

# ==========================================
# رابط کاربری Streamlit
# ==========================================
st.title("📊 داشبورد هوشمند پایگاه داده")
st.caption("سیستم واکشی اطلاعات ساختاریافته بورس کالا")
st.divider()

with st.sidebar:
    st.header("🔑 تنظیمات اتصال دیتابیس")
    db_type = st.selectbox("انتخاب نوع پایگاه داده:", ["Microsoft SQL Server", "PostgreSQL", "MySQL", "SQLite"])
    
    if db_type != "SQLite":
        st.subheader("اطلاعات سرور")
        col1, col2 = st.columns(2)
        with col1:
            server = st.text_input("سرور (Server/Host):", value="localhost")
        with col2:
            default_port = "1433" if db_type == "Microsoft SQL Server" else ("5432" if db_type == "PostgreSQL" else "3306")
            port = st.text_input("پورت (Port):", value=default_port)
        
        st.subheader("اطلاعات احراز هویت")
        database = st.text_input("نام دیتابیس (Database):", value="AI_db")
        username = st.text_input("نام کاربری (Username):", value="sa")
        password = st.text_input("رمز عبور (Password):", type="password", value="")
        
        if db_type == "Microsoft SQL Server":
            st.subheader("تنظیمات پیشرفته SQL Server")
            trust_server_cert = st.checkbox("TrustServerCertificate", value=True)
            encrypt = st.checkbox("Encrypt", value=False)
    else:
        st.subheader("فایل دیتابیس")
        db_file = st.text_input("مسیر فایل SQLite:", value="data.db")
        
    if st.button("🔌 برقراری اتصال"):
        try:
            with st.spinner("در حال تست کانکشن..."):
                conn_url = ""
                if db_type == "Microsoft SQL Server":
                    driver = "ODBC+Driver+18+for+SQL+Server"
                    params = f"driver={driver}&TrustServerCertificate={'yes' if trust_server_cert else 'no'}&Encrypt={'yes' if encrypt else 'no'}&ConnectionTimeout=60&LoginTimeout=60"
                    conn_url = f"mssql+pyodbc://{username}:{quote_plus(password)}@{server}:{port}/{database}?{params}"
                elif db_type == "PostgreSQL":
                    conn_url = f"postgresql://{username}:{quote_plus(password)}@{server}:{port}/{database}"
                elif db_type == "MySQL":
                    conn_url = f"mysql+pymysql://{username}:{quote_plus(password)}@{server}:{port}/{database}"
                elif db_type == "SQLite":
                    conn_url = f"sqlite:///{db_file}"
                
                engine = create_engine(conn_url)
                inspector = inspect(engine)
                all_tables = inspector.get_table_names() + inspector.get_view_names()
                st.session_state.db_engine = engine
                st.session_state.tables_list = all_tables
                st.success(f"اتصال موفق! {len(all_tables)} جدول/ویو بارگذاری شد.")
        except Exception as e:
            st.error(f"خطا در برقراری ارتباط: {e}")

if st.session_state.db_engine and st.session_state.tables_list:
    st.header(" انتخاب جدول و آماده‌سازی")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_table = st.selectbox("جدول مورد نظر:", st.session_state.tables_list)
    with col2:
        st.write("") 
        trigger_indexing = st.button("🏗️ استخراج و ایندکس")
        
    if trigger_indexing:
        with st.spinner("در حال پردازش..."):
            table_overview, columns_info = extract_dynamic_schema(st.session_state.db_engine, selected_table)
            
            llm_desc = CustomOpenAIChatModel(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model_name=settings.llm_model_name, temperature=0.1)
            for col in columns_info:
                col["description"] = generate_column_description(llm_desc, col)
            
            embedder_service = EmbeddingService(base_url=settings.embedding_base_url, model=settings.embedding_model)
            ingest_to_milvus(columns_info, embedder_service)
            
            st.session_state.selected_table = selected_table
            st.session_state.indexing_done = True
            st.success(f"ایندکس جدول '{selected_table}' انجام شد!")

if st.session_state.indexing_done:
    st.divider()
    st.header(f" تحلیل جدول [{st.session_state.selected_table}]")
    
    user_query = st.text_input("سوال خود را وارد کنید:", 
                               placeholder="مثال: میانگین مقدار معامله چقدر است؟")
    
    if st.button("🚀 تحلیل"):
        if not user_query:
            st.warning("لطفاً سوال خود را بنویسید.")
        else:
            with st.spinner("در حال تحلیل..."):
                reranker_service = SchemaRetrieveReranker()
                refined_schema = reranker_service.get_refined_schema(user_query, top_k=15)
                
                initial_state = {
                    "question": user_query,
                    "table_name": st.session_state.selected_table,
                    "refined_schema": refined_schema,
                    "sql_query": "",
                    "sql_error": "",
                    "execution_result": {},
                    "retry_count": 0,
                    "analysis_answer": "",
                    "plot_config": None
                }
                
                final_output = compiled_agent.invoke(initial_state)
                
                tab1, tab2, tab3 = st.tabs([" تحلیل و نمودار", "💻 کد SQL", "📋 داده‌ها"])
                
                with tab1:
                    st.subheader(" گزارش تحلیلی")
                    st.write(final_output["analysis_answer"])
                    
                    plot_config = final_output.get("plot_config")
                    if plot_config:
                        raw_data = final_output.get("execution_result", {})
                        if raw_data and "rows" in raw_data and raw_data["rows"]:
                            df_result = pd.DataFrame(raw_data["rows"], columns=raw_data["headers"])
                            fig = create_plotly_chart(df_result, plot_config)
                            if fig:
                                st.plotly_chart(fig, use_container_width=True, theme="streamlit")
                        
                with tab2:
                    st.subheader("🛠️ کد SQL")
                    st.code(final_output["sql_query"], language="sql")
                    
                with tab3:
                    st.subheader("📦 داده‌ها")
                    raw_data = final_output.get("execution_result", {})
                    if raw_data and "rows" in raw_data and raw_data["rows"]:
                        df_result = pd.DataFrame(raw_data["rows"], columns=raw_data["headers"])
                        st.dataframe(df_result, use_container_width=True)
                    else:
                        st.info("داده‌ای یافت نشد.")