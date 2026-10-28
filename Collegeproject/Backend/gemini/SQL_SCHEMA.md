# SQL Schema for Gemini Integration

This document shows the SQL schema for the Gemini integration models. These are automatically created when you run `python manage.py migrate`.

## Tables

### 1. gemini_geminiconversation

Stores conversation sessions with Gemini.

```sql
CREATE TABLE gemini_geminiconversation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NULL,
    session_id VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(200) NULL,
    context TEXT NULL,  -- JSON field
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);

CREATE INDEX idx_gemini_conv_updated ON gemini_geminiconversation(updated_at DESC);
CREATE INDEX idx_gemini_conv_user_updated ON gemini_geminiconversation(user_id, updated_at DESC);
CREATE INDEX idx_gemini_conv_session ON gemini_geminiconversation(session_id);
```

### 2. gemini_geminimessage

Stores individual messages in conversations.

```sql
CREATE TABLE gemini_geminimessage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata TEXT NULL,  -- JSON field
    created_at DATETIME NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES gemini_geminiconversation(id) ON DELETE CASCADE
);

CREATE INDEX idx_gemini_msg_conv_created ON gemini_geminimessage(conversation_id, created_at);
CREATE INDEX idx_gemini_msg_created ON gemini_geminimessage(created_at DESC);
```

### 3. gemini_geminiquestiongeneration

Stores generated interview questions.

```sql
CREATE TABLE gemini_geminiquestiongeneration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NULL,
    session_id VARCHAR(100) NOT NULL,
    job_role VARCHAR(200) NOT NULL,
    years_of_experience VARCHAR(50) NOT NULL,
    questions TEXT NOT NULL,  -- JSON array
    candidate_info TEXT NULL,  -- JSON object
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);

CREATE INDEX idx_gemini_qgen_created ON gemini_geminiquestiongeneration(created_at DESC);
CREATE INDEX idx_gemini_qgen_user_created ON gemini_geminiquestiongeneration(user_id, created_at DESC);
CREATE INDEX idx_gemini_qgen_session ON gemini_geminiquestiongeneration(session_id);
```

### 4. gemini_geminiapiusage

Tracks API usage for analytics and rate limiting.

```sql
CREATE TABLE gemini_geminiapiusage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NULL,
    session_id VARCHAR(100) NULL,
    endpoint VARCHAR(100) NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    response_time_ms INTEGER NULL,
    success BOOLEAN NOT NULL DEFAULT 1,
    error_message TEXT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);

CREATE INDEX idx_gemini_usage_created ON gemini_geminiapiusage(created_at DESC);
CREATE INDEX idx_gemini_usage_user_created ON gemini_geminiapiusage(user_id, created_at DESC);
CREATE INDEX idx_gemini_usage_session_created ON gemini_geminiapiusage(session_id, created_at DESC);
```

## Manual SQL Queries (if needed)

### Get all conversations for a user

```sql
SELECT * FROM gemini_geminiconversation 
WHERE user_id = ? 
ORDER BY updated_at DESC;
```

### Get conversation messages

```sql
SELECT * FROM gemini_geminimessage 
WHERE conversation_id = ? 
ORDER BY created_at ASC;
```

### Get API usage statistics

```sql
SELECT 
    endpoint,
    COUNT(*) as total_requests,
    SUM(tokens_used) as total_tokens,
    AVG(response_time_ms) as avg_response_time,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests
FROM gemini_geminiapiusage
WHERE created_at >= datetime('now', '-7 days')
GROUP BY endpoint;
```

### Get questions for a session

```sql
SELECT * FROM gemini_geminiquestiongeneration 
WHERE session_id = ? 
ORDER BY created_at DESC 
LIMIT 1;
```

## Notes

- All timestamps are stored in UTC
- JSON fields are stored as TEXT in SQLite, but Django handles them as JSON
- Foreign keys to `auth_user` are nullable to support unauthenticated users
- Indexes are automatically created by Django migrations

