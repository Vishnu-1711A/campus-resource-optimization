@echo off
title Campus Resource Optimization System - PES University
echo =====================================================================
echo    CAMPUS RESOURCE OPTIMIZATION SYSTEM (PES UNIVERSITY DBMS)
echo    Students: Battu Rohith (PES2UG24CS264) ^& Prateek Sharma (PES2UG24CS283)
echo =====================================================================
echo.
echo Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python.
    pause
    exit /b
)

echo Starting Campus Resource Optimization System...
python run.py
pause
