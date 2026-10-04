import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db import get_pending_leads, update_lead, get_project_stats, DEFAULT_DB_PATH
from .search import discover_company_domain
from .scraper import scrape_website_pages, rank_emails, extract_phone_numbers
from .registry import lookup_mca_registry
from .validator import verify_email_deliverability

def enrich_single_company(company_name, location=""):
    """
    Executes the full enrichment pipeline for one company.
    Returns a dictionary of enriched attributes.
    """
    domain, snippets, candidate_urls = discover_company_domain(company_name, location)
    
    website_url = candidate_urls[0] if candidate_urls else None
    email = None
    email_tier = None
    phone = None
    alt_phone = None
    source = "Unknown"

    # Step 1: Try scraping official website if domain found
    if website_url:
        w_email, w_tier, w_phone, w_alt_phone, contact_url = scrape_website_pages(
            website_url, target_domain=domain
        )
        if w_email:
            email = w_email
            email_tier = w_tier
            source = f"Official Website ({contact_url})"
        if w_phone:
            phone = w_phone
            alt_phone = w_alt_phone

    # Step 2: If no email found on website, check snippets from search results
    if not email and snippets:
        s_email, s_tier = rank_emails(snippets, target_domain=domain)
        if s_email:
            email = s_email
            email_tier = s_tier
            source = "Web Search Index"
        if not phone:
            s_phones = extract_phone_numbers(" ".join(snippets))
            if s_phones:
                phone = s_phones[0]

    # Step 3: If still no email, query MCA / RoC corporate registry fallback
    if not email:
        reg_email, reg_phone = lookup_mca_registry(company_name, location)
        if reg_email:
            email = reg_email
            email_tier = "Corporate RoC Registry"
            source = "MCA/RoC Corporate Record"
        if not phone and reg_phone:
            phone = reg_phone

    # Step 4: Verify email deliverability
    deliv_info = verify_email_deliverability(email)

    return {
        "domain": domain or "",
        "website_url": website_url or "",
        "email": email or "",
        "email_tier": email_tier or "",
        "phone": phone or "",
        "alt_phone": alt_phone or "",
        "deliverability_status": deliv_info.get("deliverability_status", "UNKNOWN"),
        "mx_record": deliv_info.get("mx_record", ""),
        "source": source,
        "status": "COMPLETED" if email else "COMPLETED"
    }

def process_batch(project_id, max_workers=5, batch_size=20, db_path=None, stop_event=None, progress_callback=None):
    """
    Processes a batch of pending leads in parallel with thread-safe DB updates.
    """
    if not db_path:
        db_path = DEFAULT_DB_PATH
    leads = get_pending_leads(project_id, limit=batch_size, db_path=db_path)
    if not leads:
        return 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for lead in leads:
            if stop_event and stop_event.is_set():
                break
            f = executor.submit(enrich_single_company, lead["company_name"], lead["location"])
            futures[f] = lead

        for f in as_completed(futures):
            if stop_event and stop_event.is_set():
                break
            lead = futures[f]
            try:
                result = f.result()
                update_lead(lead["id"], result, db_path=db_path)
            except Exception as e:
                update_lead(lead["id"], {
                    "status": "FAILED",
                    "error_message": str(e)
                }, db_path=db_path)

            if progress_callback:
                progress_callback(lead["id"])

    return len(leads)
