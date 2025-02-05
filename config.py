import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///users.db")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
OPENFOODFACTS_API_URL = "https://world.openfoodfacts.org/api/v0/product/"
