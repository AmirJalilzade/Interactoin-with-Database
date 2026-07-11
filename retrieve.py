import os
import re
import json
import pickle
from typing import List, Dict, Any, Tuple

# Modern MilvusClient and search wrappers
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker
from pymilvus.model.sparse import BM25EmbeddingFunction
from hazm import word_tokenize  # For Persian tokenization sync

# LangChain tools
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Project config
from llm import CustomOpenAIChatModel
from embedding import EmbeddingService 
from config.settings import settings


def normalize_persian_text(text: str) -> str:
    """
    Normalizes Persian text: converts Arabic characters to Persian,
    and Persian/Arabic numerals to English numerals.
    This significantly improves BM25 exact match hits.
    """
    translation_table = str.maketrans({
        # Numbers
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
        # Characters
        'ي': 'ی', 'ك': 'ک', 'ة': 'ه'
    })
    text = text.translate(translation_table)
    # Remove extra spaces
    return re.sub(r'\s+', ' ', text).strip()


class SchemaRetrieveReranker:
    _milvus_client: MilvusClient = None
    _loaded_collections: set = set()

    def __init__(self, collection_name: str = "column_info_bgem3"):
        self.collection_name = collection_name
        
        if SchemaRetrieveReranker._milvus_client is None:
            SchemaRetrieveReranker._milvus_client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            )
        self.client = SchemaRetrieveReranker._milvus_client
        
        if self.collection_name not in SchemaRetrieveReranker._loaded_collections:
            self.client.load_collection(collection_name=self.collection_name)
            SchemaRetrieveReranker._loaded_collections.add(self.collection_name)

        self.llm = CustomOpenAIChatModel(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model_name=settings.llm_model_name,
            temperature=0.0
        )

        self.embedder = EmbeddingService(
            base_url=settings.embedding_base_url,
            model=settings.embedding_model
        )

        self.bm25_ef = self._initialize_bm25()
        self.json_parser = JsonOutputParser()

    def _initialize_bm25(self) -> BM25EmbeddingFunction:
        pickle_path = "bm25_model.pkl"
        if os.path.exists(pickle_path):
            try:
                with open(pickle_path, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load pickled BM25 matrix ({e}). Re-fitting from scratch...")

        with open("columns_with_desc.json", "r", encoding="utf-8") as f:
            columns_info = json.load(f)
            
        corpus_texts = []
        for col in columns_info:
            lines = [
                f"Table: {col.get('table', 'Unknown')}",
                f"Column: {col.get('column', 'Unknown')}",
                f"Data Type: {col.get('type', 'Unknown')}",
                f"Nullable: {col.get('nullable', 'Unknown')}",
                f"Description: {col.get('description', '').strip()}"
            ]
            if "stats" in col and col["stats"]:
                lines.append(f"Statistics: {json.dumps(col['stats'], ensure_ascii=False)}")
            if "top_values" in col and col["top_values"]:
                lines.append(f"Top Values: {json.dumps(col['top_values'], ensure_ascii=False)}")
                
            corpus_texts.append("\n".join(lines))
        
        bm25_ef = BM25EmbeddingFunction(analyzer=word_tokenize)
        bm25_ef.fit(corpus_texts)
        
        try:
            with open(pickle_path, "wb") as f:
                pickle.dump(bm25_ef, f)
        except Exception as e:
            print(f"[Warning] Could not serialize BM25 matrix to disk: {e}")
            
        return bm25_ef

    # ==========================================
    # NEW LAYER: QUERY PREPROCESSOR
    # ==========================================
    def analyze_and_split_query(self, raw_query: str) -> List[str]:
        """
        Analyzes the query using LLM to correct spelling, and split multiple questions 
        into standalone sub-queries.
        """
        # 1. First Pass: Fast Regex Normalization (Numbers/Characters)
        normalized_query = normalize_persian_text(raw_query)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are a smart AI query preprocessor for a database system. "
             "Your job is to analyze the user's input and do two things:\n"
             "1. Fix any clear spelling mistakes in Persian or English.\n"
             "2. If the user is asking multiple questions at once, split them into independent, standalone questions. "
             "Ensure each split question contains the necessary context (e.g. if they ask 'who makes 6070 and what is its packet', "
             "split to 'who makes 6070?' and 'what is the packet for 6070?').\n\n"
             "If it is a single question, return it as a single item in the list.\n"
             "Output MUST be strict JSON matching this schema:\n"
             "{{\n  \"sub_queries\": [\"question 1\", \"question 2\"]\n}}"),
            ("user", "User Input: {query}")
        ])
        
        chain = prompt | self.llm | self.json_parser
        try:
            response = chain.invoke({"query": normalized_query})
            queries = response.get("sub_queries", [normalized_query])
            return queries if queries else [normalized_query]
        except Exception as e:
            print(f"[Query Analysis Error] Defaulting to normalized raw query: {e}")
            return [normalized_query]

    def hybrid_retrieve(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        dense_vector = self.embedder.embed_query(query)
        sparse_vector = self.bm25_ef.encode_queries([query])

        if sparse_vector is not None and hasattr(sparse_vector, "nnz") and sparse_vector.nnz > 0:
            req_dense = AnnSearchRequest(
                data=[dense_vector],
                anns_field="vector",
                param={"metric_type": "COSINE", "params": {}},
                limit=top_k
            )
            req_sparse = AnnSearchRequest(
                data=[sparse_vector],  
                anns_field="sparse_vector",
                param={"metric_type": "IP", "params": {}},
                limit=top_k
            )
            hybrid_results = self.client.hybrid_search(
                collection_name=self.collection_name,
                reqs=[req_dense, req_sparse],
                ranker=RRFRanker(),
                limit=top_k,
                output_fields=["column_name", "table_name", "chunk_text"]
            )
        else:
            hybrid_results = self.client.search(
                collection_name=self.collection_name,
                data=[dense_vector],
                anns_field="vector",
                search_params={"metric_type": "COSINE", "params": {}},
                limit=top_k,
                output_fields=["column_name", "table_name", "chunk_text"]
            )

        candidates = []
        if hybrid_results:
            raw_hits = hybrid_results[0] if isinstance(hybrid_results, list) and len(hybrid_results) > 0 and isinstance(hybrid_results[0], (list, tuple)) else hybrid_results
            for hit in raw_hits:
                if hasattr(hit, "entity"):
                    entity = hit.entity
                elif isinstance(hit, dict):
                    entity = hit.get("entity", {})
                else:
                    continue
                
                if isinstance(entity, dict):
                    col_name = entity.get("column_name")
                    tab_name = entity.get("table_name")
                    chunk = entity.get("chunk_text")
                else:
                    col_name = getattr(entity, "column_name", None)
                    tab_name = getattr(entity, "table_name", None)
                    chunk = getattr(entity, "chunk_text", None)

                if col_name:
                    candidates.append({
                        "column_name": col_name,
                        "table_name": tab_name,
                        "chunk_text": chunk
                    })
        return candidates

    def llm_rerank(self, query: str, candidates: List[Dict[str, Any]]) -> List[str]:
        if not candidates:
            return []

        schema_formatted = "\n".join([
            f"- Column: {c['column_name']} | Context: {c['chunk_text']}" 
            for c in candidates
        ])

        prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are an elite Database Architect.\n"
             "Analyze the candidate database columns below and select ONLY the column names that are absolutely necessary to answer the user's question.\n"
             "Be strict: filter out columns that look textually or structurally similar but are logically unrelated.\n\n"
             "Your output must be a valid JSON object matching this schema exactly. Do not wrap in backticks or code blocks:\n"
             "{{\n  \"relevant_columns\": [\"column_1\", \"column_2\"]\n}}"),
            ("user", "User Question: {query}\n\nCandidate Columns:\n{schema_formatted}")
        ])

        chain = prompt | self.llm | self.json_parser
        try:
            response = chain.invoke({"query": query, "schema_formatted": schema_formatted})
            return response.get("relevant_columns", [])
        except Exception as e:
            print(f"[Rerank Parse Error] Defaulting to all vector options: {e}")
            return [c["column_name"] for c in candidates]

    # ==========================================
    # NEW: ORCHESTRATOR FOR MULTI-QUERIES
    # ==========================================
    def process_complex_query(self, raw_query: str, top_k: int = 15) -> Tuple[List[str], str]:
        """
        Master function to handle complex inputs. 
        It splits the query, retrieves for all sub-queries, and aggregates the results.
        Returns unique selected columns and their combined schema text.
        """
        print(f"--- Processing Raw Query: '{raw_query}' ---")
        
        # 1. Analyze and Split
        sub_queries = self.analyze_and_split_query(raw_query)
        print(f"[LLM Router] Extracted Sub-Queries: {sub_queries}")
        
        all_selected_columns = set()
        all_refined_chunks = {}

        # 2. Retrieve & Rerank for each sub-query independently
        for sq in sub_queries:
            raw_candidates = self.hybrid_retrieve(sq, top_k=top_k)
            selected = self.llm_rerank(sq, raw_candidates)
            
            for col in selected:
                all_selected_columns.add(col)
            
            # Save chunk texts for selected columns
            for c in raw_candidates:
                if c["column_name"] in selected:
                    all_refined_chunks[c["column_name"]] = c["chunk_text"]

        # 3. Aggregate Final Results
        final_columns = list(all_selected_columns)
        final_schema_text = "\n\n".join(all_refined_chunks.values())
        
        return final_columns, final_schema_text


if __name__ == "__main__":
    pipeline = SchemaRetrieveReranker()
    
    # تست با یک سوال ترکیبی دارای غلط املایی و اعداد فارسی
    test_query = "تولید کننده قیر ۶۰۷۰ کیست و نام پکیج ان چیه؟"
    
    print(f"\nExecuting Advanced Pipeline...\n")
    final_cols, schema_context = pipeline.process_complex_query(test_query, top_k=5)
    
    print("\n--- Final Aggregation ---")
    print(f"-> All Required Columns: {final_cols}")