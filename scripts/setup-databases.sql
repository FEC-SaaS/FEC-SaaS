-- FEC SaaS Database Setup Script
-- Run this in pgAdmin, DBeaver, or psql to create all required databases

-- Create databases for each microservice
CREATE DATABASE auth_db;
CREATE DATABASE notification_db;
CREATE DATABASE venue_db;
CREATE DATABASE booking_db;
CREATE DATABASE customer_db;
CREATE DATABASE inventory_db;
CREATE DATABASE pos_db;
CREATE DATABASE loyalty_db;
CREATE DATABASE analytics_db;

-- Optional: Create a dedicated application user
-- Uncomment and modify the password as needed
-- CREATE USER fec_app WITH PASSWORD 'your_secure_password_here';

-- Grant privileges to the application user (if created)
-- GRANT ALL PRIVILEGES ON DATABASE auth_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE notification_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE venue_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE booking_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE customer_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE inventory_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE pos_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE loyalty_db TO fec_app;
-- GRANT ALL PRIVILEGES ON DATABASE analytics_db TO fec_app;

-- Verify databases were created
SELECT datname FROM pg_database WHERE datname LIKE '%_db' ORDER BY datname;
