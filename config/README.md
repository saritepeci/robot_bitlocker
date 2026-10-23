# Configuration

This folder holds the framework's **centralized, layered configuration**. Nothing
in the test suites, keywords, or Python libraries should contain a hardcoded
host name, timeout, credential, or path — those all live here.

## How it works

```
default.yaml   <-- base: the single source of truth for every key
   ^
   | deep-merged on top of, by libraries/core/configuration.py
   |
<env>.yaml     <-- override: ONLY the keys that differ for that environment
```

Pick an environment at runtime with the `ENVIRONMENT` variable:

```bash
robot --variable ENVIRONMENT:ci tests      # or: make test ENV=ci
```

`variables/environment.py` (a Robot *variable file*) and
`libraries/core/context.py` (the Python service container) both read the **same**
merged configuration, so Robot `${VARIABLES}` and Python code never drift apart.

## Secrets — read before adding anything sensitive

The credentials committed here are **fake, simulation-only** values. Real secrets
must never be committed. Any value may be replaced at load time by an environment
variable using the `${env:NAME}` placeholder:

```yaml
credentials:
  windows:
    password: "${env:WINDOWS_PASSWORD}"   # resolved from the OS environment
```

In CI you provide those through the platform's secret store (GitHub Actions
secrets, Azure DevOps variable groups). A personal, git-ignored
`local.override.yaml` is also supported for developer machines.

See `docs/01_ARCHITECTURE.md` → *Centralized configuration & secrets* for the
full rationale, advantages/disadvantages, and alternatives considered.
