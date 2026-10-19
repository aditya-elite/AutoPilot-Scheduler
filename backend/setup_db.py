import psycopg2
import os

def run_setup():
    db_name = "autopilot_scheduler"
    schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "schema.sql"))
    
    # 1. Connect to default 'postgres' database to create the new database
    print("Connecting to PostgreSQL default database...")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "postgres")
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")

    conn = psycopg2.connect(
        dbname="postgres",
        user=user,
        password=password,
        host=host,
        port=port
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    # Check if database already exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    exists = cur.fetchone()
    
    if not exists:
        print(f"Creating database '{db_name}'...")
        cur.execute(f"CREATE DATABASE {db_name}")
        print(f"Database '{db_name}' created successfully.")
    else:
        print(f"Database '{db_name}' already exists.")
        
    cur.close()
    conn.close()
    
    # 2. Connect to the new database and apply the schema
    print(f"Connecting to '{db_name}' to apply schema...")
    conn = psycopg2.connect(
        dbname=db_name,
        user=user,
        password=password,
        host=host,
        port=port
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    print(f"Reading schema from: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    print("Executing schema SQL queries...")
    cur.execute(schema_sql)
    print("Schema applied successfully!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    try:
        run_setup()
    except Exception as e:
        print(f"Error occurred: {e}")
