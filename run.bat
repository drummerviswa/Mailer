@echo off
title Placement Lead Enricher Dashboard
echo ========================================================
echo  Starting Placement Lead Enricher Dashboard (3k+ Scale)
echo ========================================================
cd /d "%~dp0"
streamlit run app.py
pause
