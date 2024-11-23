import os
import uuid
import requests
from flask import Flask, request, render_template_string, jsonify, send_from_directory, render_template
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import sqlite3
import re
import logging

def sanitize_domain(domain):
    return re.sub(r'[^a-zA-Z0-9\.\-]', '_', domain)

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'web_archives'))
os.makedirs(BASE_DIR, exist_ok=True)

MAIN_DB_PATH = os.path.join(BASE_DIR, 'main_sitemap.db')

def sanitize_domain_or_url(url):
    """Sanitize URLs for use as filenames."""
    return re.sub(r'[^a-zA-Z0-9\.\-_]', '_', url)

def init_main_db():
    logging.debug(f"Initializing main database: {MAIN_DB_PATH}")
    conn = sqlite3.connect(MAIN_DB_PATH)
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS archives (
            domain_or_url TEXT PRIMARY KEY,
            timestamp TEXT,
            uuid TEXT,
            files TEXT
        )''')

def save_to_main_db(domain_or_url, timestamp, uuid, files):
    logging.debug(f"Saving to main database: {domain_or_url}")
    conn = sqlite3.connect(MAIN_DB_PATH)
    with conn:
        conn.execute('''INSERT INTO archives (domain_or_url, timestamp, uuid, files)
                        VALUES (?, ?, ?, ?)''', (domain_or_url, timestamp, uuid, files))

def init_domain_db(domain_or_url):
    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')
    logging.debug(f"Initializing domain-specific database: {domain_db_path}")
    conn = sqlite3.connect(domain_db_path)
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS archives (
            url TEXT,
            content TEXT,
            timestamp TEXT,
            uuid TEXT,
            PRIMARY KEY (uuid)  -- Use UUID as the primary key instead of URL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS resources (
            resource_url TEXT,
            resource_path TEXT,
            timestamp TEXT,
            uuid TEXT
        )''')
    return domain_db_path


def save_webpage(domain_or_url, url, content, timestamp, uuid):
    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')
    
    conn = sqlite3.connect(domain_db_path)
    c = conn.cursor()
    
    c.execute('SELECT * FROM archives WHERE url = ? AND timestamp = ?', (url, timestamp))
    existing_entry = c.fetchone()

    if existing_entry:
        logging.debug(f"Page already archived with the same URL and timestamp. Skipping insert.")
        return
    
    with conn:
        conn.execute('''INSERT INTO archives (url, content, timestamp, uuid)
                        VALUES (?, ?, ?, ?)''', (url, content, timestamp, uuid))
    logging.debug(f"Page saved to database: {url} at {timestamp}")


def save_resource(domain_or_url, resource_url, resource_content, timestamp, uuid):
    sanitized = sanitize_domain_or_url(domain_or_url)
    resource_folder = os.path.join(BASE_DIR, sanitized, uuid)
    os.makedirs(resource_folder, exist_ok=True)
    resource_path = os.path.join(resource_folder, os.path.basename(urlparse(resource_url).path))
    
    with open(resource_path, 'wb') as file:
        file.write(resource_content)
    
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')
    conn = sqlite3.connect(domain_db_path)
    with conn:
        conn.execute('''INSERT INTO resources (resource_url, resource_path, timestamp, uuid)
                        VALUES (?, ?, ?, ?)''', (resource_url, resource_path, timestamp, uuid))

def fetch_and_store_page(domain, url, base_url, visited_urls):
    if url in visited_urls:
        return

    visited_urls.add(url)
    logging.debug(f"Fetching URL: {url}")

    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch page: {url} - Status {response.status_code}")
        return

    page_uuid = str(uuid.uuid4())
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    soup = BeautifulSoup(response.text, 'html.parser')

    resource_folder = os.path.join(BASE_DIR, sanitize_domain(domain), page_uuid)
    os.makedirs(resource_folder, exist_ok=True)

    for tag in soup.find_all(['link', 'script', 'img']):
        resource_url = None
        if tag.name == 'link' and tag.get('rel') == ['stylesheet']:
            resource_url = tag.get('href')
        elif tag.name == 'script' and tag.get('src'):
            resource_url = tag.get('src')
        elif tag.name == 'img' and tag.get('src'):
            resource_url = tag.get('src')

        if resource_url:
            full_resource_url = urljoin(base_url, resource_url)
            try:
                res = requests.get(full_resource_url)
                if res.status_code == 200:
                    resource_filename = os.path.basename(urlparse(full_resource_url).path)
                    resource_path = os.path.join(resource_folder, resource_filename)

                    with open(resource_path, 'wb') as file:
                        file.write(res.content)

                    if tag.name == 'link' or tag.name == 'script':
                        tag['href' if tag.name == 'link' else 'src'] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{resource_filename}"
                    elif tag.name == 'img':
                        tag['src'] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{resource_filename}"
            except Exception as e:
                logging.error(f"Failed to fetch resource: {full_resource_url} - {e}")

    save_webpage(domain, url, soup.prettify(), timestamp, page_uuid)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/archive', methods=['POST'])
def archive():
    url = request.form['url']
    domain_or_url = url
    sanitized = sanitize_domain_or_url(domain_or_url)

    init_domain_db(sanitized)
    visited_urls = set()
    fetch_and_store_page(domain_or_url, url, url, visited_urls)

    return jsonify({
        "message": f"Website {url} successfully archived!",
        "archived_urls": list(visited_urls)
    })

@app.route('/view', methods=['GET'])
def view_page():
    domain_or_url = request.args.get('url') or request.args.get('domain')
    
    if not domain_or_url:
        logging.error("No URL provided for viewing archives.")
        return jsonify({"error": "Full URL is required"}), 400

    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')

    if not os.path.exists(domain_db_path):
        logging.error(f"No database found for URL: {domain_or_url}")
        return jsonify({"error": f"No entries found for URL: {domain_or_url}"}), 404

    conn = sqlite3.connect(domain_db_path)
    c = conn.cursor()
    c.execute('SELECT url, timestamp, uuid FROM archives ORDER BY timestamp DESC')
    entries = c.fetchall()
    conn.close()

    if entries:
        logging.info(f"Found {len(entries)} archived pages for URL: {domain_or_url}")
        return render_template('view_history.html', domain_or_url=domain_or_url, entries=entries)
    else:
        logging.info(f"No archived pages found for URL: {domain_or_url}")
        return jsonify({"message": f"No archived pages found for URL: {domain_or_url}"}), 404


@app.route('/resources/<domain>/<uuid>/<path:filename>')  
def serve_resource(domain, uuid, filename):
    resource_folder = os.path.join(BASE_DIR, domain, uuid)
    return send_from_directory(resource_folder, filename)


@app.route('/version', methods=['GET'])
def view_version():
    uuid = request.args.get('uuid')
    domain_or_url = request.args.get('url')
    if not domain_or_url:
        logging.error("URL not provided for viewing a specific version.")
        return jsonify({"error": "URL is required"}), 400

    sanitized = sanitize_domain_or_url(domain_or_url)
    domain_db_path = os.path.join(BASE_DIR, f'{sanitized}.db')

    if not os.path.exists(domain_db_path):
        logging.error(f"No database found for URL: {domain_or_url}")
        return jsonify({"error": f"No entries found for URL: {domain_or_url}"}), 404

    conn = sqlite3.connect(domain_db_path)
    c = conn.cursor()

    c.execute('SELECT url, content, timestamp, uuid FROM archives WHERE uuid = ?', (uuid,))
    entry = c.fetchone()
    conn.close()

    if entry:
        url, content, timestamp, uuid = entry
        logging.info(f"Found version for URL: {domain_or_url} | UUID: {uuid} | Archived On: {timestamp}")
        response = f"<h1>Version of Archived Page for URL: {domain_or_url}</h1>"
        response += f"<p>URL: <a href='{url}'>{url}</a> | Archived On: {timestamp}</p>"
        response += f"<div>{content}</div>"
        return response
    else:
        logging.info(f"No version found for UUID: {uuid}")
        return jsonify({"message": f"No archived version found for UUID: {uuid}"}), 404


if __name__ == '__main__':
    init_main_db()
    app.run(debug=True)
