import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "dashscope")
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen_plus")
    
    MYSQL_CONFIG = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", 3306)),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "")
    }
    
    POSTGRES_CONFIG = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "database": os.getenv("POSTGRES_DATABASE", "")
    }
    
    SQLITE_CONFIG = {
        "path": os.getenv("SQLITE_PATH", "./example.db")
    }
    
    @classmethod
    def get_database_url(cls, db_type: str) -> str:
        if db_type == "mysql":
            return f"mysql+mysqlconnector://{cls.MYSQL_CONFIG['user']}:{cls.MYSQL_CONFIG['password']}@{cls.MYSQL_CONFIG['host']}:{cls.MYSQL_CONFIG['port']}/{cls.MYSQL_CONFIG['database']}"
        elif db_type == "postgres":
            return f"postgresql+psycopg2://{cls.POSTGRES_CONFIG['user']}:{cls.POSTGRES_CONFIG['password']}@{cls.POSTGRES_CONFIG['host']}:{cls.POSTGRES_CONFIG['port']}/{cls.POSTGRES_CONFIG['database']}"
        elif db_type == "sqlite":
            return f"sqlite:///{cls.SQLITE_CONFIG['path']}"
        elif db_type == "mssql":
            if cls.DATABASE_URL:
                return cls.DATABASE_URL
            raise ValueError("DATABASE_URL not configured for SQL Server")
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
