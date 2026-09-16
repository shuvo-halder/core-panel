# Implementation Plan — Phase Execution Guidelines

## 1. Execution Framework Rules

For every phase in the Master Roadmap, the following strictly enforced cycle must be executed:

1. **Read Existing Documentation:** Review all architecture specifications and relevant docs.
2. **Inspect Existing Implementation:** Audit current codebase files and dependencies.
3. **Identify Dependencies:** Determine prerequisite phases or external packages required.
4. **Update Workplan:** Define exact scope, boundary conditions, and acceptance criteria.
5. **Implement Code:** Write clean, modular, typed code adhering to security rules.
6. **Run Unit Tests:** Verify core logic with isolated unit test suites.
7. **Run Integration Tests:** Verify end-to-end API and database behavior.
8. **Run Build & Type Checks:** Execute static type checking (`mypy` / `tsc`) and linters.
9. **Perform Security Verification:** Verify threat mitigations (path jail, command whitelists, auth).
10. **Perform Failure Scenario Testing:** Test failure recovery, partial writes, network drops, locks.
11. **Update Documentation:** Keep `docs/` synchronized with actual implementation.
12. **Update `pending-work.md`:** Mark completed deliverables and record next priorities.
13. **Write Implementation Report:** Provide concise summary of completed work.

---

## 2. Immediate Focus: Phase 1 & Phase 2 Transition

- **Phase 1 Goal:** Complete initial repository architecture audit, threat modeling, and setup of all required technical documentation under `docs/`.
- **Phase 2 Goal:** Set up Python 3.12+ / FastAPI / Pydantic / Uvicorn backend structure with SQLite Alembic migrations and baseline health endpoints.
