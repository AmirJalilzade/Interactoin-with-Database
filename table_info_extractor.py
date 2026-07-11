# region 
# import argparse
# import json
# import logging
# from pathlib import Path

# import pandas as pd
# from sqlalchemy import create_engine, text, inspect, Engine
# from sqlalchemy.exc import SQLAlchemyError

# from config.settings import settings # Assuming your settings are in config.py

# # --- Configuration ---
# # Set up basic logging
# logging.basicConfig(
#     level=logging.INFO, 
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )

# # Constants for profiling logic
# SAMPLE_ROW_COUNT = 100
# CATEGORICAL_THRESHOLD = 20 # Consider a column categorical if unique values are below this

# # --- Core Functions ---

# def create_db_engine() -> Engine:
#     """Creates and returns a SQLAlchemy engine using the configured db_url."""
#     try:
#         engine = create_engine(settings.db_url)
#         # Test the connection
#         with engine.connect() as connection:
#             logging.info("Database connection successful.")
#         return engine
#     except SQLAlchemyError as e:
#         logging.error(f"Database connection failed: {e}")
#         raise

# def get_table_schema(inspector: 'Inspector', table_name: str) -> dict:
#     """
#     Retrieves the detailed schema for a given table using SQLAlchemy's Inspector.
    
#     The Inspector is more robust and database-agnostic than a raw SQL query.
#     """
#     logging.info(f"Fetching schema for table '{table_name}'...")
#     try:
#         columns = inspector.get_columns(table_name)
#         if not columns:
#             raise ValueError(f"Table '{table_name}' not found or has no columns.")
            
#         schema_info = {}
#         for col in columns:
#             schema_info[col['name']] = {
#                 "type": str(col['type']),
#                 "is_nullable": col['nullable'],
#                 "default": col['default'],
#                 "is_primary_key": col.get('primary_key', False)
#             }
#         return schema_info
#     except Exception as e:
#         logging.error(f"Could not retrieve schema for table '{table_name}': {e}")
#         raise

# def profile_data_sample(engine: Engine, table_name: str, schema_info: dict) -> dict:
#     """
#     Fetches a sample of data and computes statistics for each column.
#     """
#     logging.info(f"Profiling data sample for table '{table_name}'...")
#     query = f"SELECT TOP {SAMPLE_ROW_COUNT} * FROM {table_name};"
    
#     try:
#         df = pd.read_sql(text(query), engine)
        
#         if df.empty:
#             logging.warning(f"Table '{table_name}' is empty. No data to profile.")
#             return schema_info

#         for col_name, col_data in schema_info.items():
#             if col_name not in df.columns:
#                 continue

#             series = df[col_name]
            
#             # Basic Stats
#             col_data['null_count'] = int(series.isnull().sum())
#             unique_values = series.dropna().unique()
#             col_data['unique_count'] = len(unique_values)

#             # Sample Values
#             if col_data['unique_count'] <= CATEGORICAL_THRESHOLD:
#                 col_data['sample_values'] = sorted([item for item in unique_values])
#             else:
#                 col_data['sample_values'] = series.dropna().sample(min(5, col_data['unique_count'])).tolist()

#             # Type-specific Stats
#             if pd.api.types.is_numeric_dtype(series):
#                 stats = series.describe()
#                 col_data['min'] = stats.get('min')
#                 col_data['max'] = stats.get('max')
#                 col_data['mean'] = stats.get('mean')
#                 col_data['std_dev'] = stats.get('std')
#             elif pd.api.types.is_datetime64_any_dtype(series):
#                 col_data['min'] = series.min()
#                 col_data['max'] = series.max()

#         return schema_info
#     except Exception as e:
#         logging.error(f"Failed to profile data for '{table_name}': {e}")
#         raise

# def json_converter(o):
#     """Custom converter to handle non-serializable types for JSON."""
#     if isinstance(o, (pd.Timestamp, pd.Timedelta)):
#         return o.isoformat()
#     if pd.isna(o):
#         return None
#     # Add other types here if needed
#     raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


# # --- Main Execution ---

# def main():
#     parser = argparse.ArgumentParser(
#         description="Extract schema and profile data from a database table into a JSON file."
#     )
#     parser.add_argument("table_name", type=str, help="The name of the table to profile.")
#     parser.add_argument(
#         "-o", "--output", type=str, 
#         help="Output JSON file name. Defaults to '[table_name]_profile.json'."
#     )
#     args = parser.parse_args()

#     table_name = args.table_name
#     output_file = Path(args.output or f"{table_name}_profile.json")

#     try:
#         engine = create_db_engine()
#         inspector = inspect(engine)

#         # 1. Get the base schema
#         table_profile = get_table_schema(inspector, table_name)

#         # 2. Enhance with data profiling stats
#         table_profile = profile_data_sample(engine, table_name, table_profile)

#         # 3. Save the final result
#         logging.info(f"Saving profile to '{output_file}'...")
#         with open(output_file, 'w', encoding='utf-8') as f:
#             json.dump(
#                 {"table_name": table_name, "columns": table_profile},
#                 f,
#                 indent=4,
#                 ensure_ascii=False,
#                 default=json_converter
#             )
#         logging.info("Profiling complete. ✨")

#     except Exception as e:
#         logging.error(f"An unexpected error occurred: {e}")
#         exit(1)


# if __name__ == "__main__":
#     main()
# endregion
#region
# from config.settings import settings
# from sqlalchemy import create_engine, inspect, Engine, MetaData

# engine = create_engine(settings.db_url)
# inspector = inspect(engine)

# tables = inspector.get_table_names()

# for table in tables:
# #    print(f'your tables are: {table}')
    
#     if "GoodsExchange_Export" in table:
#         columns = inspector.get_columns(table)
#         for column in columns:
#             print(f"  Column: {column['name']} \nType: {column['type']} \n Nullable:{column['nullable']} \n Defualt:{column['default']}")

# print()

# pk = inspector.get_pk_constraint("GoodsExchange_Export")
# primary_keys = pk["constrained_columns"]
# print(f'primary keys:{primary_keys}')

# unique_constraints = inspector.get_unique_constraints("GoodsExchange_Export")
# check_constraints = inspector.get_check_constraints("GoodsExchange_Export")
# indexes = inspector.get_indexes("GoodsExchange_Export")
# table_comment = inspector.get_table_comment("GoodsExchange_Export")



# print(unique_constraints)
# print(check_constraints)
# endregion

# region 3
# import re
# from statistics import median as py_median
# from statistics import pstdev

# from config.settings import settings

# from sqlalchemy import (
#     create_engine,
#     inspect,
#     MetaData,
#     Table,
#     select,
#     func,
#     text
# )

# from sqlalchemy.exc import SQLAlchemyError

# from sqlalchemy.sql.sqltypes import (
#     Integer,
#     Float,
#     Numeric,
#     DECIMAL,
#     REAL,
#     Date,
#     DateTime,
#     String,
#     Text,
#     VARCHAR,
#     CHAR,
#     Unicode,
#     UnicodeText
# )


# # =========================================================
# # CREATE ENGINE
# # =========================================================

# engine = create_engine(settings.db_url)

# inspector = inspect(engine)

# print(f"Dialect: {engine.dialect.name}")
# print(f"Driver : {engine.dialect.driver}")


# # =========================================================
# # TYPE CHECKS
# # =========================================================

# def is_numeric_type(col_type):

#     return isinstance(
#         col_type,
#         (
#             Integer,
#             Float,
#             Numeric,
#             DECIMAL,
#             REAL
#         )
#     )

# def is_datetime_type(col_type):

#     return isinstance(
#         col_type,
#         (
#             DateTime,
#             Date
#         )
#     )

# def is_string_type(col_type):

#     return isinstance(
#         col_type,
#         (
#             String,
#             Text,
#             VARCHAR,
#             CHAR,
#             Unicode,
#             UnicodeText
#         )
#     )


# # =========================================================
# # DATA SAMPLE
# # =========================================================

# def get_data_sample(
#     engine,
#     table_name,
#     limit=5
# ):

#     metadata = MetaData()

#     table = Table(
#         table_name,
#         metadata,
#         autoload_with=engine
#     )

#     try:

#         with engine.connect() as conn:

#             stmt = select(table).limit(limit)

#             result = conn.execute(stmt).mappings().all()

#             return [dict(row) for row in result]

#     except SQLAlchemyError as e:

#         return {"error": str(e)}


# # =========================================================
# # NUMERIC COLUMN STATS
# # =========================================================

# def get_numeric_stats(
#     engine,
#     table_name,
#     column_name
# ):

#     metadata = MetaData()

#     table = Table(
#         table_name,
#         metadata,
#         autoload_with=engine
#     )

#     col = table.c[column_name]

#     stats = {}

#     try:

#         with engine.connect() as conn:

#             # =============================================
#             # BASIC AGGREGATIONS
#             # =============================================

#             stmt = (
#                 select(
#                     func.count().label(
#                         "total_count"
#                     ),

#                     func.count(col).label(
#                         "non_null_count"
#                     ),

#                     func.avg(col).label(
#                         "mean"
#                     ),

#                     func.min(col).label(
#                         "min"
#                     ),

#                     func.max(col).label(
#                         "max"
#                     ),

#                     func.sum(col).label(
#                         "sum"
#                     )
#                 )
#                 .select_from(table)
#             )

#             result = conn.execute(stmt).first()

#             stats = dict(result._mapping)

#             # Null Percentage calculation using $ (total - non_null) / total * 100 $
#             if stats.get("total_count", 0) > 0:
#                 stats["null_percentage"] = (
#                     (stats["total_count"] - stats["non_null_count"]) 
#                     / stats["total_count"]
#                 ) * 100.0
#             else:
#                 stats["null_percentage"] = 0.0

#             # =============================================
#             # STANDARD DEVIATION
#             # =============================================

#             stddev = None

#             if engine.dialect.name in (
#                 "postgresql",
#                 "mysql"
#             ):

#                 try:

#                     std_stmt = (
#                         select(
#                             func.stddev(col)
#                         )
#                         .select_from(table)
#                     )

#                     stddev = conn.execute(
#                         std_stmt
#                     ).scalar()

#                 except Exception:

#                     stddev = None

#             elif engine.dialect.name == "mssql":

#                 try:

#                     std_stmt = (
#                         select(
#                             func.stdev(col)
#                         )
#                         .select_from(table)
#                     )

#                     stddev = conn.execute(
#                         std_stmt
#                     ).scalar()

#                 except Exception:

#                     stddev = None

#             stats["stddev"] = stddev

#             # =============================================
#             # MEDIAN
#             # =============================================

#             median_value = None

#             if engine.dialect.name in (
#                 "postgresql",
#                 "mssql"
#             ):

#                 try:

#                     median_stmt = (
#                         select(
#                             func.percentile_cont(
#                                 0.5
#                             ).within_group(
#                                 col.asc()
#                             )
#                         )
#                         .select_from(table)
#                     )

#                     median_value = conn.execute(
#                         median_stmt
#                     ).scalar()

#                 except Exception:

#                     median_value = None

#             else:

#                 values_stmt = (
#                     select(col)
#                     .where(col.is_not(None))
#                     .select_from(table)
#                 )

#                 values = conn.execute(
#                     values_stmt
#                 ).scalars().all()

#                 if values:

#                     try:

#                         median_value = py_median(
#                             values
#                         )

#                     except Exception:

#                         median_value = None

#                     # SQLite fallback
#                     if (
#                         engine.dialect.name
#                         == "sqlite"
#                         and stats["stddev"] is None
#                     ):

#                         try:

#                             stats["stddev"] = pstdev(
#                                 values
#                             )

#                         except Exception:

#                             stats["stddev"] = None

#             stats["median"] = median_value

#     except SQLAlchemyError as e:

#         stats = {
#             "error": str(e)
#         }

#     return stats


# # =========================================================
# # DATETIME COLUMN STATS
# # =========================================================

# def get_datetime_stats(
#     engine,
#     table_name,
#     column_name
# ):

#     metadata = MetaData()

#     table = Table(
#         table_name,
#         metadata,
#         autoload_with=engine
#     )

#     col = table.c[column_name]

#     stats = {}

#     try:

#         with engine.connect() as conn:

#             stmt = (
#                 select(
#                     func.count().label(
#                         "total_count"
#                     ),

#                     func.count(col).label(
#                         "non_null_count"
#                     ),

#                     func.min(col).label(
#                         "min_date"
#                     ),

#                     func.max(col).label(
#                         "max_date"
#                     )
#                 )
#                 .select_from(table)
#             )

#             result = conn.execute(stmt).first()

#             stats = dict(result._mapping)

#             # Null Percentage
#             if stats.get("total_count", 0) > 0:
#                 stats["null_percentage"] = (
#                     (stats["total_count"] - stats["non_null_count"]) 
#                     / stats["total_count"]
#                 ) * 100.0
#             else:
#                 stats["null_percentage"] = 0.0

#             # =============================================
#             # DATE RANGE
#             # =============================================

#             min_date = stats.get(
#                 "min_date"
#             )

#             max_date = stats.get(
#                 "max_date"
#             )

#             if min_date and max_date:

#                 try:

#                     delta = (
#                         max_date - min_date
#                     )

#                     stats[
#                         "range_days"
#                     ] = delta.days

#                 except Exception:

#                     stats[
#                         "range_days"
#                     ] = None

#             else:

#                 stats[
#                     "range_days"
#                 ] = None

#             # =============================================
#             # TIME PATTERNS (HOUR & DOW)
#             # =============================================
            
#             try:
#                 # Group by Hour
#                 hour_stmt = (
#                     select(
#                         func.extract('hour', col).label('hr'), 
#                         func.count(col).label('freq')
#                     )
#                     .where(col.is_not(None))
#                     .group_by(func.extract('hour', col))
#                 )
#                 hour_res = conn.execute(hour_stmt).fetchall()
#                 stats["hour_distribution"] = {str(r[0]): r[1] for r in hour_res if r[0] is not None}
#             except Exception:
#                 stats["hour_distribution"] = "Not supported or error"

#             try:
#                 # Group by Day of Week (syntax varies heavily by dialect, trying standard 'dow'/'dayofweek')
#                 if engine.dialect.name == "mysql":
#                     dow_func = func.dayofweek(col)
#                 elif engine.dialect.name == "mssql":
#                     dow_func = func.datepart(text('dw'), col)
#                 else:
#                     dow_func = func.extract('dow', col)

#                 dow_stmt = (
#                     select(
#                         dow_func.label('dow'), 
#                         func.count(col).label('freq')
#                     )
#                     .where(col.is_not(None))
#                     .group_by(dow_func)
#                 )
#                 dow_res = conn.execute(dow_stmt).fetchall()
#                 stats["day_of_week_distribution"] = {str(r[0]): r[1] for r in dow_res if r[0] is not None}
#             except Exception:
#                 stats["day_of_week_distribution"] = "Not supported or error"


#     except SQLAlchemyError as e:

#         stats = {
#             "error": str(e)
#         }

#     return stats


# # =========================================================
# # STRING/CATEGORICAL COLUMN STATS
# # =========================================================

# def get_string_stats(
#     engine,
#     table_name,
#     column_name
# ):

#     metadata = MetaData()

#     table = Table(
#         table_name,
#         metadata,
#         autoload_with=engine
#     )

#     col = table.c[column_name]

#     stats = {}

#     try:

#         with engine.connect() as conn:

#             # =============================================
#             # BASIC AGGREGATIONS & CARDINALITY
#             # =============================================

#             stmt = (
#                 select(
#                     func.count().label("total_count"),
#                     func.count(col).label("non_null_count"),
#                     func.count(func.distinct(col)).label("unique_count")
#                 )
#                 .select_from(table)
#             )

#             result = conn.execute(stmt).first()
#             stats = dict(result._mapping)

#             # Null Percentage
#             if stats.get("total_count", 0) > 0:
#                 stats["null_percentage"] = (
#                     (stats["total_count"] - stats["non_null_count"]) 
#                     / stats["total_count"]
#                 ) * 100.0
#             else:
#                 stats["null_percentage"] = 0.0

#             # =============================================
#             # TOP N VALUES (FREQUENCY)
#             # =============================================

#             top_n_stmt = (
#                 select(col, func.count(col).label("freq"))
#                 .where(col.is_not(None))
#                 .group_by(col)
#                 .order_by(func.count(col).desc())
#                 .limit(5)
#             )
#             top_n_res = conn.execute(top_n_stmt).fetchall()
#             stats["top_5_values"] = {str(r[0]): r[1] for r in top_n_res}

#             # =============================================
#             # DATA PATTERNS (REGEX MATCHING)
#             # =============================================
#             # To be dialect-agnostic, fetch value frequencies 
#             # and compute regex pattern stats in Python

#             all_vals_stmt = (
#                 select(col, func.count(col).label("freq"))
#                 .where(col.is_not(None))
#                 .group_by(col)
#             )
#             all_vals_res = conn.execute(all_vals_stmt).fetchall()

#             email_pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
#             phone_pattern = re.compile(r'^\+?[\d\s\-\(\)]{7,20}$')

#             email_count = 0
#             phone_count = 0

#             for val, freq in all_vals_res:
#                 str_val = str(val).strip()
#                 if email_pattern.match(str_val):
#                     email_count += freq
#                 elif phone_pattern.match(str_val):
#                     phone_count += freq

#             if stats["non_null_count"] > 0:
#                 stats["email_format_percentage"] = (email_count / stats["non_null_count"]) * 100.0
#                 stats["phone_format_percentage"] = (phone_count / stats["non_null_count"]) * 100.0
#             else:
#                 stats["email_format_percentage"] = 0.0
#                 stats["phone_format_percentage"] = 0.0

#     except SQLAlchemyError as e:

#         stats = {
#             "error": str(e)
#         }

#     return stats


# # =========================================================
# # COMMENTS EXTRACTION
# # =========================================================

# def get_comments(
#     engine,
#     table_name,
#     schema=None
# ):

#     dialect = engine.dialect.name

#     result = {
#         "table_comment": None,
#         "column_comments": {},
#     }

#     try:

#         with engine.connect() as conn:

#             # =============================================
#             # POSTGRESQL
#             # =============================================

#             if dialect == "postgresql":

#                 query = text("""
#                     SELECT
#                         a.attname AS column_name,
#                         pg_catalog.col_description(
#                             a.attrelid,
#                             a.attnum
#                         ) AS comment
#                     FROM pg_catalog.pg_attribute a
#                     JOIN pg_catalog.pg_class c
#                         ON a.attrelid = c.oid
#                     WHERE c.relname = :table
#                       AND a.attnum > 0
#                       AND NOT a.attisdropped
#                 """)

#                 rows = conn.execute(
#                     query,
#                     {"table": table_name}
#                 ).fetchall()

#                 result["column_comments"] = {
#                     row[0]: row[1]
#                     for row in rows
#                 }

#                 tbl_query = text("""
#                     SELECT obj_description(c.oid)
#                     FROM pg_catalog.pg_class c
#                     WHERE c.relname = :table
#                       AND c.relkind = 'r'
#                 """)

#                 result["table_comment"] = conn.execute(
#                     tbl_query,
#                     {"table": table_name}
#                 ).scalar()

#             # =============================================
#             # MYSQL
#             # =============================================

#             elif dialect == "mysql":

#                 quoted_table = (
#                     engine.dialect.identifier_preparer.quote(
#                         table_name
#                     )
#                 )

#                 query = text(
#                     f"SHOW FULL COLUMNS FROM {quoted_table}"
#                 )

#                 rows = conn.execute(query).fetchall()

#                 result["column_comments"] = {
#                     row[0]: row[8]
#                     for row in rows
#                 }

#                 tbl_query = text("""
#                     SELECT TABLE_COMMENT
#                     FROM INFORMATION_SCHEMA.TABLES
#                     WHERE TABLE_SCHEMA = DATABASE()
#                       AND TABLE_NAME = :table
#                 """)

#                 result["table_comment"] = conn.execute(
#                     tbl_query,
#                     {"table": table_name}
#                 ).scalar()

#             # =============================================
#             # MSSQL
#             # =============================================

#             elif dialect == "mssql":

#                 if schema is None:
#                     schema = "dbo"

#                 query = text("""
#                     SELECT
#                         objname AS column_name,
#                         CAST(value AS NVARCHAR(MAX)) AS comment
#                     FROM ::fn_listextendedproperty(
#                         'MS_Description',
#                         'schema',
#                         :schema,
#                         'table',
#                         :table,
#                         'column',
#                         NULL
#                     )
#                 """)

#                 rows = conn.execute(
#                     query,
#                     {
#                         "schema": schema,
#                         "table": table_name
#                     }
#                 ).fetchall()

#                 result["column_comments"] = {
#                     row[0]: row[1]
#                     for row in rows
#                 }

#                 tbl_query = text("""
#                     SELECT
#                         CAST(value AS NVARCHAR(MAX))
#                     FROM ::fn_listextendedproperty(
#                         'MS_Description',
#                         'schema',
#                         :schema,
#                         'table',
#                         :table,
#                         NULL,
#                         NULL
#                     )
#                 """)

#                 result["table_comment"] = conn.execute(
#                     tbl_query,
#                     {
#                         "schema": schema,
#                         "table": table_name
#                     }
#                 ).scalar()

#             # =============================================
#             # UNSUPPORTED DIALECT
#             # =============================================

#             else:

#                 result["table_comment"] = (
#                     "Comments not supported "
#                     "for this dialect."
#                 )

#     except SQLAlchemyError as e:

#         result["error"] = str(e)

#     return result


# # =========================================================
# # TARGET TABLE
# # =========================================================

# target_table = "GoodsExchange_Export"

# tables = inspector.get_table_names()

# schema_info = {}

# # =========================================================
# # FIND TABLE
# # =========================================================

# for table in tables:

#     if table == target_table:

#         print(f"\n{'=' * 70}")
#         print(f"TABLE: {table}")
#         print(f"{'=' * 70}")

#         # =============================================
#         # DATA SAMPLE
#         # =============================================

#         print("\nDATA SAMPLE:\n")
#         data_sample = get_data_sample(engine, table, limit=5)
#         schema_info["data_sample"] = data_sample
#         for idx, row in enumerate(data_sample):
#             print(f"Row {idx+1}: {row}")

#         # =============================================
#         # COLUMNS
#         # =============================================

#         print("\nCOLUMNS:\n")

#         columns = inspector.get_columns(table)

#         structured_columns = []

#         numeric_analysis = {}

#         datetime_analysis = {}

#         string_analysis = {}

#         for column in columns:

#             column_info = {
#                 "name": column["name"],
#                 "type": str(column["type"]),
#                 "nullable": column["nullable"],
#                 "default": column["default"],
#             }

#             structured_columns.append(
#                 column_info
#             )

#             print(
#                 f"\nColumn   : {column['name']}\n"
#                 f"Type     : {column['type']}\n"
#                 f"Nullable : {column['nullable']}\n"
#                 f"Default  : {column['default']}"
#             )

#             # =========================================
#             # NUMERIC ANALYSIS
#             # =========================================

#             if is_numeric_type(
#                 column["type"]
#             ):

#                 print(
#                     f"-> Analyzing numeric column: "
#                     f"{column['name']}"
#                 )

#                 stats = get_numeric_stats(
#                     engine=engine,
#                     table_name=table,
#                     column_name=column["name"]
#                 )

#                 numeric_analysis[
#                     column["name"]
#                 ] = stats

#             # =========================================
#             # DATETIME ANALYSIS
#             # =========================================

#             if is_datetime_type(
#                 column["type"]
#             ):

#                 print(
#                     f"-> Analyzing datetime column: "
#                     f"{column['name']}"
#                 )

#                 stats = get_datetime_stats(
#                     engine=engine,
#                     table_name=table,
#                     column_name=column["name"]
#                 )

#                 datetime_analysis[
#                     column["name"]
#                 ] = stats

#             # =========================================
#             # STRING/CATEGORICAL ANALYSIS
#             # =========================================

#             if is_string_type(
#                 column["type"]
#             ):

#                 print(
#                     f"-> Analyzing string column: "
#                     f"{column['name']}"
#                 )

#                 stats = get_string_stats(
#                     engine=engine,
#                     table_name=table,
#                     column_name=column["name"]
#                 )

#                 string_analysis[
#                     column["name"]
#                 ] = stats

#         schema_info["columns"] = (
#             structured_columns
#         )

#         schema_info[
#             "numeric_analysis"
#         ] = numeric_analysis

#         schema_info[
#             "datetime_analysis"
#         ] = datetime_analysis

#         schema_info[
#             "string_analysis"
#         ] = string_analysis

#         # =============================================
#         # PRIMARY KEYS
#         # =============================================

#         try:

#             pk = inspector.get_pk_constraint(
#                 table
#             )

#             primary_keys = pk.get(
#                 "constrained_columns",
#                 []
#             )

#             schema_info[
#                 "primary_keys"
#             ] = primary_keys

#             print(
#                 f"\nPRIMARY KEYS:\n"
#                 f"{primary_keys}"
#             )

#         except Exception as e:

#             schema_info[
#                 "primary_keys"
#             ] = []

#             print(
#                 f"\nPRIMARY KEY ERROR:\n{e}"
#             )

#         # =============================================
#         # FOREIGN KEYS
#         # =============================================

#         try:

#             foreign_keys = (
#                 inspector.get_foreign_keys(
#                     table
#                 )
#             )

#             schema_info[
#                 "foreign_keys"
#             ] = foreign_keys

#             print(
#                 f"\nFOREIGN KEYS:\n"
#                 f"{foreign_keys}"
#             )

#         except Exception as e:

#             schema_info[
#                 "foreign_keys"
#             ] = []

#             print(
#                 f"\nFOREIGN KEY ERROR:\n{e}"
#             )

#         # =============================================
#         # UNIQUE CONSTRAINTS
#         # =============================================

#         try:

#             unique_constraints = (
#                 inspector.get_unique_constraints(
#                     table
#                 )
#             )

#             schema_info[
#                 "unique_constraints"
#             ] = unique_constraints

#             print(
#                 f"\nUNIQUE CONSTRAINTS:\n"
#                 f"{unique_constraints}"
#             )

#         except NotImplementedError:

#             schema_info[
#                 "unique_constraints"
#             ] = "Not supported"

#             print(
#                 "\nUNIQUE CONSTRAINTS:\n"
#                 "Not supported by dialect."
#             )

#         except Exception as e:

#             schema_info[
#                 "unique_constraints"
#             ] = []

#             print(
#                 f"\nUNIQUE CONSTRAINT ERROR:\n{e}"
#             )

#         # =============================================
#         # CHECK CONSTRAINTS
#         # =============================================

#         try:

#             check_constraints = (
#                 inspector.get_check_constraints(
#                     table
#                 )
#             )

#             schema_info[
#                 "check_constraints"
#             ] = check_constraints

#             print(
#                 f"\nCHECK CONSTRAINTS:\n"
#                 f"{check_constraints}"
#             )

#         except NotImplementedError:

#             schema_info[
#                 "check_constraints"
#             ] = "Not supported"

#             print(
#                 "\nCHECK CONSTRAINTS:\n"
#                 "Not supported by dialect."
#             )

#         except Exception as e:

#             schema_info[
#                 "check_constraints"
#             ] = []

#             print(
#                 f"\nCHECK CONSTRAINT ERROR:\n{e}"
#             )

#         # =============================================
#         # INDEXES
#         # =============================================

#         try:

#             indexes = inspector.get_indexes(
#                 table
#             )

#             schema_info[
#                 "indexes"
#             ] = indexes

#             print(
#                 f"\nINDEXES:\n"
#                 f"{indexes}"
#             )

#         except NotImplementedError:

#             schema_info[
#                 "indexes"
#             ] = "Not supported"

#             print(
#                 "\nINDEXES:\n"
#                 "Not supported by dialect."
#             )

#         except Exception as e:

#             schema_info[
#                 "indexes"
#             ] = []

#             print(
#                 f"\nINDEX ERROR:\n{e}"
#             )

#         # =============================================
#         # COMMENTS
#         # =============================================

#         comments = get_comments(
#             engine=engine,
#             table_name=table
#         )

#         schema_info[
#             "comments"
#         ] = comments

#         print(
#             f"\nTABLE COMMENT:\n"
#             f"{comments['table_comment']}"
#         )

#         print("\nCOLUMN COMMENTS:")

#         for col, comment in comments[
#             "column_comments"
#         ].items():

#             print(f"{col}: {comment}")


# # =========================================================
# # FINAL STRUCTURED OUTPUT
# # =========================================================

# print(f"\n{'=' * 70}")
# print("FINAL STRUCTURED SCHEMA")
# print(f"{'=' * 70}")

# import pprint
# pprint.pprint(schema_info, depth=4)
# endregion

import json
from datetime import datetime, date
from decimal import Decimal
from statistics import median as py_median
from statistics import pstdev

from config.settings import settings

from sqlalchemy import (
    create_engine,
    inspect,
    MetaData,
    Table,
    select,
    func,
    text
)

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.sql.sqltypes import (
    Integer,
    Float,
    Numeric,
    DECIMAL,
    REAL,
    Date,
    DateTime,
    String,
    Text,
    VARCHAR,
    CHAR,
    Unicode,
    UnicodeText
)

# ENGINE

engine = create_engine(settings.db_url)
inspector = inspect(engine)


# UTILITIES
print("wait for it bitch!!! I am trying here.")
def convert_value(v):

    if isinstance(v, Decimal):
        return float(v)

    if isinstance(v, (datetime, date)):
        return v.isoformat()

    return v


def clean_dict(d):

    return {k: convert_value(v) for k, v in d.items()}


# =========================================================
# DATABASE INFO
# =========================================================

def get_database_info(engine):

    info = {
        "dialect": engine.dialect.name,
        "driver": engine.dialect.driver,
    }

    try:

        with engine.connect() as conn:

            if engine.dialect.name == "sqlite":
                res = conn.execute(text("SELECT sqlite_version()")).scalar()

            elif engine.dialect.name == "mssql":
                res = conn.execute(text("SELECT @@VERSION")).scalar()

            else:
                res = conn.execute(text("SELECT version()")).scalar()

            info["version_string"] = str(res)

    except Exception as e:

        info["version_string_error"] = str(e)

    return info


# =========================================================
# TYPE CHECKS
# =========================================================

def is_numeric_type(col_type):

    return isinstance(col_type, (Integer, Float, Numeric, DECIMAL, REAL))


def is_datetime_type(col_type):

    return isinstance(col_type, (DateTime, Date))


def is_string_type(col_type):

    return isinstance(col_type, (String, Text, VARCHAR, CHAR, Unicode, UnicodeText))


# =========================================================
# TOP VALUES (categorical only)
# =========================================================

def get_top_values(engine, table_name, column_name, limit=10):

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    col = table.c[column_name]

    try:

        with engine.connect() as conn:

            stmt = (
                select(
                    col,
                    func.count().label("count")
                )
                .where(col.is_not(None))
                .group_by(col)
                .order_by(func.count().desc())
                .limit(limit)
            )

            rows = conn.execute(stmt).fetchall()

            return [
                {
                    "value": convert_value(r[0]),
                    "count": r[1]
                }
                for r in rows
            ]

    except SQLAlchemyError as e:

        return {"error": str(e)}


# =========================================================
# NUMERIC STATS
# =========================================================

def get_numeric_stats(engine, table_name, column_name):

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    col = table.c[column_name]

    stats = {}

    try:

        with engine.connect() as conn:

            stmt = select(
                func.count().label("total_count"),
                func.count(col).label("non_null_count"),
                func.avg(col).label("mean"),
                func.min(col).label("min"),
                func.max(col).label("max"),
                func.sum(col).label("sum")
            ).select_from(table)

            result = conn.execute(stmt).first()

            stats = clean_dict(dict(result._mapping))

            total = stats["total_count"]
            non_null = stats["non_null_count"]

            stats["null_percentage"] = (
                (total - non_null) / total * 100 if total else 0
            )

            values = conn.execute(
                select(col).where(col.is_not(None))
            ).scalars().all()

            if values:

                values = [float(v) if isinstance(v, Decimal) else v for v in values]

                stats["median"] = py_median(values)

                try:
                    stats["stddev"] = pstdev(values)
                except Exception:
                    stats["stddev"] = None

    except SQLAlchemyError as e:

        stats = {"error": str(e)}

    return stats


# =========================================================
# DATETIME STATS
# =========================================================

def get_datetime_stats(engine, table_name, column_name):

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    col = table.c[column_name]

    stats = {}

    try:

        with engine.connect() as conn:

            stmt = select(
                func.count().label("total_count"),
                func.count(col).label("non_null_count"),
                func.min(col).label("min_date"),
                func.max(col).label("max_date")
            ).select_from(table)

            result = conn.execute(stmt).first()

            stats = clean_dict(dict(result._mapping))

            total = stats["total_count"]
            non_null = stats["non_null_count"]

            stats["null_percentage"] = (
                (total - non_null) / total * 100 if total else 0
            )

            if stats["min_date"] and stats["max_date"]:

                try:

                    d1 = datetime.fromisoformat(stats["min_date"])
                    d2 = datetime.fromisoformat(stats["max_date"])

                    stats["range_days"] = (d2 - d1).days

                except Exception:

                    stats["range_days"] = None

    except SQLAlchemyError as e:

        stats = {"error": str(e)}

    return stats


# =========================================================
# STRING STATS
# =========================================================

def get_string_stats(engine, table_name, column_name):

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    col = table.c[column_name]

    stats = {}

    try:

        with engine.connect() as conn:

            stmt = select(
                func.count().label("total_count"),
                func.count(col).label("non_null_count"),
                func.count(func.distinct(col)).label("unique_count")
            ).select_from(table)

            result = conn.execute(stmt).first()

            stats = clean_dict(dict(result._mapping))

            total = stats["total_count"]
            non_null = stats["non_null_count"]

            stats["null_percentage"] = (
                (total - non_null) / total * 100 if total else 0
            )

    except SQLAlchemyError as e:

        stats = {"error": str(e)}

    return stats


# =========================================================
# SCHEMA EXTRACTION
# =========================================================

def extract_schema(engine):

    target_table = "GoodsExchange"
    tables = [target_table]


    table_overview = []
    columns_info = []

    for table_name in tables:

        columns = inspector.get_columns(table_name)
        pk = inspector.get_pk_constraint(table_name)
        fks = inspector.get_foreign_keys(table_name)

        table_overview.append({
            "table_name": table_name,
            "column_count": len(columns),
            "primary_key": pk.get("constrained_columns"),
            "foreign_keys": fks
        })

        for col in columns:

            col_name = col["name"]
            col_type = col["type"]

            column_doc = {
                "table": table_name,
                "column": col_name,
                "type": str(col_type),
                "nullable": col["nullable"],
                "default": str(col.get("default"))
            }

            if is_numeric_type(col_type):

                column_doc["stats"] = get_numeric_stats(
                    engine, table_name, col_name
                )

            elif is_datetime_type(col_type):

                column_doc["stats"] = get_datetime_stats(
                    engine, table_name, col_name
                )

            elif is_string_type(col_type):

                column_doc["stats"] = get_string_stats(
                    engine, table_name, col_name
                )

                column_doc["top_values"] = get_top_values(
                    engine, table_name, col_name
                )

            else:

                column_doc["stats"] = {}

            columns_info.append(column_doc)

    return table_overview, columns_info


# =========================================================
# SAVE JSON
# =========================================================

def save_json(data, filename):

    with open(filename, "w", encoding="utf-8") as f:

        json.dump(data, f, indent=2, ensure_ascii=False)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    db_info = get_database_info(engine)

    table_overview, columns_info = extract_schema(engine)

    save_json(
        {
            "database_info": db_info,
            "tables": table_overview
        },
        "table_overview.json"
    )

    save_json(
        columns_info,
        "columns_info.json"
    )

    print("✅ Generated:")
    print("table_overview.json")
    print("columns_info.json")
