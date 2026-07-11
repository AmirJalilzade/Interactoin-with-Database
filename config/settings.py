class Settings:
    
    #dialect+driver://username:password@host:port/database
    
    db_url =  (
        "mssql+pyodbc://Sa:Passworddjkn%40Secure122%212%21@172.16.31.12:1433/AI_db"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=no"
        "&Encrypt=no"
        "&ConnectionTimeout=60"
        "&LoginTimeout=60"
    )



    llm_base_url = "http://172.16.53.11:83/v1"
    llm_api_key ="123"
    llm_model_name ="/root/.cache/huggingface/hub/models--openai--gpt-oss-20b/snapshots/6cee5e81ee83917806bbde320786a8fb61efebee/"
    llm_temperature = 0.0
    
 
            

    embedding_base_url = "http://127.0.0.1:8009/v1/embeddings"
    embedding_model ="/root/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/"
    embedding_dimention = 1024


    MILVUS_HOST="172.16.42.11"
    MILVUS_PORT=19530
    MILVUS_DIM=1024
    MILVUS_BULK_SIZE=10


settings = Settings()