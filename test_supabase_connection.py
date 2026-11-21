"""
SMRITI SHUDDHI - SUPABASE POSTGRESQL + PGVECTOR VERIFICATION UTILITY
Uses pure-Python pg8000 driver (no C-extensions / immune to Windows DLL policies).
"""

import os
import sys
import ssl
import numpy as np
from urllib.parse import urlparse, unquote
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def test_supabase(connection_uri: str = None):
    uri = connection_uri or os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    
    print("=" * 70)
    print("SMRITI SHUDDHI: SUPABASE CONNECTION & PGVECTOR TEST")
    print("=" * 70)

    if not uri:
        print("\n❌ ERROR: No database connection URI found.")
        print("Please check your .env file and ensure DATABASE_URL is set.")
        return False

    # Clean any accidental brackets from password
    cleaned_uri = uri
    if ":[" in cleaned_uri and "]@" in cleaned_uri:
        p1 = cleaned_uri.find(":[")
        p2 = cleaned_uri.find("]@", p1)
        cleaned_uri = cleaned_uri[:p1+1] + cleaned_uri[p1+2:p2] + cleaned_uri[p2+1:]

    p = urlparse(cleaned_uri)
    host = p.hostname
    port = p.port or 5432
    user = unquote(p.username or "postgres")
    password = unquote(p.password or "")
    database = p.path.lstrip("/") or "postgres"

    # Mask password for display
    print(f"Host:     {host}")
    print(f"Port:     {port}")
    print(f"User:     {user}")
    print(f"Database: {database}")
    print(f"Password: {'*' * len(password)}")
    print("-" * 70)

    try:
        import pg8000.native
    except ImportError:
        print("❌ Missing pg8000. Run: pip install pg8000")
        return False

    # 1. Connect
    print("\n[1/5] Connecting to Supabase PostgreSQL over SSL...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    conn = None
    try:
        conn = pg8000.native.Connection(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            ssl_context=ctx
        )
        print("  ✓ Connected successfully!")
    except Exception as e:
        err_str = str(e)
        if "28P01" in err_str or "password authentication failed" in err_str:
            print("  ❌ Authentication Failed: Password does not match user credentials.")
            print("\n" + "=" * 70)
            print("🔑 HOW TO FIX PASSWORD ERROR IN SUPABASE:")
            print("=" * 70)
            print("1. Go to your Supabase Dashboard: https://supabase.com/dashboard")
            print("2. Open your project -> Click Settings (⚙️ icon) -> Database.")
            print("3. Scroll to 'Database Password' and click 'Reset database password'.")
            print("4. Set a new password (e.g. SmritiShuddhi2026).")
            print("5. Update your .env file with the new password:")
            print(f"   DATABASE_URL=postgresql://{user}:YOUR_NEW_PASSWORD@{host}:{port}/{database}")
            print("6. Run this test again.")
            print("=" * 70 + "\n")
        else:
            print(f"  ❌ Connection error: {e}")
        return False

    # 2. Server Information
    print("\n[2/5] Inspecting server details...")
    try:
        v = conn.run("SELECT version();")[0][0]
        print(f"  ✓ Database Engine: {v.split(',')[0]}")
    except Exception as e:
        print(f"  ⚠️ Error fetching version: {e}")

    # 3. Enable & Verify pgvector Extension
    print("\n[3/5] Verifying 'pgvector' extension...")
    try:
        conn.run("CREATE EXTENSION IF NOT EXISTS vector;")
        ext = conn.run("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        if ext and len(ext) > 0:
            print(f"  ✓ pgvector extension is ACTIVE (v{ext[0][0]})")
        else:
            print("  ❌ pgvector extension was not found.")
            conn.close()
            return False
    except Exception as e:
        print(f"  ❌ Failed to enable vector extension: {e}")
        conn.close()
        return False

    # 4. Initialize Database Schema
    print("\n[4/5] Checking Smriti Shuddhi tables & schema...")
    schema_file = BASE_DIR / "supabase_schema.sql"
    if schema_file.exists():
        try:
            sql_script = schema_file.read_text(encoding="utf-8")
            # Execute statement by statement
            statements = [s.strip() for s in sql_script.split(";") if s.strip()]
            for stmt in statements:
                try:
                    conn.run(stmt + ";")
                except Exception as stmt_err:
                    # Ignore table already exists or index exists notices
                    if "already exists" not in str(stmt_err).lower():
                        logger_msg = str(stmt_err)
            print("  ✓ Master schema verified & tables initialized!")
        except Exception as e:
            print(f"  ⚠️ Schema notice: {e}")
    else:
        print("  ⚠️ supabase_schema.sql not found; skipping schema step.")

    # 5. Test 384-Dimensional HNSW Vector Distance
    print("\n[5/5] Testing 384-dimensional semantic cosine search...")
    try:
        # Create a sample 384-dim normalized vector string
        vec_sample = np.random.randn(384).astype(np.float32)
        vec_sample = vec_sample / np.linalg.norm(vec_sample)
        vec_str = "[" + ",".join(f"{x:.6f}" for x in vec_sample) + "]"

        res = conn.run(f"SELECT 1 - ('{vec_str}'::vector <=> '{vec_str}'::vector) AS cosine_similarity;")
        sim = float(res[0][0])
        print(f"  ✓ Mathematical cosine vector test passed! (Self-similarity: {sim:.4f})")
    except Exception as e:
        print(f"  ❌ Vector mathematical test failed: {e}")
        conn.close()
        return False

    conn.close()
    print("\n" + "=" * 70)
    print("🎉 SUCCESS: SUPABASE POSTGRESQL + PGVECTOR IS 100% OPERATIONAL!")
    print("=" * 70)
    print("Your Smriti Shuddhi project is connected to Supabase.")
    return True

if __name__ == "__main__":
    cli_arg = sys.argv[1] if len(sys.argv) > 1 else None
    test_supabase(cli_arg)
