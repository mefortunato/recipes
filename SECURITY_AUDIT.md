# Security Audit: Application Design Review

**Date:** 2026-10-31
**Scope:** FastAPI backend (`backend/app`), Svelte frontend (`frontend/src`), Dockerfile, `docker-compose.yml`, deploy scripts.
**Baseline:** `main` at `a7aacd7`, after the first hardening pass (forged Google tokens, path traversal, JWT secret checks, atomic voting).

This second pass looks at the design issues that pass left open. Findings marked **Fixed** are fixed on this branch and covered by `backend/tests/test_audit_hardening.py`. Findings marked **Recommended** need an infrastructure or product decision, so they are written up but not changed.

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Dev login could be turned on outside production (e.g. `staging`), letting anyone sign in as any email, including bootstrap admins | High | Fixed |
| 2 | Sessions could not be revoked: logout only cleared the cookie, and a copied token stayed valid for 7 days | Medium | Fixed |
| 3 | Session cookies were only `Secure` when `ENVIRONMENT=production`, so HTTPS staging sent them without it | Medium | Fixed |
| 4 | No security headers: no CSP, and the admin panel could be framed (clickjacking) | Medium | Fixed |
| 5 | A recycled email could take over an existing account: the stored `google_id` was never compared with the signing-in identity | Medium | Fixed |
| 6 | Recipe image URLs were not validated (`javascript:`, `data:`, `file:`, protocol-relative) | Low–Medium | Fixed |
| 7 | CSRF protection relied only on `SameSite=Lax` and FastAPI's JSON content-type check | Low (defense in depth) | Fixed |
| 8 | Login responses returned the session JWT in the JSON body, readable by any script on the page | Low | Fixed |
| 9 | Recipe input sizes were unbounded (tags, ingredients, steps, notes, times) | Low | Fixed |
| 10 | Log injection: the JSON log format was built by string interpolation | Low | Fixed |
| 11 | `JWT_ALGORITHM` accepted any value | Low | Fixed |
| 12 | CORS allowed every method and header on credentialed requests | Info | Fixed |
| 13 | Dockerfile fell back from `npm ci` to `npm install`, skipping lockfile integrity | Low | Fixed |
| 14 | No record of who created or last edited a recipe | Info | Fixed |
| 15 | Secrets are passed to Cloud Run as plain environment variables | Medium | Recommended |
| 16 | No rate limiting on sign-in, voting or write endpoints | Medium | Recommended |
| 17 | OAuth redirect URLs fall back to the request `Host` header when `FRONTEND_URL` is unset | Low | Partly fixed (warning) / Recommended |
| 18 | Local MongoDB has no auth; Mongo Express defaults to `admin`/`pass` | Low (local only) | Recommended |
| 19 | `/health/ready`, `/docs` and `/openapi.json` are public and expose environment and DB name | Info | Recommended |

## Fixed findings

### 1. Dev login reachable outside local development (High)
`DEV_LOGIN_ENABLED` was only blocked when `ENVIRONMENT=production`. With dev login on, `POST /auth/google/verify` accepts any `email` without a Google token, so on a shared `staging` deployment anyone could sign in as the bootstrap admin email and get full admin rights.

**Fix:** settings validation now refuses `DEV_LOGIN_ENABLED=true` unless `ENVIRONMENT` is `development` or `test`. Dev logins also no longer store a fake `google_id`, so they can't interfere with linking a real Google account later.

### 2. Sessions could not be revoked (Medium)
JWTs had no ID, and logout only deleted the browser cookie. A token that leaked (from logs, a shared machine or a proxy) stayed valid for its whole 7-day life, and users and admins had no way to end sessions.

**Fix:**
- Every token now carries a unique `jti` and the user's `session_version` (`sv`).
- `POST /auth/logout` deny-lists the presented token. Revoked IDs go in a `revoked_tokens` collection with a TTL index, so entries are purged once the token would have expired anyway.
- New `POST /auth/logout-all` bumps `session_version`, which invalidates every device. It appears in the user menu as **Sign Out Everywhere**.
- New admin endpoint `POST /admin/users/{id}/revoke-sessions`.
- Tokens without a `jti`, i.e. issued before this change, are rejected. Users have to sign in once more after deploy.
- `exp`, `iat` and `sub` claims are now required.

### 3. Insecure session cookies outside production (Medium)
`cookie_secure` now returns true whenever the environment is not `development`/`test`, or `FRONTEND_URL` is `https://`. HSTS is sent whenever cookies are secure.

### 4. Missing security headers (Medium)
New middleware adds these headers:
- **Content-Security-Policy:** `default-src 'self'`, with the Google Identity Services and Google Fonts origins allowlisted, `img-src https:` for recipe photos, `frame-ancestors 'none'` and `object-src 'none'`. Swagger and ReDoc (`/docs`, `/redoc`) are exempt because they load from a CDN.
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `Cross-Origin-Opener-Policy: same-origin-allow-popups` (Google sign-in popups need this).
- `Cache-Control: no-store` on API responses, since they contain per-user data (votes, roles).

The built SPA was loaded in headless Chromium with this policy and logged no CSP violations. The Google sign-in button itself could not be tested because the sandbox has no access to Google, so check it once on staging.

### 5. Account takeover via recycled email (Medium)
Users were matched by email only. If a Google Workspace account was deleted and the address reissued to someone else, the new person inherited the old account and its role. Now, when a user already has a `google_id` and a different Google `sub` signs in with that email, the sign-in is rejected: 403 from `/google/verify`, and `?error=oauth_failed` from the redirect flow. Pre-provisioned users, who have no `google_id` yet, still get linked on first sign-in.

### 6. Unvalidated image URLs (Low–Medium)
`images` and `image_url` now accept only absolute `http(s)` URLs, up to 2048 characters, with no whitespace or control characters, and at most 10 images. Values already stored that fail these checks are dropped when recipes are returned, so legacy `javascript:` or `data:` values never reach clients.

### 7. CSRF defense in depth (Low)
State-changing requests (`POST`/`PUT`/`PATCH`/`DELETE`) under `/api/v1` are rejected with 403 when the browser's `Origin` is not same-host and not in `CORS_ORIGINS`/`FRONTEND_URL`, when `Origin` is `null`, or when `Sec-Fetch-Site: cross-site` is sent. Requests with neither header, i.e. non-browser API clients using bearer tokens, are unaffected. The same-host check compares hosts rather than full origins, because TLS ends at Cloud Run's front end and the container only sees plain http. Disable with `CSRF_ORIGIN_CHECK_ENABLED=false` if ever needed.

### 8. Session token in login response body (Low)
`/auth/google/verify` now returns `access_token: null` unless the request sets `"include_token": true`. The browser app uses only the `httpOnly` cookie, so an XSS bug can no longer just read a 7-day token from the login response.

### 9. Unbounded input sizes (Low)
| Field | Limit |
|-------|-------|
| Tags | 30 per recipe, 40 characters each, de-duplicated |
| Ingredients | 100 per recipe; name 200, unit 30, notes 300 characters |
| Steps | 100 per recipe; 2000 characters per step, tips 1000 |
| Notes | 5000 characters |
| Prep / cook time | 1 week each |
| Admin-provisioned email / name | 254 / 100 characters; email must match a basic address pattern |
| Dev-login fields | bounded lengths |

### 10. Log injection (Low)
JSON logs now go through `json.dumps`, so attacker-controlled text such as the OAuth `error` parameter can't add or forge fields. The level key is now `severity`, which Cloud Logging reads. Text logs escape `\r` and `\n`. Role changes, user deletions and session revocations are now logged with the acting admin.

### 11–13. Smaller hardening
- `JWT_ALGORITHM` is restricted to `HS256`, `HS384` or `HS512`.
- CORS now allows only the methods the API uses and the `Content-Type` and `Authorization` headers.
- The Dockerfile uses `npm ci` only, so a lockfile mismatch fails the build.
- The frontend now URL-encodes path parameters in API calls.

### 14. Recipe attribution (Info)
Recipes now store and return `created_by` and `updated_by` (user IDs). This is the basis for the audit trail and revision history suggested below.

## Recommendations (not changed on this branch)

1. **Move secrets to Secret Manager (Medium).** `scripts/deploy-gcp.sh` passes `JWT_SECRET`, `GOOGLE_CLIENT_SECRET` and `MONGODB_URI` (which contains the Atlas password) with `--set-env-vars`. Anyone with `run.services.get` can read them, and they appear in revision history. Store them in Secret Manager and deploy with `--set-secrets JWT_SECRET=recipe-jwt:latest,...`, granting the Cloud Run service account `roles/secretmanager.secretAccessor`.
2. **Rate limiting (Medium).** Add per-IP and per-user limits on `/auth/google/verify`, the vote endpoints and recipe writes, using Cloud Armor in front of Cloud Run or `slowapi` in the app. Cap `max-instances` cost exposure accordingly.
3. **Require `FRONTEND_URL` in production.** The server now logs a warning when it is missing. Once the deploy script always knows the URL before first deploy (e.g. using a custom domain), make this a hard error, so redirects never depend on the `Host` header.
4. **Local services.** Enable MongoDB auth in `docker-compose.yml` (`MONGO_INITDB_ROOT_USERNAME`/`PASSWORD`), and remove the `pass` default for Mongo Express so it requires a value to be set.
5. **Reduce public surface.** In production, consider `docs_url=None`/`openapi_url=None` (or admin-only access), and drop `environment` and the DB name from `/health/ready`.
6. **Shorter sessions.** 7-day tokens are long for an admin-capable session. Consider 12–24 hours with silent re-issue while the user is active, or a shorter lifetime for admins.
7. **Supply chain.** Pin `ghcr.io/astral-sh/uv`, `node:20-alpine` and `python:3.11-slim` by digest, and enable Dependabot for `uv.lock`, `package-lock.json` and GitHub Actions.
8. **Recipe ownership.** Any editor can edit or delete any recipe. If that is not intended, limit edits to the author (`created_by`) plus admins, and make deletes soft (see below).
9. **Third-party image hotlinking.** Remote images leak viewer IPs and referrers to arbitrary hosts and can change after review. Uploading to Cloud Storage, or proxying images, would allow tightening `img-src` to `'self'` plus the bucket.

## Suggested feature improvements

- **Soft delete and trash:** add `deleted_at` instead of hard deletes, an admin "Trash" view with restore, and a TTL purge. This protects against accidental or malicious deletion by an editor.
- **Revision history:** keep a `recipe_revisions` snapshot on every update (with `updated_by`), plus diff and rollback in the UI.
- **Admin audit log:** persist role changes, deletions and session revocations to an `audit_log` collection and show it in the Admin Panel.
- **Show "Added by / edited by" on recipe cards,** using the new attribution fields.
- **Separate favorites from upvotes:** `is_favorite` currently means "the user upvoted". A per-user collection would let people save recipes without voting.
- **Image uploads:** upload directly to Cloud Storage with signed URLs, with server-side type and size checks and automatic thumbnails.
- **Shopping list:** combine scaled ingredients from several recipes into a checklist.
- **Unit conversion:** switch between metric and imperial in the scaler.
- **Better search:** Atlas Search, or a text index with relevance ranking, instead of unanchored regex scans that can't use indexes and get slow as the collection grows.
- **Import from URL (schema.org `Recipe`):** if added, fetch server-side with an SSRF guard (block private and link-local addresses, enforce timeouts and size limits).
- **Print and cook mode:** a print stylesheet, plus a step-by-step full-screen view that keeps the screen awake.
