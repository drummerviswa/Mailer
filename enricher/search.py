import re
import time
import base64
import random
import urllib3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
]

EXCLUDED_DOMAINS = {
    'zaubacorp.com', 'tofler.in', 'indiamart.com', 'justdial.com', 'linkedin.com',
    'facebook.com', 'instagram.com', 'youtube.com', 'twitter.com', 'x.com',
    'glassdoor.com', 'glassdoor.co.in', 'ambitionbox.com', 'naukri.com', 'indeed.com',
    'instahyre.com', 'zoominfo.com', 'crunchbase.com', 'leadstal.com', 'signalhire.com',
    'dnb.com', 'rocketreach.co', 'lusha.com', 'thecompanycheck.com', 'quickcompany.in',
    'economictimes.indiatimes.com', 'wikipedia.org', 'mapsofindia.com', 'jobrapido.com',
    'instafinancials.com', 'fundoodata.com', 'tradeindia.com', 'sulekha.com', 'quora.com',
    'google.com', 'bing.com', 'duckduckgo.com', 'yahoo.com'
}

def clean_company_name(name):
    """Strips corporate suffixes to find the fundamental brand name."""
    cleaned = re.sub(
        r'\b(Private Limited|Pvt Ltd|Pvt\. Ltd\.|P\. Ltd\.|Limited|Ltd|LLP|Inc\.|LLC|Corporation|Corp)\b',
        '', name, flags=re.IGNORECASE
    ).strip()
    cleaned = re.sub(r'[\(\)\[\]\{\}]', '', cleaned)
    return " ".join(cleaned.split())

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1"
    }

def decode_bing_url(bing_href):
    """Decodes Bing redirect URL containing base64 target."""
    try:
        parsed = urlparse(bing_href)
        qs = parse_qs(parsed.query)
        if 'u' in qs:
            u_param = qs['u'][0]
            # Bing uses prefix 'a1' before base64 string
            if u_param.startswith("a1"):
                b64 = u_param[2:]
                # Fix padding
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                return base64.b64decode(b64).decode('utf-8', errors='ignore')
    except Exception:
        pass
    return bing_href

def search_yahoo(query, timeout=6):
    """Searches Yahoo and returns (snippets, urls). Highly reliable for Indian corporate data."""
    try:
        url = "https://search.yahoo.com/search"
        resp = requests.get(
            url,
            params={"p": query},
            headers=get_headers(),
            verify=False,
            timeout=timeout
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = [div.text.strip() for div in soup.select("div.compText")]
            urls = []
            for a in soup.select("h3.title a"):
                href = a.get("href", "")
                if href and "r.search.yahoo.com" in href and "/RU=" in href:
                    # Parse real URL from Yahoo redirect
                    try:
                        real = href.split("/RU=")[1].split("/RK=")[0]
                        href = unquote(real)
                    except Exception:
                        pass
                if href.startswith("http"):
                    urls.append(href)
            return snippets, urls
    except Exception:
        pass
    return [], []

def search_bing(query, timeout=6):
    """Searches Bing and returns (snippets, urls)."""
    try:
        url = "https://www.bing.com/search"
        resp = requests.get(
            url,
            params={"q": query},
            headers=get_headers(),
            verify=False,
            timeout=timeout
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = [p.text.strip() for p in soup.select("li.b_algo div.b_caption p, li.b_algo p")]
            urls = []
            for a in soup.select("li.b_algo h2 a"):
                raw_href = a.get("href", "")
                if "bing.com/ck/a" in raw_href:
                    decoded = decode_bing_url(raw_href)
                    if decoded.startswith("http"):
                        urls.append(decoded)
                elif raw_href.startswith("http"):
                    urls.append(raw_href)
            return snippets, urls
    except Exception:
        pass
    return [], []

def discover_company_domain(company_name, location=""):
    """
    Finds the official domain name and candidate URLs for a given company.
    Returns: (primary_domain, list_of_snippets, list_of_urls)
    """
    core_name = clean_company_name(company_name)
    queries = [
        f'"{company_name}" contact email',
        f'{core_name} {location} official website contact'
    ]

    all_snippets = []
    discovered_domains = []
    discovered_urls = []

    for q in queries:
        # 1. Query Yahoo first (fastest and cleanest contact snippets)
        snippets, urls = search_yahoo(q)
        all_snippets.extend(snippets)

        # 2. Query Bing
        if not urls:
            b_snippets, b_urls = search_bing(q)
            all_snippets.extend(b_snippets)
            urls.extend(b_urls)

        for u in urls:
            parsed = urlparse(u)
            dom = parsed.netloc.replace("www.", "").lower()
            if dom and dom not in EXCLUDED_DOMAINS and "." in dom:
                if dom not in discovered_domains:
                    discovered_domains.append(dom)
                    discovered_urls.append(f"{parsed.scheme}://{parsed.netloc}")

        if discovered_domains:
            break
        time.sleep(random.uniform(0.2, 0.5))

    primary_domain = discovered_domains[0] if discovered_domains else None
    return primary_domain, all_snippets, discovered_urls
