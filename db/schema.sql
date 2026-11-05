CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL CONSTRAINT users_email_key UNIQUE,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    locality TEXT NOT NULL,
    favorite_station_id TEXT NOT NULL,
    health_profile TEXT NOT NULL,
    notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    role TEXT NOT NULL DEFAULT 'citizen',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_invites (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expires_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS admin_invites_expiry_idx ON admin_invites(expires_at);
