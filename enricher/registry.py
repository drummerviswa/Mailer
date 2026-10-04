import re
import urllib3
from .scraper import EMAIL_REGEX, extract_phone_numbers, clean_email, clean_phone
from .search import search_yahoo, search_bing

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def lookup_mca_registry(company_name, location=""):
    """
    Looks up public corporate filing records (RoC/MCA registered entity details)
    via search engines to discover verified registered emails, director details, and corporate telephone.
    """
    search_query = f'"{company_name}" ZaubaCorp OR Tofler email contact'
    
    snippets, _ = search_yahoo(search_query)
    if not snippets:
        snippets, _ = search_bing(search_query)

    emails = []
    phones = []

    full_text = " ".join(snippets)

    # Extract emails from corporate summaries
    found_emails = EMAIL_REGEX.findall(full_text)
    for e in found_emails:
        c = clean_email(e)
        if c and not any(bad in c for bad in ['zaubacorp.com', 'tofler.in', 'thecompanycheck.com']):
            if c not in emails:
                emails.append(c)

    # Extract phone numbers
    found_phones = extract_phone_numbers(full_text)
    for p in found_phones:
        cp = clean_phone(p)
        if cp and cp not in phones:
            phones.append(cp)

    primary_email = emails[0] if emails else None
    primary_phone = phones[0] if phones else None

    return primary_email, primary_phone
