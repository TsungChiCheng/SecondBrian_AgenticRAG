-- Database initialization for Second Brain Microservices with Session Management
-- Enhanced with LangGraph conversation state support

-- Create users table for user management
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) PRIMARY KEY,  -- Google user ID (sub)
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    picture TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create conversation_sessions table for LangGraph state persistence
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT true
);

-- Create conversation_messages table for message history
CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- 'user', 'assistant', 'system', 'tool'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,  -- Store model info, tool calls, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Original prompt_logs table (kept for backward compatibility)
CREATE TABLE IF NOT EXISTS prompt_logs (
    id SERIAL PRIMARY KEY,
    user_input TEXT NOT NULL,
    answers JSONB NOT NULL,
    summary TEXT,
    user_id VARCHAR(255),
    session_id UUID REFERENCES conversation_sessions(id),  -- NEW: Link to session
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create vocabulary_memory table for vocabulary learning feature
CREATE TABLE IF NOT EXISTS vocabulary_memory (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(255) NOT NULL,
    word            VARCHAR(255) NOT NULL,
    pronunciation   TEXT,
    definition      TEXT NOT NULL,
    sample_sentence TEXT,
    related_words   TEXT[],
    language        VARCHAR(50) DEFAULT 'english',
    difficulty      VARCHAR(20),
    tags            TEXT[],
    notes           TEXT,
    review_count    INTEGER DEFAULT 0,
    last_reviewed   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Create indexes for conversation_sessions
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON conversation_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON conversation_sessions(user_id, is_active, created_at DESC);

-- Create indexes for conversation_messages
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON conversation_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON conversation_messages(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_messages_role ON conversation_messages(role);

-- Create indexes for prompt_logs
CREATE INDEX IF NOT EXISTS idx_prompt_logs_created_at ON prompt_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_summary ON prompt_logs USING gin(to_tsvector('english', summary));
CREATE INDEX IF NOT EXISTS idx_prompt_logs_user_id ON prompt_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_user_created ON prompt_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_session_id ON prompt_logs(session_id);  -- NEW index

-- Create indexes for vocabulary_memory table
CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_word ON vocabulary_memory(word);
CREATE INDEX IF NOT EXISTS idx_vocabulary_language ON vocabulary_memory(language);
CREATE INDEX IF NOT EXISTS idx_vocabulary_difficulty ON vocabulary_memory(difficulty);
CREATE INDEX IF NOT EXISTS idx_vocabulary_user_created ON vocabulary_memory(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_vocabulary_user_word ON vocabulary_memory(user_id, LOWER(word));
CREATE INDEX IF NOT EXISTS idx_vocabulary_tags ON vocabulary_memory USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_vocabulary_review ON vocabulary_memory(user_id, last_reviewed, review_count);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at for sessions
CREATE TRIGGER update_session_updated_at BEFORE UPDATE ON conversation_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
