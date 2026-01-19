@echo off
REM FEC SaaS Database Setup Script for Windows
REM This script creates all required databases

echo Creating FEC SaaS databases...
echo.

REM Set PostgreSQL connection details
SET PGHOST=localhost
SET PGPORT=5432
SET PGUSER=postgres

REM Prompt for password
SET /P PGPASSWORD=Enter PostgreSQL password for user postgres:

echo.
echo Creating databases...

REM Create each database (ignore errors if already exists)
psql -c "CREATE DATABASE auth_db;" 2>nul
psql -c "CREATE DATABASE notification_db;" 2>nul
psql -c "CREATE DATABASE venue_db;" 2>nul
psql -c "CREATE DATABASE booking_db;" 2>nul
psql -c "CREATE DATABASE customer_db;" 2>nul
psql -c "CREATE DATABASE inventory_db;" 2>nul
psql -c "CREATE DATABASE pos_db;" 2>nul
psql -c "CREATE DATABASE loyalty_db;" 2>nul
psql -c "CREATE DATABASE analytics_db;" 2>nul

echo.
echo Listing created databases:
psql -c "SELECT datname FROM pg_database WHERE datname LIKE '%%_db' ORDER BY datname;"

echo.
echo Database setup complete!
pause
