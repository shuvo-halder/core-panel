# Comprehensive Test Strategy

## 1. Testing Methodology

CorePanel requires rigorous automated testing to prevent regressions and ensure high security for server management tasks.

```
                  ┌──────────────────────┐
                  │    System & E2E      │
                  │ Playwright / Cypress │
                  └──────────┬───────────┘
                             │
                  ┌──────────┴───────────┐
                  │  Integration Tests   │
                  │ Pytest / FastAPI Test│
                  └──────────┬───────────┘
                             │
                  ┌──────────┴───────────┐
                  │      Unit Tests      │
                  │ Pytest / Mocked OS   │
                  └──────────────────────┘
```

---

## 2. Testing Levels

### A. Unit Testing (`pytest`)
- Tests business domain logic, configuration generators, and Pydantic validators.
- Mocks out subprocess executions and external OS calls.
- Target coverage: >85% for backend services.

### B. Linux Adapter & Command Runner Tests
- Tests `LinuxCommandRunner` against whitelisted/blacklisted inputs.
- Verifies zero shell concatenation and strict argument array passing.
- Validates path jail enforcers and canonical path resolution.

### C. API Integration Tests (`httpx` AsyncClient)
- Verifies FastAPI routes, request validation, authentication headers, and response status codes.
- Verifies database interactions using an isolated in-memory or temporary SQLite test database.

### D. Failure & Edge Case Testing
- **Locked Package Manager:** Mocks `apt-get` lock error (`/var/lib/dpkg/lock-frontend`) and verifies retry/error envelope.
- **Invalid Nginx Config:** Mocks `nginx -t` exit code 1 and verifies automatic configuration rollback.
- **Disk Space Exhaustion:** Simulates low disk condition and verifies task failure reporting.
