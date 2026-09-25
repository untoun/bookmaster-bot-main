import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_ID", "").split(",")
    if uid.strip().isdigit()
]

# Loyalty program settings
LOYALTY_EVERY_N: int = 5          # every Nth visit gives discount
LOYALTY_DISCOUNT_PERCENT: int = 20  # discount percentage
