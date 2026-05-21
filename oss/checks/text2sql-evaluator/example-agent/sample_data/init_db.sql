CREATE TABLE IF NOT EXISTS "User" (
    "id" INTEGER PRIMARY KEY,
    "email" TEXT NOT NULL,
    "firstName" TEXT,
    "lastName" TEXT,
    "createdAt" TEXT NOT NULL,
    "isTestAccount" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "Organization" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL,
    "createdAt" TEXT NOT NULL,
    "isActive" INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS "OrganizationUser" (
    "organizationId" INTEGER NOT NULL,
    "userId" INTEGER NOT NULL,
    PRIMARY KEY ("organizationId", "userId"),
    FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id"),
    FOREIGN KEY ("userId") REFERENCES "User" ("id")
);

CREATE TABLE IF NOT EXISTS "Order" (
    "id" INTEGER PRIMARY KEY,
    "userId" INTEGER NOT NULL,
    "amountCents" INTEGER NOT NULL,
    "status" TEXT NOT NULL,
    "createdAt" TEXT NOT NULL,
    FOREIGN KEY ("userId") REFERENCES "User" ("id")
);

INSERT INTO "User" ("id", "email", "firstName", "lastName", "createdAt", "isTestAccount") VALUES
    (1, 'ada@example.com', 'Ada', 'Lovelace', '2024-01-10', 0),
    (2, 'grace@example.com', 'Grace', 'Hopper', '2024-02-15', 0),
    (3, 'test-bot@internal', 'Test', 'Bot', '2024-03-01', 1);

INSERT INTO "Organization" ("id", "name", "createdAt", "isActive") VALUES
    (1, 'Acme Corp', '2024-01-01', 1),
    (2, 'Inactive LLC', '2023-06-01', 0);

INSERT INTO "OrganizationUser" ("organizationId", "userId") VALUES
    (1, 1),
    (1, 2);

INSERT INTO "Order" ("id", "userId", "amountCents", "status", "createdAt") VALUES
    (1, 1, 5000, 'completed', '2024-05-01'),
    (2, 2, 12000, 'completed', '2024-05-10'),
    (3, 1, 3000, 'pending', '2024-06-01');
