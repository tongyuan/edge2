CREATE INDEX IF NOT EXISTS idx_observations_symbol_latest
    ON observations (symbol, observed_at DESC, received_at DESC, id DESC)
    INCLUDE (observation_price, ipda_20w_high, ipda_20w_low);
