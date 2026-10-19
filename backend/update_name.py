import os
import psycopg2

def update():
    db_url = os.getenv("DATABASE_URL", "postgresql://autopilot:autopilot@localhost:5432/autopilot_scheduler")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("UPDATE users SET full_name = 'Factory Manager' WHERE username = 'manager';")
    print("Database updated: Full name set to 'Factory Manager' for username 'manager'.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    update()
