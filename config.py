"""Application configuration and platform-provided inputs."""

import base64
import json
import os
from datetime import timedelta, timezone


def _load_dotenv(path=".env"):
    """Load simple KEY=VALUE entries without overwriting environment values."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("DHAN_CLIENT_ID", "{{CLIENT_ID}}")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
BASE_URL = "https://api.dhan.co/v2"
IST = timezone(timedelta(hours=5, minutes=30))

_raw_inputs = "{{DHAN_INPUTS}}"
if _raw_inputs and not _raw_inputs.startswith("{{"):
    DASHBOARD_INPUTS = json.loads(base64.b64decode(_raw_inputs).decode())
else:
    DASHBOARD_INPUTS = {}

SIMULATION = DASHBOARD_INPUTS.get("simulation", True)
NIFTY_ID = 13
SENSEX_ID = 51

INSTRUMENT_MASTER_SOURCE = (
    "https://images.dhan.co/api-data/api-scrip-master.csv"
)
INSTRUMENT_MASTER_VERIFIED_AT = "2026-11-05"

# Verified against the official Dhan master as NSE,E,EQUITY rows on the date above.
NIFTY50_INSTRUMENTS = {
    "ADANIENT": (25, "Adani Enterprises"),
    "ADANIPORTS": (15083, "Adani Ports"),
    "APOLLOHOSP": (157, "Apollo Hospitals"),
    "ASIANPAINT": (236, "Asian Paints"),
    "AXISBANK": (5900, "Axis Bank"),
    "BSE": (19585, "BSE"),
    "BAJAJ-AUTO": (16669, "Bajaj Auto"),
    "BAJFINANCE": (317, "Bajaj Finance"),
    "BAJAJFINSV": (16675, "Bajaj Finserv"),
    "BEL": (383, "Bharat Electronics"),
    "BHARTIARTL": (10604, "Bharti Airtel"),
    "CIPLA": (694, "Cipla"),
    "COALINDIA": (20374, "Coal India"),
    "DRREDDY": (881, "Dr Reddy's Laboratories"),
    "EICHERMOT": (910, "Eicher Motors"),
    "ETERNAL": (5097, "Eternal"),
    "GRASIM": (1232, "Grasim Industries"),
    "HCLTECH": (7229, "HCL Technologies"),
    "HDFCBANK": (1333, "HDFC Bank"),
    "HDFCLIFE": (467, "HDFC Life"),
    "HINDALCO": (1363, "Hindalco"),
    "HINDUNILVR": (1394, "Hindustan Unilever"),
    "ICICIBANK": (4963, "ICICI Bank"),
    "ITC": (1660, "ITC"),
    "INFY": (1594, "Infosys"),
    "INDIGO": (11195, "InterGlobe Aviation"),
    "JSWSTEEL": (11723, "JSW Steel"),
    "JIOFIN": (18143, "Jio Financial Services"),
    "KOTAKBANK": (1922, "Kotak Mahindra Bank"),
    "LT": (11483, "Larsen & Toubro"),
    "M&M": (2031, "Mahindra & Mahindra"),
    "MARUTI": (10999, "Maruti Suzuki"),
    "MAXHEALTH": (22377, "Max Healthcare"),
    "NTPC": (11630, "NTPC"),
    "NESTLEIND": (17963, "Nestle India"),
    "ONGC": (2475, "ONGC"),
    "POWERGRID": (14977, "Power Grid"),
    "RELIANCE": (2885, "Reliance Industries"),
    "SBILIFE": (21808, "SBI Life"),
    "SHRIRAMFIN": (4306, "Shriram Finance"),
    "SBIN": (3045, "State Bank of India"),
    "SUNPHARMA": (3351, "Sun Pharma"),
    "TCS": (11536, "TCS"),
    "TATACONSUM": (3432, "Tata Consumer"),
    "TMPV": (3456, "Tata Motors Passenger Vehicles"),
    "TATASTEEL": (3499, "Tata Steel"),
    "TECHM": (13538, "Tech Mahindra"),
    "TITAN": (3506, "Titan Company"),
    "TRENT": (1964, "Trent"),
    "ULTRACEMCO": (11532, "UltraTech Cement"),
}
NIFTY50_NAMES = {
    symbol: name for symbol, (_security_id, name) in NIFTY50_INSTRUMENTS.items()
}
NIFTY50_SECURITY_IDS = {
    symbol: security_id
    for symbol, (security_id, _name) in NIFTY50_INSTRUMENTS.items()
}
NIFTY50_SYMBOLS = list(NIFTY50_INSTRUMENTS)
NIFTY50_IDS = list(NIFTY50_SECURITY_IDS.values())
VERIFIED_STOCK_COUNT = len(NIFTY50_IDS)
EXCLUDED_STOCKS = {}
