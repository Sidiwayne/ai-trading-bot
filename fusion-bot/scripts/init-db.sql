-- ══════════════════════════════════════════════════════════════════════════════
-- FusionBot Database Initialization
-- ══════════════════════════════════════════════════════════════════════════════
-- Creates separate databases for each environment
-- Tables are created by SQLAlchemy ORM on first run

-- Create databases for each environment
CREATE DATABASE fusionbot_dry_run;
CREATE DATABASE fusionbot_testnet;
CREATE DATABASE fusionbot_prod;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE fusionbot_dry_run TO fusionbot;
GRANT ALL PRIVILEGES ON DATABASE fusionbot_testnet TO fusionbot;
GRANT ALL PRIVILEGES ON DATABASE fusionbot_prod TO fusionbot;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'FusionBot databases initialized successfully';
    RAISE NOTICE '  - fusionbot_dry_run (paper trading - 100% simulated)';
    RAISE NOTICE '  - fusionbot_testnet (real API, fake money)';
    RAISE NOTICE '  - fusionbot_prod (live trading - REAL MONEY)';
END $$;

