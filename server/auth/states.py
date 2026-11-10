"""Names and limits for Google sign-in."""

# The cookie that remembers, for the few minutes the person is at Google, which sign-in this is (state + nonce).
STATE_COOKIE = "wb_oauth_state"
STATE_TTL_SECONDS = 600
# How long the one-time code in `/login?code=...` can be traded for a session. Short on purpose: it is in the address bar.
LOGIN_CODE_TTL_SECONDS = 60
# The audit log records a refused sign-in once per email and reason in this window (it is append-only, so no flooding).
REFUSED_LOGIN_QUIET_SECONDS = 600

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"  # the public keys Google signs ID tokens with
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# The `/login?error=<code>` values. The login page has a message for each (client/src/features/auth/LoginPage.tsx).
ERR_NOT_CONFIGURED = "oauth_not_configured"  # the GOOGLE_* settings are not all set
ERR_DENIED = "oauth_denied"  # the person pressed cancel at Google
ERR_STATE = "invalid_state"  # the sign-in did not start here, or took too long: start again
ERR_EXCHANGE = "token_exchange_failed"  # Google would not give us the person's identity
ERR_PROFILE = "userinfo_failed"  # what Google sent was not a valid, verified identity
ERR_DOMAIN = "domain_not_allowed"  # the verified email is not on the company domain
ERR_NOT_ONBOARDED = "not_onboarded"  # a real company account, but not an active manager or admin
ERR_RATE_LIMITED = "too_many_attempts"  # this email has tried to sign in too often in the last few minutes
