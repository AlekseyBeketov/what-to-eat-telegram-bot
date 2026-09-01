## ADDED Requirements

### Requirement: Reproducible local runtime
The system SHALL run on Python 3.12+ with pinned compatible dependencies, typed environment configuration, SQLite, migrations, long polling, structured logs without secrets, and graceful SIGINT/SIGTERM shutdown.

#### Scenario: Clean database startup
- **WHEN** migrations run against an empty writable database path
- **THEN** the complete indexed schema is created with foreign keys enabled

### Requirement: Automated verification
The system SHALL provide isolated temporary-database tests for business rules, repositories, access control, family flows, and key mocked Telegram handlers, plus Ruff checks.

#### Scenario: Clean verification run
- **WHEN** the documented test and lint commands run in a clean virtual environment
- **THEN** they complete without contacting Telegram except for an explicit optional smoke test

### Requirement: Linux service deployment
The system SHALL provide Ubuntu/Debian instructions and a systemd unit template using an unprivileged user, EnvironmentFile, writable data path, journald, one polling process, and controlled restart.

#### Scenario: Service stop
- **WHEN** systemd sends SIGTERM
- **THEN** polling stops, Telegram and SQLite resources close, and no orphan process remains
