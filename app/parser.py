import os
import uuid
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
from .database import save_webpage, save_resource
from .utils import sanitize_domain_or_url as sanitize_domain

ALLOWED_DOMAINS = ["example.com", "another-allowed-domain.com"]

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../web_archives'))

def fetch_and_store_page(domain, url, base_url, visited_urls):
    if url in visited_urls:
        logger.debug(f"Skipping already visited URL: {url}")
        return

    visited_urls.add(url)
    
    try:
        if not is_url_allowed(url):
            logger.error(f"URL not allowed: {url}")
            return

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to fetch page: {url} - Status {response.status_code}")
            return

        page_uuid = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        soup = BeautifulSoup(response.text, 'html.parser')

        resource_folder = os.path.join(BASE_DIR, sanitize_domain(domain), page_uuid)
        os.makedirs(resource_folder, exist_ok=True)

        for tag in soup.find_all(['link', 'script', 'img']):
            process_resource(tag, base_url, resource_folder, domain, page_uuid, timestamp)

        save_webpage(domain, url, soup.prettify(), timestamp, page_uuid)
        logger.info(f"Page {url} archived successfully!")

    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing page {url}: {str(e)}")

def process_resource(tag, base_url, resource_folder, domain, page_uuid, timestamp):
    """Fetch and store resources like CSS, JS, and images."""
    resource_url = None
    if tag.name == 'link' and tag.get('rel') == ['stylesheet']:
        resource_url = tag.get('href')
    elif tag.name == 'script' and tag.get('src'):
        resource_url = tag.get('src')
    elif tag.name == 'img' and tag.get('src'):
        resource_url = tag.get('src')

    if not resource_url:
        return

    full_resource_url = urljoin(base_url, resource_url)
    
    try:
        if not is_url_allowed(full_resource_url):
            logger.error(f"Resource URL not allowed: {full_resource_url}")
            return

        res = requests.get(full_resource_url, timeout=10)
        if res.status_code == 200:
            resource_filename = generate_unique_filename(full_resource_url)
            resource_path = os.path.join(resource_folder, resource_filename)

            with open(resource_path, 'wb') as file:
                file.write(res.content)

            if tag.name == 'link' or tag.name == 'script':
                tag['href' if tag.name == 'link' else 'src'] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{resource_filename}"
            elif tag.name == 'img':
                tag['src'] = f"/resources/{sanitize_domain(domain)}/{page_uuid}/{resource_filename}"

            save_resource(domain, full_resource_url, resource_path, timestamp, page_uuid)
            logger.debug(f"Resource {full_resource_url} archived successfully!")
        else:
            logger.error(f"Failed to fetch resource: {full_resource_url} - Status {res.status_code}")

    except requests.RequestException as e:
        logger.error(f"Failed to fetch resource: {full_resource_url} - {str(e)}")

def is_url_allowed(url):
    """Check if the URL is within the allowed domains."""
    parsed_url = urlparse(url)
    return any(parsed_url.netloc.endswith(domain) for domain in ALLOWED_DOMAINS)

def generate_unique_filename(resource_url):
    """Generate a unique filename for the resource to avoid overwriting."""
    resource_name = os.path.basename(urlparse(resource_url).path)
    if not resource_name:
        resource_name = str(uuid.uuid4())
    return resource_name