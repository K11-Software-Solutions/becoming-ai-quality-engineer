# Public API and Rate Limits

The NimbusNotes public API is available on the Pro and Team plans. It is not available on the Free plan.

Pro accounts can make 60 API requests per minute. Team accounts can make 300 API requests per minute per workspace.

When the limit is exceeded, the API returns HTTP status 429 Too Many Requests with a Retry-After header that says how many seconds to wait.

API keys are created under Settings, Developer, API keys. Each key can be scoped to read-only or read-write access.
