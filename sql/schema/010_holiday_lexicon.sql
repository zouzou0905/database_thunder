CREATE TABLE IF NOT EXISTS holiday_events (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name_cn TEXT NOT NULL,
    name_en TEXT NOT NULL DEFAULT '',
    marketplace TEXT NOT NULL DEFAULT 'UK',
    trend_start_month SMALLINT NOT NULL CHECK (trend_start_month BETWEEN 1 AND 12),
    trend_end_month SMALLINT NOT NULL CHECK (trend_end_month BETWEEN 1 AND 12),
    min_growth_rate NUMERIC(8, 4) NOT NULL DEFAULT 0.2,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS holiday_terms (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES holiday_events(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    term_normalized TEXT NOT NULL,
    match_type TEXT NOT NULL DEFAULT 'word' CHECK (match_type IN ('word', 'phrase')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, term_normalized)
);

CREATE INDEX IF NOT EXISTS idx_holiday_events_active
    ON holiday_events (is_active, marketplace, code);

CREATE INDEX IF NOT EXISTS idx_holiday_terms_event
    ON holiday_terms (event_id, is_active, term_normalized);

INSERT INTO holiday_events (
    code, name_cn, name_en, marketplace, trend_start_month, trend_end_month, min_growth_rate
)
VALUES
    ('halloween', '万圣节', 'Halloween', 'UK', 8, 10, 0.2),
    ('christmas', '圣诞节', 'Christmas', 'UK', 10, 12, 0.2)
ON CONFLICT (code) DO NOTHING;

INSERT INTO holiday_terms (event_id, term, term_normalized, match_type)
SELECT e.id, term, lower(term), CASE WHEN position(' ' in term) > 0 THEN 'phrase' ELSE 'word' END
FROM holiday_events e
CROSS JOIN (
    VALUES
        ('Halloween'), ('Trick or treat'), ('costume'), ('cosplay'), ('dress up'),
        ('witch'), ('witches'), ('wiches'), ('Ghost'), ('Vampire'), ('Zombie'),
        ('Skeleton'), ('Warlock'), ('Pumpkin'), ('Bat'), ('Black Cat'), ('Spider'),
        ('Spider Web'), ('Tombstone'), ('Skull'), ('Cobweb'), ('Bones'), ('Blood'),
        ('Broomstick')
) AS terms(term)
WHERE e.code = 'halloween'
ON CONFLICT (event_id, term_normalized) DO NOTHING;

INSERT INTO holiday_terms (event_id, term, term_normalized, match_type)
SELECT e.id, term, lower(term), CASE WHEN position(' ' in term) > 0 THEN 'phrase' ELSE 'word' END
FROM holiday_events e
CROSS JOIN (
    VALUES
        ('christmas'), ('Reindeer'), ('Grinch'), ('Grinches'), ('Santa Claus'),
        ('Santa'), ('Santa Hat'), ('Elf'), ('Advent Calendar'), ('Stocking'),
        ('Stocking Stuffer'), ('Gingerbread'), ('Gingerbread Man'), ('Candy Cane'),
        ('Snowflake'), ('Sleigh')
) AS terms(term)
WHERE e.code = 'christmas'
ON CONFLICT (event_id, term_normalized) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keyword_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON holiday_events TO keyword_user;
        GRANT SELECT, INSERT, UPDATE, DELETE ON holiday_terms TO keyword_user;
        GRANT USAGE, SELECT ON SEQUENCE holiday_events_id_seq TO keyword_user;
        GRANT USAGE, SELECT ON SEQUENCE holiday_terms_id_seq TO keyword_user;
    END IF;
END $$;
