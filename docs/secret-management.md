<!-- secret-migrate:start -->
# Repository secret management

Secrets for this repository are managed with Bitwarden Secrets Manager.

- Keep `BWS_ACCESS_TOKEN` in the external user session; never place it in this repository.
- Run trusted native commands with `./scripts/with-secrets '<command>'`.
- Start the local Compose project with `./scripts/dev-up`.
- Check migration state with `secret-migrate status .`.
- Run `secret-migrate verify .` before `secret-migrate cleanup .`.
- Review any repository-configured health command before using `--allow-health-command`.
- Do not print, log, diff, commit, or copy injected environment values.

`bws run` injects project secrets into the trusted child process. Secret assignments in local
env-style files are blanked only after successful verification and explicit cleanup. Ordinary
configuration remains local, and `.env.example` contains names without migrated values.
<!-- secret-migrate:end -->
