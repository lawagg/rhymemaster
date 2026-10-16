-- ============================================================
-- СХЕМА БД — Рифмомастер
-- PostgreSQL 15+ с расширением pgvector
-- ============================================================

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- ПОЛЬЗОВАТЕЛИ
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    login           VARCHAR(64) UNIQUE,
    email_verified  BOOLEAN DEFAULT FALSE,
    role            VARCHAR(16) NOT NULL DEFAULT 'user',  -- 'user' | 'admin'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted         BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_users_email ON users(email) WHERE NOT deleted;
CREATE INDEX idx_users_role ON users(role) WHERE role = 'admin';

-- Защита админов: нельзя менять role у admin и удалять admin
CREATE OR REPLACE FUNCTION protect_admins()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE' AND OLD.role = 'admin') THEN
        RAISE EXCEPTION 'Cannot delete admin user';
    END IF;
    IF (TG_OP = 'UPDATE' AND OLD.role = 'admin' AND NEW.role != 'admin') THEN
        RAISE EXCEPTION 'Cannot change admin role';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_admins
BEFORE UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION protect_admins();

-- Подтверждение email, сброс пароля
CREATE TABLE email_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(128) UNIQUE NOT NULL,
    kind        VARCHAR(32) NOT NULL,  -- 'verify' | 'reset_password'
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_email_tokens_token ON email_tokens(token);
CREATE INDEX idx_email_tokens_user ON email_tokens(user_id);

-- Сессии (JWT хранится в cookie, но ведём лог активных токенов для отзыва)
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(128) UNIQUE NOT NULL,
    ip          INET,
    user_agent  VARCHAR(512),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at) WHERE NOT revoked;

-- ============================================================
-- ПОДПИСКИ И ПРОМОКОДЫ
-- ============================================================

CREATE TABLE subscriptions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan        VARCHAR(32) NOT NULL DEFAULT 'monthly',  -- 'monthly'
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    payment_id  VARCHAR(128),
    source      VARCHAR(32) NOT NULL DEFAULT 'robokassa',  -- 'robokassa' | 'promo' | 'gift'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subs_user ON subscriptions(user_id);
CREATE INDEX idx_subs_active ON subscriptions(user_id, expires_at)
    WHERE expires_at > NOW();

-- Лимиты простой формы (10 поисков в день)
CREATE TABLE usage_limits (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_start    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    searches_used   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, period_start)
);

CREATE INDEX idx_usage_user ON usage_limits(user_id);

CREATE TABLE promo_codes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            VARCHAR(32) UNIQUE NOT NULL,
    duration_days   INTEGER NOT NULL,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    used_by         UUID REFERENCES users(id),
    used_at         TIMESTAMPTZ,
    revoked         BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_promo_code ON promo_codes(code);
CREATE INDEX idx_promo_unused ON promo_codes(expires_at)
    WHERE used_by IS NULL AND NOT revoked;

-- Лимит: 2 кода в день на админа
CREATE OR REPLACE FUNCTION check_promo_daily_limit()
RETURNS TRIGGER AS $$
DECLARE
    today_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO today_count
    FROM promo_codes
    WHERE created_by = NEW.created_by
      AND created_at >= CURRENT_DATE
      AND created_at < CURRENT_DATE + INTERVAL '1 day';

    IF today_count >= 2 THEN
        RAISE EXCEPTION 'Daily promo limit reached (2 per day)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_promo_daily_limit
BEFORE INSERT ON promo_codes
FOR EACH ROW EXECUTE FUNCTION check_promo_daily_limit();
-- ============================================================
-- СТУДИЯ: ПРОЕКТЫ И СТРУКТУРА ХОЛСТА
-- ============================================================

CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL DEFAULT 'Без названия',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted     BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_projects_user ON projects(user_id) WHERE NOT deleted;

-- Строка куплета (4 такта)
CREATE TABLE lines (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    input_text  TEXT DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lines_project ON lines(project_id, position);

-- Такт (в строке 4 такта)
CREATE TABLE tacts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    line_id     UUID NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
    position    SMALLINT NOT NULL CHECK (position BETWEEN 0 AND 3),
    mode        VARCHAR(16) NOT NULL DEFAULT 'standard',  -- 'standard' | 'custom'
    size        SMALLINT NOT NULL DEFAULT 4,  -- количество ячеек: 2, 3, 4, 6, 8
    pattern     VARCHAR(32) DEFAULT 'Хорей',  -- паттерн если standard
    continue_rhythm BOOLEAN DEFAULT FALSE,
    UNIQUE (line_id, position)
);

CREATE INDEX idx_tacts_line ON tacts(line_id, position);

-- Ячейка (слог в такте)
-- state: 'stressed' | 'unstressed' | 'empty'
-- mark:  'green' | 'blue' | 'purple' | 'yellow' | NULL (цвет маркера рифмы)
-- mark_group: числовой ID группы рифмы в рамках проекта
CREATE TABLE cells (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tact_id     UUID NOT NULL REFERENCES tacts(id) ON DELETE CASCADE,
    position    SMALLINT NOT NULL,
    state       VARCHAR(16) NOT NULL DEFAULT 'empty',
    text        VARCHAR(64),  -- слог, если вписан
    word_id     UUID,  -- FK на words (заполняется бэкендом)
    mark        VARCHAR(16),
    mark_group  INTEGER,
    UNIQUE (tact_id, position)
);

CREATE INDEX idx_cells_tact ON cells(tact_id, position);
CREATE INDEX idx_cells_mark ON cells(mark, mark_group) WHERE mark IS NOT NULL;

-- Шаблоны рифм (запросы) на уровне проекта
-- Один шаблон на цвет
CREATE TABLE marker_templates (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    color       VARCHAR(16) NOT NULL,
    group_id    INTEGER NOT NULL,  -- ID первой нарисованной группы
    length      SMALLINT NOT NULL,
    states      VARCHAR(32) NOT NULL,  -- сериализованные состояния через запятую
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, color)
);

CREATE INDEX idx_templates_project ON marker_templates(project_id);

-- Закреплённые результаты в панели Б
CREATE TABLE pinned_results (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    text        VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pinned_project ON pinned_results(project_id);

-- Undo-стек на уровне проекта (серверная синхронизация)
CREATE TABLE undo_stack (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_undo_project ON undo_stack(project_id, created_at DESC);

-- Проверка: количество ячеек в такте должно совпадать с size
CREATE OR REPLACE FUNCTION check_tact_size()
RETURNS TRIGGER AS $$
DECLARE
    cell_count INTEGER;
    tact_size SMALLINT;
BEGIN
    SELECT size INTO tact_size FROM tacts WHERE id = NEW.tact_id;
    SELECT COUNT(*) INTO cell_count FROM cells WHERE tact_id = NEW.tact_id;

    -- Не блокируем, но при попытке вставить больше size — ошибка
    IF cell_count >= tact_size THEN
        RAISE EXCEPTION 'Cannot add more cells than tact size (%)', tact_size;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_tact_size
BEFORE INSERT ON cells
FOR EACH ROW EXECUTE FUNCTION check_tact_size();
-- ============================================================
-- СЛОВАРЬ И ЧАСТОТНОСТЬ
-- ============================================================

CREATE TABLE words (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    text        VARCHAR(64) NOT NULL,
    ipa         VARCHAR(255),  -- IPA-транскрипция (пре-компьютинг)
    phonemes    JSONB,  -- массив фонем с флагами stressed/soft
    syllables   SMALLINT,
    is_profanity BOOLEAN DEFAULT FALSE,
    slang_type  VARCHAR(32),  -- 'молодёжный' | 'геймерский' | 'интернет' | 'уличный' | 'мат' | NULL
    group_label VARCHAR(64),  -- группа из корпуса
    definition  TEXT,  -- краткое определение
    deleted     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_words_text ON words(LOWER(text)) WHERE NOT deleted;
CREATE INDEX idx_words_slang_type ON words(slang_type);
CREATE INDEX idx_words_profanity ON words(is_profanity);
-- Полнотекстовый индекс по слову (для быстрого поиска по частям)
CREATE INDEX idx_words_text_trgm ON words USING GIN (LOWER(text) gin_trgm_ops);

-- Частотность (пересчитывается cron раз в месяц)
CREATE TABLE word_frequencies (
    word_id     UUID PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
    ipm         NUMERIC(12, 4) NOT NULL,  -- instances per million
    source      VARCHAR(32) NOT NULL,  -- 'lyashevskaya' | 'ruword_frequency' | 'own_corpus'
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_freq_ipm ON word_frequencies(ipm DESC);

-- Векторы слов (pgvector, 300-мерные)
CREATE TABLE word_vectors (
    word_id     UUID PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
    source      VARCHAR(32) NOT NULL,  -- 'navec' | 'word2vec_v3' | 'fasttext'
    vector      vector(300) NOT NULL
);

-- HNSW-индекс для быстрого семантического поиска
CREATE INDEX idx_vectors_hnsw ON word_vectors
    USING hnsw (vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================
-- КОНТЕНТ: КРЫЛАТЫЕ ФРАЗЫ, ПОСЛОВИЦЫ, АФОРИЗМЫ
-- ============================================================

CREATE TABLE phrases (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    text        TEXT NOT NULL,
    kind        VARCHAR(32) NOT NULL,  -- 'krylatye' | 'poslovicy' | 'aforizmy' | 'slang'
    source      VARCHAR(32) DEFAULT 'community',
    group_label VARCHAR(64),
    definition  TEXT,
    phonemes    JSONB,  -- пре-компьютинг
    syllables   SMALLINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_phrases_kind ON phrases(kind);
CREATE INDEX idx_phrases_text_trgm ON phrases USING GIN (text gin_trgm_ops);

-- ============================================================
-- МОДЕРАЦИЯ ПОЛЬЗОВАТЕЛЬСКОГО ВВОДА
-- ============================================================

CREATE TABLE moderation_queue (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    word_text   VARCHAR(64) NOT NULL,
    submitted_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status      VARCHAR(16) NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    reason      VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_moderation_status ON moderation_queue(status);
CREATE INDEX idx_moderation_user ON moderation_queue(submitted_by);

-- Лог модерации
CREATE TABLE moderation_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id    UUID NOT NULL REFERENCES users(id),
    action      VARCHAR(32) NOT NULL,  -- 'approve' | 'reject' | 'edit' | 'delete'
    target_type VARCHAR(32) NOT NULL,  -- 'word' | 'phrase'
    target_id   UUID NOT NULL,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_modlog_admin ON moderation_log(admin_id, created_at DESC);

-- ============================================================
-- ЛОГИ ПОИСКА (для улучшения корпуса)
-- ============================================================

CREATE TABLE search_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    query       TEXT NOT NULL,
    mode        VARCHAR(16) NOT NULL,  -- 'simple' | 'studio'
    results_count INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_log_user ON search_log(user_id);
CREATE INDEX idx_search_log_created ON search_log(created_at DESC);

-- ============================================================
-- ОБНОВЛЕНИЕ updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_projects_updated
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_words_updated
BEFORE UPDATE ON words
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- КОНЕЦ СХЕМЫ
-- ============================================================