from dotenv import load_dotenv

from app.api import create_app

load_dotenv()

app = create_app()
