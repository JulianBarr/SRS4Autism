-- HHS (Heep Hong Society) goals catalog for daily scheduler / FSRS.
-- Applied automatically when running backend.database.db.init_db() (create_all).
-- For existing deployments, run this once against data/content_db/srs4autism.db

CREATE TABLE IF NOT EXISTS hhs_goals (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    quest_id VARCHAR NOT NULL UNIQUE,
    goal_iri VARCHAR NOT NULL UNIQUE,
    content_source VARCHAR NOT NULL DEFAULT 'HHS',
    domain_file VARCHAR NOT NULL,
    label TEXT NOT NULL,
    module_label VARCHAR NOT NULL,
    submodule_label VARCHAR,
    objective_label VARCHAR,
    phasal_label VARCHAR,
    breadcrumb_json TEXT,
    goal_code VARCHAR,
    age_group VARCHAR,
    materials_json TEXT,
    activities_json TEXT,
    precautions_json TEXT,
    passing_criteria TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_hhs_goals_quest_id ON hhs_goals (quest_id);
CREATE INDEX IF NOT EXISTS idx_hhs_goals_goal_iri ON hhs_goals (goal_iri);
CREATE INDEX IF NOT EXISTS idx_hhs_goals_module ON hhs_goals (module_label);
