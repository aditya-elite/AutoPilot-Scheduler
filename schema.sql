-- =====================================================================
-- AutoPilot Scheduler — Phase 1 PostgreSQL Schema
-- =====================================================================
-- Design notes:
--   * This schema supports a FLEXIBLE job-shop model: a task can be
--     processed on more than one eligible machine, each with its own
--     processing time (task_machine_eligibility). This is what lets
--     the OR-Tools engine choose the best machine, not just the best
--     start time.
--   * Every mutable entity (assignments, machine status, jobs) is
--     paired with an audit_logs trail so managers can see exactly
--     what the AI (or a human) changed and why.
--   * Enums are implemented as native PostgreSQL types for data
--     integrity at the DB layer (defense in depth — don't rely on
--     the API alone to enforce valid states).
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";       -- gen_random / uuid helpers
CREATE EXTENSION IF NOT EXISTS "pgcrypto";        -- gen_random_uuid()

-- ---------------------------------------------------------------------
-- Enumerated types
-- ---------------------------------------------------------------------
CREATE TYPE user_role            AS ENUM ('admin', 'factory_manager', 'machine_operator');
CREATE TYPE machine_status       AS ENUM ('online', 'offline', 'maintenance', 'degraded');
CREATE TYPE job_status           AS ENUM ('pending', 'scheduled', 'in_progress', 'completed', 'cancelled');
CREATE TYPE task_status          AS ENUM ('pending', 'scheduled', 'in_progress', 'completed', 'blocked');
CREATE TYPE assignment_status    AS ENUM ('planned', 'confirmed', 'in_progress', 'completed', 'violated', 'superseded');
CREATE TYPE optimization_goal    AS ENUM ('minimize_makespan', 'minimize_tardiness', 'maximize_profit', 'balanced');
CREATE TYPE optimization_status  AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE downtime_reason      AS ENUM ('unplanned_breakdown', 'planned_maintenance', 'predicted_failure_risk');

-- ---------------------------------------------------------------------
-- Users & roles (kept minimal here — auth detail belongs to an
-- identity table you may already own; this is the FK anchor point)
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(128) NOT NULL,
    role            user_role NOT NULL DEFAULT 'machine_operator',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Machines — the resources tasks compete for
-- ---------------------------------------------------------------------
CREATE TABLE machines (
    machine_id          SERIAL PRIMARY KEY,
    machine_code        VARCHAR(32) NOT NULL UNIQUE,      -- e.g. "CNC-04"
    machine_name        VARCHAR(128) NOT NULL,
    machine_type        VARCHAR(64) NOT NULL,             -- e.g. "CNC_MILL", "LATHE", "ASSEMBLY_LINE"
    status              machine_status NOT NULL DEFAULT 'online',
    cost_per_hour       NUMERIC(10,2) NOT NULL DEFAULT 0,  -- feeds "maximize profit" objective
    failure_risk_score  NUMERIC(5,4) NOT NULL DEFAULT 0,   -- 0..1, written by the ML maintenance model
    age_years           NUMERIC(4,1) NOT NULL DEFAULT 5,   -- feeds the ML failure-risk model
    last_maintained_at  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Planned or unplanned windows during which a machine cannot be used.
-- The solver treats these as hard "forbidden intervals" per machine —
-- this is exactly what powers the Breakdown Simulator.
CREATE TABLE machine_downtime (
    downtime_id     BIGSERIAL PRIMARY KEY,
    machine_id      INTEGER NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    reason          downtime_reason NOT NULL,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    notes           TEXT,
    created_by      UUID REFERENCES users(user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT downtime_valid_range CHECK (end_time > start_time)
);
CREATE INDEX idx_machine_downtime_machine_time ON machine_downtime (machine_id, start_time, end_time);

-- ---------------------------------------------------------------------
-- Jobs — a customer order / production order, made of ordered tasks
-- ---------------------------------------------------------------------
CREATE TABLE jobs (
    job_id          SERIAL PRIMARY KEY,
    job_code        VARCHAR(32) NOT NULL UNIQUE,          -- e.g. "SO-2026-0142"
    description     TEXT,
    priority_weight SMALLINT NOT NULL DEFAULT 5 CHECK (priority_weight BETWEEN 1 AND 10),
    profit_value    NUMERIC(12,2) NOT NULL DEFAULT 0,      -- feeds "maximize profit" objective
    due_date        TIMESTAMPTZ NOT NULL,
    material_available_minutes INT NOT NULL DEFAULT 0,
    status          job_status NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_due_date ON jobs (due_date);
CREATE INDEX idx_jobs_status ON jobs (status);

-- ---------------------------------------------------------------------
-- Tasks — an ordered operation within a job (job-shop "operation")
-- ---------------------------------------------------------------------
CREATE TABLE tasks (
    task_id                 SERIAL PRIMARY KEY,
    job_id                  INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    sequence_index          SMALLINT NOT NULL,             -- 0-based order within the job
    task_name               VARCHAR(128) NOT NULL,
    base_duration_minutes   INTEGER NOT NULL CHECK (base_duration_minutes > 0),   -- nominal/engineering estimate
    predicted_duration_minutes INTEGER,                    -- written by the ML duration model, nullable until predicted
    status                  task_status NOT NULL DEFAULT 'pending',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, sequence_index)
);
CREATE INDEX idx_tasks_job ON tasks (job_id);

-- Which machines CAN run a given task, and how long it takes on each
-- one. This is the crux of "flexible" job-shop scheduling: OR-Tools
-- picks both the machine AND the timing simultaneously.
CREATE TABLE task_machine_eligibility (
    task_id             INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    machine_id          INTEGER NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    processing_minutes  INTEGER NOT NULL CHECK (processing_minutes > 0),
    PRIMARY KEY (task_id, machine_id)
);

-- ---------------------------------------------------------------------
-- Assignments — the actual (or proposed) placement of a task on a
-- machine at a point in time. This table IS the Gantt chart data.
-- ---------------------------------------------------------------------
CREATE TABLE assignments (
    assignment_id       BIGSERIAL PRIMARY KEY,
    task_id             INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    machine_id          INTEGER NOT NULL REFERENCES machines(machine_id),
    scheduled_start     TIMESTAMPTZ NOT NULL,
    scheduled_end       TIMESTAMPTZ NOT NULL,
    actual_start        TIMESTAMPTZ,
    actual_end          TIMESTAMPTZ,
    status              assignment_status NOT NULL DEFAULT 'planned',
    is_manual_override  BOOLEAN NOT NULL DEFAULT FALSE,     -- true if a manager drag-and-dropped this
    violates_constraint BOOLEAN NOT NULL DEFAULT FALSE,     -- flagged by validation pass after manual override
    violation_reason    TEXT,
    optimization_run_id BIGINT,                             -- FK added below after optimization_runs exists
    created_by          UUID REFERENCES users(user_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT assignment_valid_range CHECK (scheduled_end > scheduled_start)
);
CREATE INDEX idx_assignments_machine_time ON assignments (machine_id, scheduled_start, scheduled_end);
CREATE INDEX idx_assignments_task ON assignments (task_id);

-- ---------------------------------------------------------------------
-- Optimization runs — one row per solver invocation, so every Gantt
-- state can be traced back to the run (and objective/config) that
-- produced it. Essential for the "Breakdown Simulator" re-solve loop.
-- ---------------------------------------------------------------------
CREATE TABLE optimization_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    triggered_by    UUID REFERENCES users(user_id),
    goal            optimization_goal NOT NULL DEFAULT 'balanced',
    status          optimization_status NOT NULL DEFAULT 'queued',
    solver_config   JSONB NOT NULL DEFAULT '{}'::jsonb,     -- weights, time limit, etc.
    objective_value NUMERIC,
    makespan_minutes INTEGER,
    total_tardiness_minutes INTEGER,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE assignments
    ADD CONSTRAINT fk_assignments_run
    FOREIGN KEY (optimization_run_id) REFERENCES optimization_runs(run_id);

-- ---------------------------------------------------------------------
-- Audit logs — generic change trail across the mutable entities above
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
    log_id          BIGSERIAL PRIMARY KEY,
    entity_type     VARCHAR(32) NOT NULL,     -- 'job' | 'task' | 'assignment' | 'machine'
    entity_id       BIGINT NOT NULL,
    action          VARCHAR(32) NOT NULL,     -- 'create' | 'update' | 'delete' | 'override' | 'ai_reschedule'
    old_value       JSONB,
    new_value       JSONB,
    changed_by      UUID REFERENCES users(user_id),
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_changed_at ON audit_logs (changed_at);

-- ---------------------------------------------------------------------
-- updated_at helper trigger (kept small and reusable)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_machines_updated_at
    BEFORE UPDATE ON machines
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
