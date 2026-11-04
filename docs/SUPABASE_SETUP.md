# Supabase connection and setup

Verified project: VisionAIry Trader
Reference: configure the designated project through environment settings.
API URL: set `SUPABASE_URL` for your project.
Region: us-east-2
At setup, connected tools could access the project and returned no public tables.

The publishable API key is intended for permitted client operations. It does not grant administrative schema access or server privilege. No actual key is included in this repository.

The supplied direct connection string contained `[YOUR-PASSWORD]`; it is a template, not a working credential. Do not paste a database password into chat or commit it. The connected Supabase tools can prepare schema without that password. A later Render runtime needs securely configured server-side access, chosen with least privilege.

No npm dependencies have been installed: the current research code is Python. A JavaScript frontend or server-rendered login may justify the Supabase JS packages later; they are not needed merely because a project exists.

Before importing:
1. Inspect schemas, existing grants and intended Data API exposure.
2. Create versioned schema and access policies; private research data must not become public.
3. Validate constraints, provenance and owner access; run security/performance advisors.
4. Import a small dataset/run, compare counts and identifiers, then qualify full migration.
5. Verify backup/restore, quota/cost and bounded query performance.

Do not create permissive anonymous write policies to make a publishable key work. Server secrets remain server-side. The initial setup was read-only; the private trader schema, learning/retrieval guards and verified pilot import are now installed. See STATUS.md and INTEGRATION_VERIFICATION.md. No deployed application is connected yet.

