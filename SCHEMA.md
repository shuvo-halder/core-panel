# Database Schema (Phase 2)

## Overview
The schema is designed for PostgreSQL using Prisma ORM syntax. It handles multi-server management, RBAC, websites, and database configurations.

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// ==========================================
// User & Authentication
// ==========================================
model User {
  id            String    @id @default(uuid())
  email         String    @unique
  passwordHash  String
  name          String
  role          Role      @default(OPERATOR)
  isActive      Boolean   @default(true)
  lastLoginAt   DateTime?
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
  
  auditLogs     AuditLog[]
}

enum Role {
  SUPER_ADMIN
  ADMIN
  OPERATOR
  READ_ONLY
}

// ==========================================
// Server Management
// ==========================================
model Server {
  id            String    @id @default(uuid())
  hostname      String
  ipAddress     String
  privateIp     String?
  os            String
  agentStatus   AgentStatus @default(OFFLINE)
  lastSeen      DateTime?
  agentVersion  String?
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt

  websites      Website[]
  databases     Database[]
  cronJobs      CronJob[]
}

enum AgentStatus {
  ONLINE
  OFFLINE
  INSTALLING
  ERROR
}

// ==========================================
// Website Management
// ==========================================
model Website {
  id            String    @id @default(uuid())
  serverId      String
  domain        String    @unique
  rootDirectory String
  phpVersion    String?
  hasSsl        Boolean   @default(false)
  sslExpiry     DateTime?
  status        ServiceStatus @default(ACTIVE)

  server        Server    @relation(fields: [serverId], references: [id], onDelete: Cascade)
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
}

enum ServiceStatus {
  ACTIVE
  SUSPENDED
  DELETED
}

// ==========================================
// Database Management
// ==========================================
model Database {
  id            String    @id @default(uuid())
  serverId      String
  name          String
  dbUser        String
  type          DbType    @default(MYSQL)
  
  server        Server    @relation(fields: [serverId], references: [id], onDelete: Cascade)
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
}

enum DbType {
  MYSQL
  MARIADB
  POSTGRESQL
}

// ==========================================
// Cron Jobs
// ==========================================
model CronJob {
  id            String    @id @default(uuid())
  serverId      String
  command       String
  schedule      String    // e.g., "0 0 * * *"
  user          String    @default("root")
  isActive      Boolean   @default(true)

  server        Server    @relation(fields: [serverId], references: [id], onDelete: Cascade)
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
}

// ==========================================
// Audit Logging
// ==========================================
model AuditLog {
  id            String    @id @default(uuid())
  userId        String?
  action        String
  details       Json?
  ipAddress     String?
  createdAt     DateTime  @default(now())

  user          User?     @relation(fields: [userId], references: [id], onDelete: SetNull)
}
```
