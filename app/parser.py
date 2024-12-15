import os
import uuid
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse, unquote
from .database import save_webpage, save_resource
from .utils import sanitize_domain_or_url as sanitize_domain

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../web_archives'))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

MAX_RETRIES = 3
TIMEOUT = 15


def initialize_selenium():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    return driver


def fetch_and_store_page(domain, url, base_url, visited_urls):
    if url in visited_urls:
        logger.debug(f"Skipping already visited URL: {url}")
        return

    visited_urls.add(url)

    driver = initialize_selenium()

    try:
        driver.get(url)
        driver.implicitly_wait(10)
        page_html = driver.page_source

        page_uuid = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        soup = BeautifulSoup(page_html, 'html.parser')

        for tag in soup.find_all(['link', 'script', 'img', 'iframe', 'audio', 'video', 'source', 'font']):
            resolve_and_decode_links(tag, base_url)

        resource_folder = os.path.join(BASE_DIR, sanitize_domain(domain), page_uuid)
        os.makedirs(resource_folder, exist_ok=True)

        for tag in soup.find_all(['link', 'script', 'img', 'iframe', 'audio', 'video', 'source', 'font']):
            process_resource(tag, base_url, resource_folder, domain, page_uuid, timestamp)

        update_local_links(soup, domain, page_uuid)

        save_webpage(domain, url, soup.prettify(), timestamp, page_uuid)
        logger.info(f"Page {url} archived successfully!")

        for tag in soup.find_all('a', href=True):
            link = tag['href']
            full_url = urljoin(url, link)
            parsed_url = urlparse(full_url)

            if parsed_url.netloc == domain and full_url not in visited_urls:
                fetch_and_store_page(domain, full_url, base_url, visited_urls)

    except Exception as e:
        logger.error(f"Error processing page {url}: {str(e)}")
    finally:
        driver.quit()


def update_local_links(soup, domain, page_uuid):
    for tag in soup.find_all(['link', 'script', 'img', 'iframe', 'audio', 'video', 'source', 'font']):
        attr = 'href' if tag.name == 'link' else 'src'
        if tag.get(attr):
            tag[attr] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{os.path.basename(tag[attr])}"


def process_resource(tag, base_url, resource_folder, domain, page_uuid, timestamp):
    resource_url = None
    resource_type = None

    if tag.name == 'link':
        resource_url = tag.get('href')
        if 'stylesheet' in tag.get('rel', []):
            resource_type = 'stylesheet'
        elif 'icon' in tag.get('rel', []):
            resource_type = 'icon'
        elif 'preload' in tag.get('rel', []):
            resource_type = 'preload'
        elif 'manifest' in tag.get('rel', []):
            resource_type = 'manifest'

    elif tag.name == 'script' and tag.get('src'):
        resource_url = tag.get('src')
        resource_type = 'script'
    elif tag.name == 'img' and tag.get('src'):
        resource_url = tag.get('src')
        resource_type = 'image'
    elif tag.name == 'audio' and tag.get('src'):
        resource_url = tag.get('src')
        resource_type = 'audio'
    elif tag.name == 'video' and tag.get('src'):
        resource_url = tag.get('src')
        resource_type = 'video'
    elif tag.name == 'source' and tag.get('src'):
        resource_url = tag.get('src')
        resource_type = 'media'
    elif tag.name == 'font' and tag.get('src'):
        resource_url = tag.get('src')
        resource_type = 'font'

    if not resource_url:
        return

    full_resource_url = urljoin(base_url, resource_url)

    for _ in range(MAX_RETRIES):
        try:
            res = requests.get(full_resource_url, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code == 200:
                resource_filename = generate_unique_filename(full_resource_url)
                resource_path = os.path.join(resource_folder, resource_filename)

                if os.path.exists(resource_path):
                    logger.debug(f"Resource already exists: {full_resource_url}")
                    return

                with open(resource_path, 'wb') as file:
                    file.write(res.content)

                if tag.name == 'link' or tag.name == 'script':
                    tag['href' if tag.name == 'link' else 'src'] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{resource_filename}"
                elif tag.name in ['img', 'audio', 'video', 'source', 'font']:
                    tag['src'] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{resource_filename}"

                save_resource(domain, full_resource_url, resource_path, timestamp, page_uuid)
                logger.debug(f"Resource {full_resource_url} archived successfully!")
                break
            else:
                logger.error(f"Failed to fetch resource: {full_resource_url} - Status {res.status_code}")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch resource: {full_resource_url} - {str(e)}")


def generate_unique_filename(resource_url):
    resource_name = os.path.basename(urlparse(resource_url).path)
    if not resource_name:
        resource_name = str(uuid.uuid4())
    return unquote(resource_name)


def resolve_and_decode_links(tag, base_url):
    if tag.name in ['link', 'script', 'img', 'iframe', 'audio', 'video', 'source', 'font']:
        attr = 'href' if tag.name == 'link' else 'src'
        if tag.get(attr):
            tag[attr] = unquote(urljoin(base_url, tag[attr]))
