CREATE ROLE app WITH LOGIN PASSWORD 'app' NOSUPERUSER NOBYPASSRLS CREATEDB NOCREATEROLE;
ALTER ROLE app SET lock_timeout = '3s';
ALTER ROLE app SET statement_timeout = '10s';
ALTER ROLE app SET idle_in_transaction_session_timeout = '30s';
CREATE DATABASE ecommerce OWNER app;
