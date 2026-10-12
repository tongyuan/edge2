CREATE TABLE IF NOT EXISTS instruments (
    symbol TEXT PRIMARY KEY,
    asset_class TEXT NULL CHECK (
        asset_class IS NULL OR asset_class IN (
            'EQUITY', 'ETF', 'INDEX', 'CRYPTO', 'COMMODITY', 'FX'
        )
    ),
    sector TEXT NULL CHECK (
        sector IS NULL OR sector IN (
            'Communication Services',
            'Consumer Discretionary',
            'Consumer Staples',
            'Energy',
            'Financials',
            'Health Care',
            'Industrials',
            'Materials',
            'Real Estate',
            'Technology',
            'Utilities'
        )
    ),
    industry TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT instruments_industry_requires_sector CHECK (
        industry IS NULL OR sector IS NOT NULL
    ),
    CONSTRAINT instruments_industry_matches_sector CHECK (
        industry IS NULL OR
        (sector = 'Communication Services' AND industry IN (
            'Diversified Telecommunication Services', 'Entertainment',
            'Interactive Media & Services', 'Media',
            'Wireless Telecommunication Services'
        )) OR
        (sector = 'Consumer Discretionary' AND industry IN (
            'Automobiles', 'Broadline Retail',
            'Consumer Discretionary Distribution & Retail',
            'Hotels, Restaurants & Leisure', 'Household Durables',
            'Leisure Products', 'Textiles, Apparel & Luxury Goods'
        )) OR
        (sector = 'Consumer Staples' AND industry IN (
            'Beverages', 'Consumer Staples Distribution & Retail',
            'Food Products', 'Household Products',
            'Personal Care Products', 'Tobacco'
        )) OR
        (sector = 'Energy' AND industry IN (
            'Energy Equipment & Services', 'Oil & Gas'
        )) OR
        (sector = 'Financials' AND industry IN (
            'Banks', 'Capital Markets', 'Consumer Finance',
            'Digital Asset Treasury', 'Financial Services', 'Insurance',
            'Mortgage REITs'
        )) OR
        (sector = 'Health Care' AND industry IN (
            'Biotechnology', 'Health Care Equipment & Supplies',
            'Health Care Providers & Services', 'Health Care Technology',
            'Life Sciences Tools & Services', 'Managed Health Care',
            'Pharmaceuticals'
        )) OR
        (sector = 'Industrials' AND industry IN (
            'Aerospace & Defense', 'Building Products',
            'Commercial Services & Supplies', 'Construction & Engineering',
            'Electrical Equipment', 'Ground Transportation',
            'Industrial Conglomerates', 'Machinery', 'Passenger Airlines',
            'Professional Services', 'Trading Companies & Distributors'
        )) OR
        (sector = 'Materials' AND industry IN (
            'Chemicals', 'Construction Materials', 'Containers & Packaging',
            'Metals & Mining', 'Paper & Forest Products'
        )) OR
        (sector = 'Real Estate' AND industry IN (
            'Equity REITs', 'Real Estate Management & Development'
        )) OR
        (sector = 'Technology' AND industry IN (
            'Communications Equipment', 'Consumer Electronics',
            'Electronic Equipment, Instruments & Components', 'IT Services',
            'Semiconductors', 'Software',
            'Technology Hardware, Storage & Peripherals'
        )) OR
        (sector = 'Utilities' AND industry IN (
            'Electric Utilities', 'Gas Utilities',
            'Independent Power and Renewable Electricity Producers',
            'Multi-Utilities', 'Water Utilities'
        ))
    ),
    CONSTRAINT instruments_non_equity_has_no_corporate_taxonomy CHECK (
        COALESCE(asset_class = 'EQUITY', FALSE)
        OR (sector IS NULL AND industry IS NULL)
    )
);

INSERT INTO instruments (symbol)
SELECT DISTINCT symbol
FROM observations
ON CONFLICT (symbol) DO NOTHING;
