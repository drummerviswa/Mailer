import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from enricher.db import init_db, create_or_get_project, import_records, get_project_stats, export_dataframe
from enricher.pipeline import process_batch

def test_pipeline():
    test_db = os.path.join(os.path.dirname(__file__), "test_leads.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    print("1. Initializing DB...")
    init_db(test_db)

    print("2. Creating Test Project...")
    proj_id = create_or_get_project("Test_Sample", 3, db_path=test_db)

    sample_companies = [
        {"company_name": "FLUIDTHERM TECHNOLOGY PRIVATE LIMITED", "location": "Tamil Nadu", "roll_no": "TEST01"},
        {"company_name": "TENSORHUB TECHNOLOGIES PRIVATE LIMITED", "location": "Tamil Nadu", "roll_no": "TEST02"},
        {"company_name": "VOLTECH MANUFACTURING COMPANY PRIVATE LIMITED", "location": "Tamil Nadu", "roll_no": "TEST03"}
    ]

    print("3. Importing Records...")
    import_records(proj_id, sample_companies, db_path=test_db)

    stats = get_project_stats(proj_id, db_path=test_db)
    print(f"Imported: Total={stats['total']}, Pending={stats['pending']}")
    assert stats["total"] == 3
    assert stats["pending"] == 3

    print("4. Running Batch Enrichment Worker Pool (max_workers=2)...")
    processed = process_batch(proj_id, max_workers=2, batch_size=3, db_path=test_db)
    print(f"Processed count: {processed}")

    stats_after = get_project_stats(proj_id, db_path=test_db)
    print(f"Post-enrichment: Completed={stats_after['completed']}, With Email={stats_after['with_email']}, With Phone={stats_after['with_phone']}, Deliverable={stats_after['deliverable']}")
    assert stats_after["completed"] == 3

    print("5. Testing Data Export...")
    df = export_dataframe(proj_id, db_path=test_db)
    for _, row in df.iterrows():
        print(f"Company: {row['Company Name']} | Email: {row['Mail']} | Phone: {row['Phone Number']} | Status: {row['Deliverability Status']}")

    print("\n[SUCCESS] All Enrichment Pipeline tests passed successfully!")

    if os.path.exists(test_db):
        os.remove(test_db)

if __name__ == "__main__":
    test_pipeline()
