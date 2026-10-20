# RestoCore Runbook

## Deployment policy

RestoCore uses three deployment stages:

1. Local development for active implementation and visual QA.
2. Staging for integrated testing against production-like infrastructure.
3. Production for approved releases only.

Docker is intentionally deferred until after Version 1. The first staging and production deployments may therefore use a conventional Python application stack. Docker can be introduced later without changing the branch policy.

## Branch mapping

| Branch | Purpose | Deployment |
| --- | --- | --- |
| `feature/*`, `fix/*`, `chore/*` | Short-lived development | Local only |
| `staging` | Integrated release candidate | Future staging environment |
| `main` | Production-ready releases | Future production environment |

Normal promotion path:

```text
feature/fix/chore
      |
      v
   staging
      |
      v
     main
```

Changes should enter `staging` through pull requests after local validation and CI. Production releases should enter `main` through a pull request from `staging` after staging verification.

## CI

GitHub Actions runs on:

- every pull request
- every push to `staging`
- every push to `main`

CI validates:

- Ruff linting
- Ruff formatting
- Django system checks
- migration drift
- migrations against PostgreSQL
- the full pytest suite

CI passing is necessary but does not replace staging or manual product QA.

## Environment isolation

Staging and production must not share mutable infrastructure.

Each environment requires its own:

- application directory
- PostgreSQL database and database user
- Django secret key
- allowed hosts and CSRF origins
- uploaded media storage
- logs
- process configuration
- environment file or secret store

Never point staging at the production database.

## Planned non-Docker server stack

Until Docker is introduced, the recommended deployment stack is:

- Ubuntu LTS
- Python 3.12
- uv
- PostgreSQL 16+
- Gunicorn
- Nginx
- systemd
- HTTPS via a managed certificate or Certbot

Redis and Celery should only be added when a feature actually requires background work.

## Planned server layout

Use a dedicated RestoCore host or isolated server paths. Do not place RestoCore inside the existing ProSupport Squad application directories.

Suggested layout:

```text
/var/www/restocore/
  staging/
  production/
```

Suggested service names:

```text
restocore-staging
restocore-production
```

Suggested databases:

```text
restocore_staging
restocore_production
```

## Staging deployment contract

A staging deployment should eventually perform these steps:

1. Fetch the exact `staging` commit.
2. Sync dependencies from `uv.lock`.
3. Load staging-only environment variables.
4. Run `python manage.py check --settings=config.settings.staging`.
5. Run pending migrations.
6. Collect static assets.
7. Restart the staging application process.
8. Verify `/healthz/`.
9. Smoke-test login and critical pages.
10. Record the deployed commit SHA.

Automatic deployment may be added only after the staging host and GitHub environment secrets exist.

## Production deployment contract

Production remains manual until staging deployment and rollback have been exercised successfully.

A production release should:

1. Start only from a commit already verified on `staging`.
2. Take a database backup before migrations.
3. Fetch the exact approved `main` commit.
4. Sync locked dependencies.
5. Run Django deployment checks.
6. Apply migrations.
7. Collect static assets.
8. Restart the production application process.
9. Verify `/healthz/` and critical workflows.
10. Record the deployed SHA and backup reference.

Do not deploy a feature branch directly to production.

## Rollback policy

Application rollback and database rollback are separate decisions.

For an application-only regression:

1. Identify the last known-good deployed commit.
2. Check whether the failed release applied migrations.
3. If schema remains backward-compatible, redeploy the known-good commit.
4. Verify health and critical workflows.

If the release includes destructive or incompatible migrations, do not blindly reverse the application commit. Restore or migrate the database using a reviewed recovery plan.

## Backups

Before the first real deployment, define and test:

- automated PostgreSQL backups
- backup retention
- restore procedure
- media backup if uploads are introduced
- restore verification

A backup is not considered operational until a restore has been tested.

## Current state

As of the current development phase:

- local development is active
- `staging` exists in GitHub
- `main` remains the production branch
- CI is configured for pull requests, `staging`, and `main`
- no RestoCore staging server exists yet
- no RestoCore production server exists yet
- no deployment workflow is enabled yet
- Docker remains deferred until after Version 1
