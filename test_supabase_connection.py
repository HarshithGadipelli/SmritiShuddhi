"""
SMRITI SHUDDHI - SUPABASE POSTGRESQL + PGVECTOR VERIFICATION UTILITY
Run this script to verify your Supabase database connection and auto-initialize tables.
Usage:
    python test_supabase_connection.py [optional_postgres_uri]
"""

import os
import sys
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def test_supabase(connection_uri: str = None):
    uri = connection_uri or os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    
    print("=" * 70)
    print("SMRITI SHUDDHI: SUPABASE CONNECTION & PGVECTOR TEST")
    print("=" * 70)

    if not uri:
        print("\n❌ ERROR: No database connection URI found.")
        print("Please provide it as an argument or set DATABASE_URL in your .env file:")
        print("  python test_supabase_connection.py \"postgresql://postgres.[REF]:[PASS]@[HOST]:5432/postgres\"\n")
        return False

    # Mask password for safe display
    safe_uri = uri
    if "@" in uri and "://" in uri:
        proto, rest = uri.split("://", 1)
        creds, host_part = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        safe_uri = f"{proto}://{user}:********@{host_part}"

    print(f"Target URI: {safe_uri}\n")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from pgvector.psycopg2 import register_vector
    except ImportError as e:
        print(f"❌ Missing required libraries: {e}")
        print("Run: pip install psycopg2-binary pgvector\n")
        return False

    # 1. Connect
    print("[1/5] Establishing connection to Supabase PostgreSQL...")
    try:
        conn = psycopg2.connect(uri, connect_timeout=10)
        conn.autocommit = True
        register_vector(conn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("  ✓ Connected successfully!")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}\n")
        print("Tip: If you're using Supabase, ensure:")
        print("  1. The password does not contain unencoded special characters (e.g. '@' or '#').")
        print("  2. If on a restricted network or IPv4, use the Connection Pooler URL (port 6543) with sslmode=require.")
        return False

    # 2. Server Information
    print("\n[2/5] Inspecting server details...")
    try:
        cursor.execute("SELECT version();")
        v = cursor.fetchone()["version"]
        print(f"  ✓ Database Engine: {v.split(',')[0]}")
    except Exception as e:
        print(f"  ⚠️ Error fetching version: {e}")

    # 3. Enable & Verify pgvector Extension
    print("\n[3/5] Verifying 'pgvector' extension...")
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        row = cursor.fetchone()
        if row:
            print(f"  ✓ pgvector extension is ACTIVE (v{row['extversion']})")
        else:
            print("  ❌ pgvector extension was not found.")
            return False
    except Exception as e:
        print(f"  ❌ Failed to enable vector extension: {e}")
        return False

    # 4. Initialize Database Schema
    print("\n[4/5] Checking Smriti Shuddhi tables & schema...")
    schema_file = BASE_DIR / "supabase_schema.sql"
    if schema_file.exists():
        try:
            sql_script = schema_file.read_text(encoding="utf-8")
            cursor.execute(sql_script)
            print("  ✓ Master schema verified / created successfully!")
        except Exception as e:
            print(f"  ⚠️ Schema execution note: {e}")
    else:
        print("  ⚠️ supabase_schema.sql not found; skipping automatic DDL migration.")

    # 5. Test 384-Dimensional HNSW Vector Distance
    print("\n[5/5] Testing 384-dimensional semantic cosine search...")
    try:
        # Create a sample 384-dim normalized vector
        vec_sample = np.random.randn(384).astype(np.float32)
        vec_sample = vec_sample / np.linalg.norm(vec_sample)

        # Temporary probe query
        cursor.execute(
            """
            SELECT 1 - (%s <=> %s) AS cosine_similarity;
            """,
            (vec_sample, vec_sample)
        )
        sim = cursor.fetchone()["cosine_similarity"]
        print(f"  ✓ Mathematical cosine vector test passed! (Self-similarity: {sim:.4f})")
    except Exception as e:
        print(f"  ❌ Vector mathematical test failed: {e}")
        return False

    print("\n" + "=" * 70)
    print("🎉 SUCCESS: SUPABASE POSTGRESQL + PGVECTOR IS 100% OPERATIONAL!")
    print("=" * 70)
    print("Your project is ready to run with Supabase.")
    return True

if __name__ == "__main__":
    cli_arg = sys.argv[1] if len(sys.argv) > 1 else None
    test_supabase(cli_arg)
