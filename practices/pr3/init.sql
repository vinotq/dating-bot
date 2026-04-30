CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    age         INTEGER NOT NULL,
    bio         TEXT NOT NULL,
    updated_at  TIMESTAMP DEFAULT NOW()
);

INSERT INTO profiles (id, name, age, bio)
SELECT g, 'user_' || g, 18 + (g % 50), 'bio of user ' || g
FROM generate_series(1, 1000) g
ON CONFLICT (id) DO NOTHING;
