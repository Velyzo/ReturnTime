import os
from flask import Flask, Blueprint, request, jsonify, render_template, send_from_directory
from .database import init_main_db, init_domain_db
from .parser import fetch_and_store_page
from .utils import sanitize_domain_or_url
import logging
import sqlite3

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../web_archives'))

app = Flask(__name__)

routes = Blueprint('routes', __name__)

@app.route('/')
def index():
    return render_template('main/index.html')

@app.route('/about')
def about():
    return render_template('about/index.html')

@app.route('/report')
def report():
    return render_template('report/index.html')

@app.route('/top-domains')
def top_domains():
    return render_template('top_domains/index.html')

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
    domain_db_path = os.path.normpath(os.path.join(BASE_DIR, f'{sanitized}.db'))

    if not domain_db_path.startswith(BASE_DIR):
        logging.error(f"Attempted access to a path outside the base directory: {domain_db_path}")
        return jsonify({"error": "Invalid path"}), 400

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
        return render_template('dyn_history/index.html', domain_or_url=domain_or_url, entries=entries)
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
    domain_db_path = os.path.normpath(os.path.join(BASE_DIR, f'{sanitized}.db'))
    if not domain_db_path.startswith(BASE_DIR):
        logging.error(f"Attempted access to a path outside the base directory: {domain_db_path}")
        return jsonify({"error": "Invalid path"}), 400

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
        response = content
        return response
    else:
        logging.info(f"No version found for UUID: {uuid}")
        return jsonify({"message": f"No archived version found for UUID: {uuid}"}), 404

def create_app():
    init_main_db()
    app.register_blueprint(routes)
    return app