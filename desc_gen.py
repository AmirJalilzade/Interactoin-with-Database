# generate_descriptions.py

import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, List, Dict

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from sqlalchemy import create_engine, inspect, MetaData, Table, select, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.sqltypes import (
    Integer, Float, Numeric, DECIMAL, REAL,
    Date, DateTime,
    String, Text, VARCHAR, CHAR, Unicode, UnicodeText,
)
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import settings
from llm import CustomOpenAIChatModel

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

TARGET_TABLE = "GoodsExchange"
LLM_BATCH_CHUNK_SIZE = 30  # How many columns to send in a single LLM prompt

# ============================================================
# ENGINE
# ============================================================

engine = create_engine(settings.db_url)

# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _convert_value(v: Any) -> Any:
    """Make a single value JSON-serializable."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v

def _clean_dict(d: dict) -> dict:
    return {k: _convert_value(v) for k, v in d.items()}

def _parse_llm_json(response_text: str) -> dict:
    """Safely parse JSON from LLM responses, stripping potential markdown formatting."""
    cleaned = response_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())

# ============================================================
# DATABASE META INFO
# ============================================================

def get_database_info(engine) -> dict:
    info = {"dialect": engine.dialect.name, "driver": engine.dialect.driver}
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                res = conn.execute(text("SELECT sqlite_version()")).scalar()
            elif engine.dialect.name == "mssql":
                res = conn.execute(text("SELECT @@VERSION")).scalar()
            else:
                res = conn.execute(text("SELECT version()")).scalar()
            info["version_string"] = str(res)
    except Exception as exc:
        logger.warning("Could not retrieve DB version string: %s", exc)
        info["version_string_error"] = str(exc)
    return info

# ============================================================
# COLUMN TYPE DETECTION
# ============================================================

def _is_numeric(col_type) -> bool:
    return isinstance(col_type, (Integer, Float, Numeric, DECIMAL, REAL))

def _is_datetime(col_type) -> bool:
    return isinstance(col_type, (DateTime, Date))

def _is_string(col_type) -> bool:
    return isinstance(col_type, (String, Text, VARCHAR, CHAR, Unicode, UnicodeText))

# ============================================================
# COLUMN STATISTICS (Optimized with Connection Reuse)
# ============================================================

def get_numeric_stats(conn, table: Table, col) -> dict:
    stats: dict = {}
    dialect = conn.engine.dialect.name
    try:
        stmt = select(
            func.count().label("total_count"),
            func.count(col).label("non_null_count"),
            func.avg(col).label("mean"),
            func.min(col).label("min"),
            func.max(col).label("max"),
        ).select_from(table)
        row = conn.execute(stmt).first()
        stats = _clean_dict(dict(row._mapping))

        total = stats["total_count"]
        non_null = stats["non_null_count"]
        stats["null_percentage"] = round((total - non_null) / total * 100, 2) if total else 0.0

        if dialect == "mssql":
            median_row = conn.execute(text(
                f"SELECT TOP 1 PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY [{col.name}]) OVER () "
                f"FROM [{table.name}] WHERE [{col.name}] IS NOT NULL"
            )).first()
            stats["median"] = _convert_value(median_row[0]) if median_row else None
        elif dialect == "postgresql":
            row = conn.execute(text(
                f'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "{col.name}") '
                f'FROM "{table.name}" WHERE "{col.name}" IS NOT NULL'
            )).first()
            if row: stats["median"] = _convert_value(row[0])

    except SQLAlchemyError as exc:
        logger.error("Numeric stats failed for %s: %s", col.name, exc)
    return stats

def get_datetime_stats(conn, table: Table, col) -> dict:
    stats: dict = {}
    try:
        stmt = select(
            func.count().label("total_count"),
            func.count(col).label("non_null_count"),
            func.min(col).label("min_date"),
            func.max(col).label("max_date"),
        ).select_from(table)
        row = conn.execute(stmt).first()
        stats = _clean_dict(dict(row._mapping))

        total = stats["total_count"]
        non_null = stats["non_null_count"]
        stats["null_percentage"] = round((total - non_null) / total * 100, 2) if total else 0.0
    except SQLAlchemyError as exc:
        logger.error("Datetime stats failed for %s: %s", col.name, exc)
    return stats

def get_string_stats(conn, table: Table, col) -> dict:
    stats: dict = {}
    try:
        stmt = select(
            func.count().label("total_count"),
            func.count(col).label("non_null_count"),
            func.count(func.distinct(col)).label("unique_count"),
        ).select_from(table)
        row = conn.execute(stmt).first()
        stats = _clean_dict(dict(row._mapping))

        total = stats["total_count"]
        non_null = stats["non_null_count"]
        stats["null_percentage"] = round((total - non_null) / total * 100, 2) if total else 0.0
        stats["cardinality_ratio"] = round(stats["unique_count"] / non_null, 4) if non_null else 0.0
    except SQLAlchemyError as exc:
        logger.error("String stats failed for %s: %s", col.name, exc)
    return stats

def get_top_values(conn, table: Table, col, limit: int = 10) -> list:
    try:
        stmt = (
            select(col, func.count().label("count"))
            .where(col.is_not(None))
            .group_by(col)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = conn.execute(stmt).fetchall()
        return [{"value": _convert_value(r[0]), "count": r[1]} for r in rows]
    except SQLAlchemyError as exc:
        logger.error("Top values failed for %s: %s", col.name, exc)
        return []

# ============================================================
# SCHEMA EXTRACTION (Connection Reused)
# ============================================================

def extract_schema(engine, table_name: str) -> tuple[list, list]:
    insp = inspect(engine)
    columns = insp.get_columns(table_name)
    pk = insp.get_pk_constraint(table_name)
    fks = insp.get_foreign_keys(table_name)

    table_overview = [{
        "table_name": table_name,
        "column_count": len(columns),
        "primary_key": pk.get("constrained_columns"),
        "foreign_keys": fks,
    }]

    columns_info: list = []
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)

    #  SINGLE CONNECTION REUSED FOR ALL STATS 
    with engine.connect() as conn:
        for col_dict in columns:
            col_name = col_dict["name"]
            col_type = col_dict["type"]
            col_obj = table.c[col_name]

            column_doc: dict = {
                "table": table_name,
                "column": col_name,
                "type": str(col_type),
                "nullable": col_dict["nullable"],
            }

            if _is_numeric(col_type):
                column_doc["stats"] = get_numeric_stats(conn, table, col_obj)
            elif _is_datetime(col_type):
                column_doc["stats"] = get_datetime_stats(conn, table, col_obj)
            elif _is_string(col_type):
                column_doc["stats"] = get_string_stats(conn, table, col_obj)
                column_doc["top_values"] = get_top_values(conn, table, col_obj)
            else:
                column_doc["stats"] = {}

            columns_info.append(column_doc)
            logger.debug("Extracted: %s.%s", table_name, col_name)

    return table_overview, columns_info

# ============================================================
# BATCHED LLM DESCRIPTION GENERATION
# ============================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_llm(llm, messages: list):
    return llm.invoke(messages)

def generate_batched_column_descriptions(llm, columns_info: List[Dict], table_name: str) -> List[Dict]:
    """
    Sends columns to the LLM in chunks. Returns JSON mapped descriptions.
    """
    system_prompt = (
        "You are an expert Database Administrator. "
        "Analyze the following JSON list of column metadata and statistics. "
        "Return a STRICT JSON dictionary where keys are column names, and values are objects "
        "containing two keys: 'description' (a concise 1-sentence business purpose) and "
        "'data_quality' (a 1-sentence note on stats like sparsity, range, or cardinality). "
        "RESPOND ENTIRELY IN PERSIAN. DO NOT output markdown or extra text outside the JSON."
    )

    # Process in chunks to avoid context limits and ensure complete JSON generation
    for i in range(0, len(columns_info), LLM_BATCH_CHUNK_SIZE):
        chunk = columns_info[i:i + LLM_BATCH_CHUNK_SIZE]
        logger.info(f"  Sending chunk {i//LLM_BATCH_CHUNK_SIZE + 1} ({len(chunk)} columns) to LLM...")
        
        # Strip heavy arrays if they exist to save tokens, but keep top_values
        prompt_data = [
            {
                "column": c["column"], "type": c["type"], "nullable": c["nullable"],
                "stats": c.get("stats", {}), "top_values": c.get("top_values", [])
            } for c in chunk
        ]

        user_prompt = f"Table: {table_name}\nMetadata:\n{json.dumps(prompt_data, ensure_ascii=False)}"
        
        try:
            response = _call_llm(llm, [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            parsed_results = _parse_llm_json(response.content)
            
            # Merge results back into original column dicts
            for col in chunk:
                llm_data = parsed_results.get(col["column"], {})
                col["description"] = llm_data.get("description", "Description generation failed.")
                col["data_quality"] = llm_data.get("data_quality", "")
                
        except Exception as exc:
            logger.error("Failed to generate batched descriptions for chunk: %s", exc)
            for col in chunk:
                col["description"] = f"Error: {exc}"
                col["data_quality"] = ""

    return columns_info

def generate_table_description(llm, table_overview: dict, columns_with_desc: list) -> str:
    col_summaries = "\n".join(
        f"- {c['column']}: {c.get('description', '')}"
        for c in columns_with_desc if c["table"] == table_overview["table_name"]
    )
    
    system_prompt = (
        "You are an expert Database Documentation Architect. "
        "Based on the provided metadata and column descriptions, write a cohesive, professional "
        "paragraph (3–5 sentences) explaining the overarching business purpose of this table. "
        "RESPOND ENTIRELY IN PERSIAN."
    )
    
    user_prompt = (
        f"Table: {table_overview['table_name']}\n"
        f"Primary Key: {table_overview['primary_key']}\n"
        f"Columns:\n{col_summaries}"
    )
    
    response = _call_llm(llm, [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    return response.content.strip()

# ============================================================
# FILE I/O
# ============================================================

def save_json(data: Any, filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("Saved → %s", filename)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Schema Enrichment Pipeline (Batched) — table: %s", TARGET_TABLE)
    logger.info("=" * 60)

    # ── Step 1: database info + schema extraction ──────────────
    logger.info("Step 1/4  Connecting to DB and extracting schema...")
    db_info = get_database_info(engine)
    table_overview, columns_info = extract_schema(engine, TARGET_TABLE)
    logger.info("          Found %d columns in '%s'.", len(columns_info), TARGET_TABLE)

    # ── Step 2: instantiate the LLM ───────────────────────────
    logger.info("Step 2/4  Initialising LLM...")
    llm = CustomOpenAIChatModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.llm_model_name,
        temperature=0.0,   #  0.0 for deterministic JSON formatting
    )

    # ── Step 3: batched description generation ─────────────────
    logger.info("Step 3/4  Generating column descriptions (Batched JSON)...")
    columns_info = generate_batched_column_descriptions(llm, columns_info, TARGET_TABLE)

    # ── Step 4: describe the table ─────────────────────────────
    logger.info("Step 4/4  Generating table-level description...")
    for table in table_overview:
        try:
            table["description"] = generate_table_description(llm, table, columns_info)
            logger.info("          ✔ Table described: %s", table["table_name"])
        except Exception as exc:
            table["description"] = f"Error: {exc}"
            logger.error("          ✘ Table description failed: %s", exc)

    # ── Persist ────────────────────────────────────────────────
    save_json({"database_info": db_info, "tables": table_overview}, "table_overview_with_desc.json")
    save_json(columns_info, "columns_with_desc.json")

    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info("=" * 60)