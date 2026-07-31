# Universal VPS Management Panel Architecture (Phase 1)

## Overview
This document outlines the architecture for a production-grade, self-hosted VPS Management Platform designed to be a modern, lightweight alternative to standard control panels.

## 1. System Architecture

### 1.1 Core Components
*   **Central Dashboard (React + Vite):** A lightweight, SPA frontend providing a rich GUI for server management.
*   **API Server (Express / Node.js):** REST API handling business logic, authentication, and communication with server agents.
*   **Server Agent (Go/Node):** A lightweight daemon running on managed servers to execute system commands, monitor resources, and report back to the central panel securely.
*   **Database (PostgreSQL):** Stores server configurations, users, RBAC roles, audit logs, and website configurations.
*   **Cache & Queue (Redis):** Handles session management, WebSocket state, and background task queuing (e.g., backups, software installations).

### 1.2 Communication Flow
1.  **User -> Dashboard:** HTTPS, WebSocket (for real-time metrics and terminal).
2.  **Dashboard -> API Server:** REST (JSON), JWT Auth.
3.  **API Server -> Server Agent:** Mutual TLS (mTLS) or JWT-secured gRPC/REST over private IP or secure tunnel.

## 2. Technology Stack

*   **Frontend:** React 19, Tailwind CSS (High Density theme), Vite, Zustand (State Management).
*   **Backend:** Node.js, Express (TypeScript), Prisma (ORM), jsonwebtoken.
*   **Real-time:** Socket.io or native WebSockets (ws).
*   **Database:** PostgreSQL 16+.
*   **Monitoring:** Prometheus exporter integration.

## 3. Security Architecture
*   **Authentication:** JWT-based auth with short-lived access tokens and HttpOnly refresh tokens.
*   **RBAC (Role-Based Access Control):** Granular permissions (Super Admin, Admin, Operator, Read Only).
*   **Command Execution:** All system commands are executed via parameterized wrappers avoiding shell injection (e.g., using `spawn` without `shell: true`).
*   **Network:** API Server and Database should reside in a private subnet, exposing only the HTTPS port.

## 4. Phase Delivery Plan
*   **Phase 1:** Architecture & System Design (Completed)
*   **Phase 2:** Database Schema Design (Completed - see SCHEMA.md)
*   **Phase 3:** Backend Implementation (In Progress)
*   **Phase 4:** Frontend Implementation (In Progress)
*   **Phase 5:** Agent Implementation
*   **Phase 6:** Security Audit & Testing
