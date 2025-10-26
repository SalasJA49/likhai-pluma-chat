import os
import re
import sys
from urllib.parse import urlparse

# Load simple key=value .env (ignores comments and blank lines). Does not print values.
def load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k,v=line.split('=',1)
            k=k.strip()
            v=v.strip().strip('"')
            os.environ.setdefault(k, v)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(HERE, '.env'))

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set in .env or environment')
    sys.exit(2)

try:
    import psycopg2
except Exception as e:
    print('psycopg2 not installed:', e)
    sys.exit(3)

try:
    # psycopg2 accepts the URL directly
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    cur = conn.cursor()
    cur.execute('SELECT version();')
    ver = cur.fetchone()
    print('OK: connected to database. version:', ver[0])
    cur.close()
    conn.close()
    sys.exit(0)
except Exception as e:
    print('ERROR: could not connect to database:', str(e))
    sys.exit(1)
