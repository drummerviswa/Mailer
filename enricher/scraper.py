import re
import urllib3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# Indian Phone Regex: Mobile (+91/0 followed by 6-9 and 9 digits), Landlines (0xx-xxxxxxx), Toll-free (1800)
MOBILE_REGEX = re.compile(r'(?:(?:\+|0{0,2})91[\s\-]*)?([6-9]\d{4}[\s\-]*\d{5})\b')
LANDLINE_REGEX = re.compile(r'\b(0[1-9]{2,4}[\s\-]?[2-8]\d{6,7})\b')
TOLLFREE_REGEX = re.compile(r'\b(1800[\s\-]?[0-9]{3}[\s\-]?[0-9]{3,4})\b')

BAD_EMAIL_PREFIXES = (
    'example@', 'user@', 'email@', 'yourname@', 'sentry@', 'test@', 'admin@example',
    'support@wix', 'info@wix', 'domain@', 'name@', 'sample@', 'sales@jobrapido',
    'noreply@', 'no-reply@', 'donotreply@', 'privacy@', 'abuse@', 'security@',
    'mailer-daemon@', 'postmaster@'
)

BAD_EMAIL_DOMAINS = {
    'wixpress.com', 'sentry.io', 'cloudflare.com', 'wordpress.org', 'schema.org',
    'domain.com', 'example.com', 'yourcompany.com', 'bootstrapmade.com', 'themeforest.net'
}

def clean_email(email):
    if not email:
        return None
    email = email.lower().strip().strip(".,;:'\"()[]{}<>\\/?!")
    if " " in email or "\t" in email or "\n" in email or "\r" in email:
        return None
    if any(email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css', '.ico']):
        return None
    if any(email.startswith(bad) for bad in BAD_EMAIL_PREFIXES):
        return None
    if any(bad in email for bad in BAD_EMAIL_DOMAINS):
        return None
    if len(email) < 6 or '@' not in email or '.' not in email.split('@')[1]:
        return None
    return email

def clean_phone(raw_phone):
    """Normalizes Indian phone numbers into standard readable formats."""
    digits = re.sub(r'\D', '', raw_phone)
    if digits.startswith("91") and len(digits) == 12:
        return f"+91 {digits[2:7]} {digits[7:]}"
    elif len(digits) == 10 and digits[0] in "6789":
        return f"+91 {digits[:5]} {digits[5:]}"
    elif digits.startswith("1800"):
        return f"1800 {digits[4:7]} {digits[7:]}"
    elif len(digits) in (10, 11) and digits.startswith("0"):
        return f"{digits[:4]}-{digits[4:]}"
    elif len(digits) >= 10:
        return raw_phone.strip()
    return None

def extract_phone_numbers(text):
    """Extracts valid Indian phone numbers from text and removes duplicates."""
    if not text:
        return []
    
    found = []
    
    # 1. Toll-free
    for m in re.findall(r'\b1800[\s\-]?[0-9]{3}[\s\-]?[0-9]{3,4}\b', text):
        cp = clean_phone(m)
        if cp and cp not in found:
            found.append(cp)

    # 2. STD Code Landlines (e.g., +91-44-43978000 or 044-26357390)
    for m in re.finditer(r'(?:(?:\+|0{0,2})91[\s\-]*)?(?:0?[1-9]\d{1,3}[\s\-])[2-8]\d{6,7}\b', text):
        raw = m.group(0).strip()
        cp = clean_phone(raw)
        if cp and cp not in found:
            found.append(cp)

    # 3. Standard 10-digit Indian Mobile Numbers (+91 9876543210 or 9876543210)
    for m in re.finditer(r'(?:(?:\+|0{0,2})91[\s\-]*)?([6-9]\d{4}[\s\-]*\d{5})\b', text):
        raw = m.group(0).strip()
        cp = clean_phone(raw)
        if cp and cp not in found:
            found.append(cp)

    return found

def rank_emails(email_list, target_domain=None):
    """
    Ranks extracted emails by priority hierarchy. Extracts email addresses from text snippets.
    """
    raw_candidates = []
    for item in email_list:
        if not item:
            continue
        found = EMAIL_REGEX.findall(item)
        if found:
            raw_candidates.extend(found)
        elif "@" in item and " " not in item:
            raw_candidates.append(item)

    cleaned_set = set()
    for e in raw_candidates:
        c = clean_email(e)
        if c:
            cleaned_set.add(c)

    domain_clean = target_domain.replace("www.", "").lower() if target_domain else None

    tier1 = []
    tier2 = []
    tier3 = []
    tier4 = []
    tier5 = []
    tier6 = []

    for email in cleaned_set:
        try:
            user, dom = email.split('@', 1)
        except Exception:
            continue
        is_company_domain = domain_clean and (domain_clean in dom or dom in domain_clean)

        if is_company_domain:
            if any(k in user for k in ['career', 'hr', 'job', 'talent', 'recruit', 'hiring', 'apply']):
                tier1.append((email, "Careers/HR Domain"))
            elif any(k in user for k in ['info', 'contact', 'sales', 'hello', 'connect', 'enquiry', 'support', 'admin', 'office']):
                tier2.append((email, "General Contact Domain"))
            else:
                tier3.append((email, "Official Domain Officer"))
        else:
            if any(k in dom for k in ['gmail.com', 'yahoo.com', 'yahoo.co.in', 'outlook.com', 'hotmail.com']):
                tier6.append((email, "Public Registry Mailbox"))
            else:
                if any(k in user for k in ['career', 'hr', 'job', 'talent', 'recruit']):
                    tier4.append((email, "External HR"))
                elif any(k in user for k in ['info', 'contact', 'sales', 'support']):
                    tier5.append((email, "External Contact"))
                else:
                    tier6.append((email, "External Domain"))

    for t in [tier1, tier2, tier3, tier4, tier5, tier6]:
        if t:
            return t[0][0], t[0][1]

    return None, None

def scrape_website_pages(base_url, target_domain=None, timeout=6):
    """
    Inspects homepage and key contact/career pages on the company's website.
    Returns: (best_email, email_tier, primary_phone, alt_phone, contact_url)
    """
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    subpaths = ["", "/contact", "/contact-us", "/careers", "/about-us"]
    all_emails = []
    all_phones = []
    contact_url = base_url

    for path in subpaths:
        page_url = urljoin(base_url, path)
        try:
            resp = requests.get(page_url, headers=headers, verify=False, timeout=timeout)
            if resp.status_code == 200:
                text = resp.text
                soup = BeautifulSoup(text, "html.parser")
                
                # Extract mailto links
                for a in soup.select("a[href^='mailto:']"):
                    raw = a["href"].replace("mailto:", "").split("?")[0]
                    all_emails.append(raw)
                    
                # Extract tel links
                for a in soup.select("a[href^='tel:']"):
                    raw = a["href"].replace("tel:", "").split("?")[0]
                    all_phones.append(raw)

                # Regex scan full visible text
                page_text = soup.get_text(separator=" ")
                all_emails.extend(EMAIL_REGEX.findall(text))
                all_phones.extend(extract_phone_numbers(page_text))

                if path in ["/contact", "/contact-us"] and (all_emails or all_phones):
                    contact_url = page_url

                # If Tier 1 HR email found, we can stop scraping extra subpages early
                best_email, tier = rank_emails(all_emails, target_domain)
                if tier == "Careers/HR Domain":
                    break
        except Exception:
            pass

    best_email, email_tier = rank_emails(all_emails, target_domain)
    
    # Filter and dedup phones
    cleaned_phones = []
    for p in all_phones:
        cp = clean_phone(p)
        if cp and cp not in cleaned_phones:
            cleaned_phones.append(cp)

    phone = cleaned_phones[0] if len(cleaned_phones) > 0 else None
    alt_phone = cleaned_phones[1] if len(cleaned_phones) > 1 else None

    return best_email, email_tier, phone, alt_phone, contact_url
