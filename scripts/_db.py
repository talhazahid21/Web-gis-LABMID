import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import psycopg2

import config


def connect(dbname=None):
    cfg = dict(config.DB)
    if dbname:
        cfg["dbname"] = dbname
    try:
        return psycopg2.connect(**cfg)
    except psycopg2.OperationalError as e:
        sys.exit(f"Cannot connect to PostgreSQL ({cfg['host']}:{cfg['port']}, user {cfg['user']}).\n"
                 f"Check that PostgreSQL is running and the password in .env is right.\n{e}")
