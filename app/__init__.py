import os
import logging
from flask import Flask
from .web import routes
from .database import init_main_db

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../web_archives'))
os.makedirs(BASE_DIR, exist_ok=True)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.register_blueprint(routes)
    try:
        init_main_db()
        logger.info("Main database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize the main database: {e}")
        raise

    return app