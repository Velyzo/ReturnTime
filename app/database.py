import os
import sqlite3
import logging
from .utils import sanitize_domain_or_url
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../web_archives'))
MAIN_DB_PATH = os.path.join(BASE_DIR, 'main_sitemap.db')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def init_main_db():
    logging.debug(f"Initializing main database: {MAIN_DB_PATH}")
    try:
        with sqlite3.connect(MAIN_DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS archives (
                domain_or_url TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                uuid TEXT NOT NULL UNIQUE,
                files TEXT NOT NULL
            )''')

            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON archives (timestamp)')
        logger.info("Main database initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error initializing main database: {e}")

def save_to_main_db(domain_or_url, timestamp, uuid, files):
    logging.debug(f"Saving to main database: {domain_or_url}")
    try:
        with sqlite3.connect(MAIN_DB_PATH) as conn:
            conn.execute('''INSERT OR REPLACE INTO archives (domain_or_url, timestamp, uuid, files)
                            VALUES (?, ?, ?, ?)''', (domain_or_url, timestamp, uuid, files))
        logger.info(f"Data for {domain_or_url} saved to main database.")
    except sqlite3.Error as e:
        logger.error(f"Error saving data to main database: {e}")

def init_domain_db(domain_or_url):
    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')
    logging.debug(f"Initializing domain-specific database: {domain_db_path}")
    try:
        with sqlite3.connect(domain_db_path) as conn:

            conn.execute('''CREATE TABLE IF NOT EXISTS archives (
                url TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                uuid TEXT NOT NULL PRIMARY KEY
            )''')

            conn.execute('''CREATE TABLE IF NOT EXISTS resources (
                resource_url TEXT NOT NULL,
                resource_path TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                uuid TEXT NOT NULL PRIMARY KEY
            )''')

            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp_archive ON archives (timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_resource_timestamp ON resources (timestamp)')
        logger.info(f"Domain-specific database {domain_db_path} initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error initializing domain database {domain_db_path}: {e}")
    return domain_db_path

def save_webpage(domain_or_url, url, content, timestamp, uuid):
    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')
    try:
        with sqlite3.connect(domain_db_path) as conn:
            conn.execute('''INSERT OR REPLACE INTO archives (url, content, timestamp, uuid)
                            VALUES (?, ?, ?, ?)''', (url, content, timestamp, uuid))
        logger.info(f"Webpage {url} saved successfully in domain database.")
    except sqlite3.Error as e:
        logger.error(f"Error saving webpage {url}: {e}")

def save_resource(domain_or_url, resource_url, resource_path, timestamp, uuid):
    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')
    try:
        with sqlite3.connect(domain_db_path) as conn:
            conn.execute('''INSERT OR REPLACE INTO resources (resource_url, resource_path, timestamp, uuid)
                            VALUES (?, ?, ?, ?)''', (resource_url, resource_path, timestamp, uuid))
        logger.info(f"Resource {resource_url} saved successfully in domain database.")
    except sqlite3.Error as e:
        logger.error(f"Error saving resource {resource_url}: {e}")

def get_archives_by_timestamp(domain_or_url, start_date, end_date):
    """
    Retrieve archives from the main database by a given date range.
    """
    logging.debug(f"Fetching archives from {domain_or_url} between {start_date} and {end_date}")
    try:
        with sqlite3.connect(MAIN_DB_PATH) as conn:
            query = '''
                SELECT domain_or_url, timestamp, uuid, files
                FROM archives
                WHERE domain_or_url = ? AND timestamp BETWEEN ? AND ?
            '''
            cursor = conn.execute(query, (domain_or_url, start_date, end_date))
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error fetching archives by timestamp: {e}")
        return []

def get_current_timestamp():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
