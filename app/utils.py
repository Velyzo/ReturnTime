import re

def sanitize_domain_or_url(url):
    return re.sub(r'[^a-zA-Z0-9\.\-_]', '_', url)