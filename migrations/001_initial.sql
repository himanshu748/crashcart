CREATE TABLE IF NOT EXISTS fixtures (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  owned INTEGER NOT NULL CHECK(owned = 1),
  environment TEXT NOT NULL CHECK(environment = 'sandbox'),
  amount INTEGER NOT NULL CHECK(amount = 2900),
  currency TEXT NOT NULL CHECK(currency = 'USD')
);
INSERT OR IGNORE INTO fixtures VALUES ('workshop-v1', 'Workshop ticket', 1, 'sandbox', 2900, 'USD');
CREATE TABLE IF NOT EXISTS invariant_versions (
  version TEXT PRIMARY KEY,
  body_json TEXT NOT NULL CHECK(json_valid(body_json))
);
INSERT OR IGNORE INTO invariant_versions VALUES ('ticket-v1', '{"version":"ticket-v1","amount":2900,"currency":"USD","ticket_count":1,"recovery_seconds":60}');
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  promise TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('LOCAL_TEST','LIVE_SANDBOX','RECORDED_REPLAY','FRESH_SANDBOX')),
  fixture_id TEXT NOT NULL REFERENCES fixtures(id),
  invariant_version TEXT NOT NULL REFERENCES invariant_versions(version),
  fault_json TEXT NOT NULL CHECK(json_valid(fault_json)),
  invariant_json TEXT NOT NULL CHECK(json_valid(invariant_json)),
  budget_json TEXT NOT NULL CHECK(json_valid(budget_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1))
);
CREATE TABLE IF NOT EXISTS purchases (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
  order_id TEXT UNIQUE,
  amount INTEGER NOT NULL CHECK(amount = 2900),
  currency TEXT NOT NULL CHECK(currency = 'USD'),
  payment_state TEXT NOT NULL DEFAULT 'UNPAID',
  capture_id TEXT UNIQUE,
  capture_completed_at TEXT,
  payment_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(payment_confirmed IN (0,1)),
  confirmation_json TEXT CHECK(confirmation_json IS NULL OR json_valid(confirmation_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK(payment_confirmed = 0 OR (payment_state = 'COMPLETED' AND capture_id IS NOT NULL AND capture_completed_at IS NOT NULL AND confirmation_json IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  ordinal INTEGER NOT NULL CHECK(ordinal > 0),
  kind TEXT NOT NULL,
  state TEXT NOT NULL,
  input_json TEXT NOT NULL CHECK(json_valid(input_json)),
  result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
  created_at TEXT NOT NULL,
  finished_at TEXT,
  UNIQUE(run_id, ordinal)
);
CREATE TABLE IF NOT EXISTS operations (
  id TEXT PRIMARY KEY,
  purchase_id TEXT NOT NULL REFERENCES purchases(id),
  semantic_key TEXT NOT NULL,
  request_id TEXT NOT NULL UNIQUE,
  body_json TEXT NOT NULL CHECK(json_valid(body_json)),
  state TEXT NOT NULL DEFAULT 'INTENDED',
  response_json TEXT CHECK(response_json IS NULL OR json_valid(response_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(purchase_id, semantic_key)
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  purchase_id TEXT REFERENCES purchases(id),
  order_id TEXT,
  operation_id TEXT REFERENCES operations(id),
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_time TEXT,
  observed_at TEXT NOT NULL,
  caused_by TEXT REFERENCES events(id),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, observed_at);
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY,
  purchase_id TEXT NOT NULL UNIQUE REFERENCES purchases(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_refs (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  kind TEXT NOT NULL,
  path TEXT NOT NULL UNIQUE,
  sha256 TEXT NOT NULL,
  mode TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(run_id, path)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  kind TEXT NOT NULL,
  semantic_key TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  state TEXT NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','RUNNING','COMPLETED','FAILED','CANCELLED')),
  available_at REAL NOT NULL,
  lease_until REAL,
  owner TEXT,
  fence_token INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(run_id, semantic_key)
);
CREATE TABLE IF NOT EXISTS webhooks (
  event_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(id),
  verified INTEGER NOT NULL CHECK(verified = 1),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  received_at TEXT NOT NULL,
  processed_at TEXT
);
CREATE TRIGGER IF NOT EXISTS operations_identity_immutable
BEFORE UPDATE OF purchase_id, semantic_key, request_id, body_json ON operations
BEGIN SELECT RAISE(ABORT, 'payment operation identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS run_contract_immutable
BEFORE UPDATE OF fixture_id, invariant_version, fault_json, invariant_json, mode ON runs
BEGIN SELECT RAISE(ABORT, 'run contract is immutable'); END;
CREATE TRIGGER IF NOT EXISTS purchase_identity_immutable
BEFORE UPDATE OF run_id, amount, currency ON purchases
BEGIN SELECT RAISE(ABORT, 'purchase identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS order_identity_immutable
BEFORE UPDATE OF order_id ON purchases WHEN OLD.order_id IS NOT NULL AND NEW.order_id IS NOT OLD.order_id
BEGIN SELECT RAISE(ABORT, 'order identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS capture_identity_immutable
BEFORE UPDATE OF capture_id ON purchases WHEN OLD.capture_id IS NOT NULL AND NEW.capture_id IS NOT OLD.capture_id
BEGIN SELECT RAISE(ABORT, 'capture identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS ticket_requires_confirmation
BEFORE INSERT ON tickets WHEN NOT EXISTS (
  SELECT 1 FROM purchases WHERE id = NEW.purchase_id AND payment_confirmed = 1 AND payment_state = 'COMPLETED'
)
BEGIN SELECT RAISE(ABORT, 'ticket requires independently confirmed payment'); END;
CREATE TRIGGER IF NOT EXISTS evidence_mode_matches_run
BEFORE INSERT ON evidence_refs WHEN NEW.mode != (SELECT mode FROM runs WHERE id = NEW.run_id)
BEGIN SELECT RAISE(ABORT, 'evidence mode does not match run'); END;
CREATE TRIGGER IF NOT EXISTS events_namespace
BEFORE INSERT ON events WHEN
  (NEW.purchase_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM purchases WHERE id = NEW.purchase_id AND run_id = NEW.run_id)) OR
  (NEW.order_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM purchases WHERE order_id = NEW.order_id AND run_id = NEW.run_id)) OR
  (NEW.operation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM operations o JOIN purchases p ON p.id = o.purchase_id WHERE o.id = NEW.operation_id AND p.run_id = NEW.run_id)) OR
  (NEW.caused_by IS NOT NULL AND NOT EXISTS(SELECT 1 FROM events WHERE id = NEW.caused_by AND run_id = NEW.run_id))
BEGIN SELECT RAISE(ABORT, 'event identity crosses run namespace'); END;
PRAGMA user_version = 1;
