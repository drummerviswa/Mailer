import os
import sys
import argparse
import time
import pandas as pd
from enricher.db import (
    init_db,
    create_or_get_project,
    import_records,
    get_project_stats,
    export_dataframe,
    DEFAULT_DB_PATH
)
from enricher.pipeline import process_batch

def main():
    parser = argparse.ArgumentParser(description="Placement Lead Enricher - CLI Batch Engine (3k+ Scale)")
    parser.add_argument("--input", required=True, help="Path to input Excel (.xlsx) or CSV (.csv) file")
    parser.add_argument("--project", default=None, help="Project name in database (default: input file name)")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel worker threads (default: 5)")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch chunk size (default: 25)")
    parser.add_argument("--output", default=None, help="Output Excel/CSV path")
    parser.add_argument("--txt-output", default=None, help="Output plain text emails path")
    
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)

    init_db()

    project_name = args.project or os.path.splitext(os.path.basename(input_path))[0]
    print(f"\n==========================================")
    print(f"🚀 Placement Lead Enricher - CLI Engine")
    print(f"📁 Input File: {input_path}")
    print(f"🏷️  Project Name: {project_name}")
    print(f"⚡ Workers: {args.workers} | Batch Size: {args.batch_size}")
    print(f"==========================================\n")

    # Load input file
    if input_path.endswith(".csv"):
        df = pd.read_csv(input_path)
    else:
        df = pd.read_excel(input_path)

    cols = df.columns.tolist()
    col_comp = "CompanyName" if "CompanyName" in cols else ("Company Name" if "Company Name" in cols else cols[0])
    col_loc = "Location" if "Location" in cols else ""
    col_roll = "RollNo" if "RollNo" in cols else ("Roll No" if "Roll No" in cols else "")

    print(f"Found {len(df)} total rows.")
    print(f"Mapped Columns -> Company: '{col_comp}', Location: '{col_loc or 'None'}', RollNo: '{col_roll or 'None'}'")

    project_id = create_or_get_project(project_name, len(df))
    stats = get_project_stats(project_id)

    if stats["total"] == 0:
        print(f"Importing {len(df)} records into SQLite checkpoint database...")
        records = []
        for _, row in df.iterrows():
            records.append({
                "company_name": str(row[col_comp]),
                "location": str(row[col_loc]) if col_loc else "",
                "roll_no": str(row[col_roll]) if col_roll else ""
            })
        import_records(project_id, records)
        stats = get_project_stats(project_id)

    print(f"Initial Checkpoint -> Total: {stats['total']}, Completed: {stats['completed']}, Pending: {stats['pending']}\n")

    # Start loop
    start_time = time.time()
    while True:
        stats = get_project_stats(project_id)
        pending = stats["pending"]
        completed = stats["completed"]
        total = stats["total"]

        if pending == 0:
            print("\n🎉 All records completed successfully!")
            break

        pct = (completed / total * 100) if total > 0 else 0
        elapsed = time.time() - start_time
        rate = (completed / elapsed) * 60 if elapsed > 0 else 0
        print(f"[{completed}/{total}] ({pct:.1f}%) | Pending: {pending} | Speed: {rate:.1f} leads/min | Active Chunk: {args.batch_size}...")

        processed = process_batch(
            project_id=project_id,
            max_workers=args.workers,
            batch_size=args.batch_size
        )

        if processed == 0:
            break

    # Final export
    df_export = export_dataframe(project_id)
    output_path = args.output or f"{project_name}_enriched.xlsx"
    txt_path = args.txt_output or f"{project_name}_emails_only.txt"

    if output_path.endswith(".csv"):
        df_export.to_csv(output_path, index=False)
    else:
        df_export.to_excel(output_path, index=False, engine="openpyxl")

    with open(txt_path, "w", encoding="utf-8") as f:
        for mail in df_export["Mail"]:
            f.write((str(mail).strip() if pd.notna(mail) else "") + "\n")

    print(f"\n==========================================")
    print(f"✅ Enrichment Complete!")
    print(f"📊 Enriched Spreadsheet: {output_path}")
    print(f"📋 Emails Column: {txt_path}")
    print(f"==========================================\n")

if __name__ == "__main__":
    main()
