# Placement Lead Enricher & Outreach Engine

An intelligent lead enrichment and verification system engineered for placement teams and recruiters to enrich **3,000+ companies** with verified official email addresses, phone numbers, websites, and deliverability checks at scale.

---

## 🚀 Key Features

- **Automated Web & Domain Discovery**: Detects corporate domains and handles acronyms and subsidiary names.
- **Deep Contact Scraping**: Crawls homepage, `/contact`, `/about`, and `/careers` pages to discover contact details.
- **Smart Email Ranking**: Categorizes emails into:
  - 🥇 **Primary / Corporate Outreach**: `hr@`, `careers@`, `info@`, `contact@`, `placements@`
  - 🥈 **Alternative / Direct Inboxes**: Specific team or executive contacts
- **Deliverability & Verification**:
  - Validates email syntax and disposable domain filters.
  - Checks live DNS MX records and SMTP deliverability.
- **Resilient SQLite Checkpointing**:
  - WAL mode enabled for high concurrency.
  - Safely pause and resume runs at any time without losing progress or re-running completed companies.
- **Interactive Streamlit Dashboard**: Live real-time stats, interactive progress bars, table viewer, and export tools.
- **High-Performance CLI Batch Engine**: Multi-threaded parallel processing with customizable workers and batch sizes.

---

## 🛠️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/drummerviswa/Mailer.git
   cd Mailer
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🖥️ Usage

### 1. Interactive Streamlit Web UI
Launch the dashboard:
```bash
streamlit run app.py
```
Or double-click `run.bat` on Windows.

- **Upload**: Upload an Excel (`.xlsx`) or CSV (`.csv`) containing `CompanyName`, `Location`, and optional `RollNo`.
- **Enrich**: Adjust worker threads and click **▶️ Start / Resume Enrichment**.
- **Export**: Download results directly formatted for spreadsheets, or export a clean plain-text list of emails.

### 2. High-Throughput CLI Runner
For large batches (e.g., 3,000+ leads):
```bash
python cli.py --input companies.xlsx --workers 5 --batch-size 25
```

**CLI Options:**
- `--input`: Path to input `.xlsx` or `.csv` file (required).
- `--project`: Custom project name in the SQLite database.
- `--workers`: Number of parallel worker threads (default: `5`).
- `--batch-size`: Number of records to process per checkpoint transaction (default: `25`).
- `--output`: Custom output spreadsheet path (`.xlsx` or `.csv`).
- `--txt-output`: Output file for extracted emails only.

---

## 📂 Project Structure

```
Mailer/
├── app.py                # Streamlit web dashboard
├── cli.py                # CLI runner for high-volume batches
├── run.bat               # Windows quick-launch script
├── requirements.txt      # Project dependencies
├── enricher/             # Core enrichment engine
│   ├── db.py             # SQLite checkpointing & schema
│   ├── pipeline.py       # Multi-threaded worker orchestration
│   ├── scraper.py        # Website contact scraper & email ranker
│   ├── search.py         # Search engine domain discovery
│   ├── validator.py      # Email deliverability & MX verification
│   └── registry.py       # Corporate registry lookup fallbacks
└── tests/                # Pipeline verification tests
```
