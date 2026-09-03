CREATE TABLE IF NOT EXISTS saved_symbol_groups (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL CHECK (
        char_length(btrim(name)) BETWEEN 1 AND 80
    ),
    member_symbols TEXT[] NOT NULL CHECK (
        cardinality(member_symbols) BETWEEN 1 AND 100
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_symbol_groups_name
    ON saved_symbol_groups (lower(name));
