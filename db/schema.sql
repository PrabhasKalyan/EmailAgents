CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT,
    ceo_email TEXT,
    role TEXT,
    fit_score TEXT DEFAULT 'Unscored',
    description TEXT,
    news_headline TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_fit ON companies(fit_score);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_email ON companies(ceo_email);

CREATE TABLE IF NOT EXISTS emails_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    gmail_account TEXT,
    subject TEXT,
    body TEXT,
    sent_at DATETIME,
    thread_id TEXT,
    message_id TEXT,
    day_number INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_emails_company ON emails_sent(company_id);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails_sent(thread_id);
CREATE INDEX IF NOT EXISTS idx_emails_sent_at ON emails_sent(sent_at);

CREATE TABLE IF NOT EXISTS follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    initial_subject TEXT,
    initial_body TEXT,
    day3_subject TEXT,
    day3_body TEXT,
    day6_subject TEXT,
    day6_body TEXT,
    day3_sent_at DATETIME,
    day6_sent_at DATETIME,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_followups_company ON follow_ups(company_id);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    email_sent_id INTEGER REFERENCES emails_sent(id),
    reply_from TEXT,
    reply_subject TEXT,
    reply_snippet TEXT,
    classification TEXT,
    gmail_thread_url TEXT,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notified INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_replies_company ON replies(company_id);
CREATE INDEX IF NOT EXISTS idx_replies_classification ON replies(classification);

CREATE TABLE IF NOT EXISTS account_daily_counts (
    gmail_account TEXT,
    send_date TEXT,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (gmail_account, send_date)
);
