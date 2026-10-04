import os
import io
import time
import pandas as pd
import streamlit as st
from enricher.db import (
    init_db,
    create_or_get_project,
    import_records,
    get_project_stats,
    export_dataframe,
    get_connection,
    DEFAULT_DB_PATH
)
from enricher.pipeline import process_batch

# Set page layout
st.set_page_config(
    page_title="Placement Lead Enricher (3k+ Scale)",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_db()

# Custom styles
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #0d6efd;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stProgress > div > div > div > div {
        background-color: #28a745;
    }
    .badge-success { background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-warning { background-color: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-info { background-color: #d1ecf1; color: #0c5460; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🎓 Placement Lead Enricher & Outreach Engine")
st.caption("Engineered for Placement Teams to enrich 3,000+ companies with verified Emails, Phone Numbers, Websites & Deliverability checks.")

# Sidebar - Project & Configuration
st.sidebar.header("📁 Project Management")

conn = get_connection()
projects_df = pd.read_sql_query("SELECT id, name, total_records FROM projects ORDER BY id DESC", conn)
conn.close()

project_names = projects_df["name"].tolist() if not projects_df.empty else []
selected_project = st.sidebar.selectbox(
    "Select Existing Project",
    ["-- Create New Project --"] + project_names
)

if selected_project == "-- Create New Project --":
    new_proj_name = st.sidebar.text_input("New Project Name", value=f"Placement_Batch_{int(time.time())}")
    project_id = None
else:
    project_id = int(projects_df[projects_df["name"] == selected_project]["id"].iloc[0])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Worker Settings")
max_workers = st.sidebar.slider("Parallel Threads (Workers)", min_value=1, max_value=12, value=5, help="Number of concurrent web lookups")
batch_chunk = st.sidebar.slider("Batch Size per Cycle", min_value=10, max_value=50, value=25)

# Session state for controlling continuous processing
if "is_running" not in st.session_state:
    st.session_state["is_running"] = False

# Main Tab Structure
tab_upload, tab_monitor, tab_export = st.tabs(["📤 1. Upload & Setup", "⚡ 2. Live Enrichment Monitor", "💾 3. Export Center"])

with tab_upload:
    st.subheader("Upload Company Dataset (.xlsx or .csv)")
    uploaded_file = st.file_uploader("Upload spreadsheet containing Company Names & Locations", type=["xlsx", "xls", "csv"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
            
            st.success(f"Successfully read `{uploaded_file.name}` ({len(df_upload)} total rows).")
            
            st.markdown("#### Map Spreadsheet Columns")
            cols = df_upload.columns.tolist()
            
            c1, c2, c3 = st.columns(3)
            with c1:
                col_comp = st.selectbox(
                    "Company Name Column", cols,
                    index=cols.index("CompanyName") if "CompanyName" in cols else (cols.index("Company Name") if "Company Name" in cols else 0)
                )
            with c2:
                col_loc = st.selectbox(
                    "Location Column (Optional)", ["None"] + cols,
                    index=(cols.index("Location") + 1) if "Location" in cols else 0
                )
            with c3:
                col_roll = st.selectbox(
                    "Roll No / ID Column (Optional)", ["None"] + cols,
                    index=(cols.index("RollNo") + 1) if "RollNo" in cols else (cols.index("Roll No") + 1 if "Roll No" in cols else 0)
                )

            st.write("Preview of Uploaded Data:")
            st.dataframe(df_upload.head(5), use_container_width=True)

            if st.button("🚀 Import and Initialize Records into Database", type="primary"):
                target_name = new_proj_name if selected_project == "-- Create New Project --" else selected_project
                proj_id = create_or_get_project(target_name, len(df_upload))
                
                records = []
                for _, row in df_upload.iterrows():
                    records.append({
                        "company_name": str(row[col_comp]),
                        "location": str(row[col_loc]) if col_loc != "None" else "",
                        "roll_no": str(row[col_roll]) if col_roll != "None" else ""
                    })

                import_records(proj_id, records)
                st.success(f"Imported {len(records)} companies into project `{target_name}`! Switch to the 'Live Enrichment Monitor' tab to start processing.")
                st.rerun()

        except Exception as e:
            st.error(f"Error reading file: {e}")

with tab_monitor:
    st.subheader("Live Processing & Checkpoint Monitor")

    if not project_id:
        st.warning("Please select or create a project from the sidebar, or import records in Tab 1.")
    else:
        stats = get_project_stats(project_id)
        total = stats.get("total", 0)
        completed = stats.get("completed", 0)
        pending = stats.get("pending", 0)
        with_email = stats.get("with_email", 0)
        with_phone = stats.get("with_phone", 0)
        deliverable = stats.get("deliverable", 0)

        # Progress bar
        pct = (completed / total) if total > 0 else 0
        st.progress(pct, text=f"Progress: {completed} / {total} companies completed ({pct*100:.1f}%)")

        # Metric cards
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Companies", total)
        m2.metric("Completed", completed)
        m3.metric("Pending Remaining", pending)
        m4.metric("Emails Found", f"{with_email} ({(with_email/completed*100 if completed>0 else 0):.0f}%)")
        m5.metric("Phone Numbers", f"{with_phone} ({(with_phone/completed*100 if completed>0 else 0):.0f}%)")

        st.markdown("---")

        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 4])
        with ctrl1:
            if st.button("▶️ Start / Resume Enrichment", type="primary", disabled=st.session_state["is_running"] or pending == 0):
                st.session_state["is_running"] = True
                st.rerun()

        with ctrl2:
            if st.button("⏸️ Pause Processing", disabled=not st.session_state["is_running"]):
                st.session_state["is_running"] = False
                st.info("Pausing enrichment. Progress is safely saved in SQLite checkpoint.")
                st.rerun()

        # Processing loop execution
        if st.session_state["is_running"] and pending > 0:
            status_box = st.empty()
            status_box.info(f"⏳ Active Workers running... Processing next chunk of {batch_chunk} companies.")
            
            processed = process_batch(
                project_id=project_id,
                max_workers=max_workers,
                batch_size=batch_chunk
            )
            
            if processed > 0:
                time.sleep(0.5)
                st.rerun()
            else:
                st.session_state["is_running"] = False
                status_box.success("🎉 All companies in this batch have been completely processed!")
                st.rerun()

        st.markdown("#### Live Leads Data Feed")
        df_display = export_dataframe(project_id)
        if not df_display.empty:
            st.dataframe(df_display.head(100), use_container_width=True)
        else:
            st.info("No records loaded yet.")

with tab_export:
    st.subheader("Export Results for Google Sheets & Master Database")

    if not project_id:
        st.warning("Please select a project to export data.")
    else:
        df_export = export_dataframe(project_id)
        total_rows = len(df_export)
        st.write(f"Exporting **{total_rows}** companies for project.")

        col_ex1, col_ex2, col_ex3 = st.columns(3)

        with col_ex1:
            st.markdown("##### 📥 Complete Excel Workbook")
            st.caption("Contains all enriched attributes (Mail, Phone, Website, Deliverability, Source).")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name="Enriched_Leads")
            st.download_button(
                label="Download Enriched Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"enriched_placement_leads_{project_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col_ex2:
            st.markdown("##### 📋 Emails-Only Column (.txt)")
            st.caption("Exact row order matching your sheet — ready for 1-click paste into Google Sheets.")
            emails_txt = "\n".join([str(e) if pd.notna(e) and str(e).strip() != "" else "" for e in df_export["Mail"]])
            st.download_button(
                label="Download Emails Only (.txt)",
                data=emails_txt,
                file_name=f"emails_only_col_{project_id}.txt",
                mime="text/plain"
            )

        with col_ex3:
            st.markdown("##### 📊 Full CSV Dataset")
            st.caption("Standard CSV format for importing into central databases or CRM systems.")
            csv_data = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Full CSV (.csv)",
                data=csv_data,
                file_name=f"enriched_placement_leads_{project_id}.csv",
                mime="text/csv"
            )
