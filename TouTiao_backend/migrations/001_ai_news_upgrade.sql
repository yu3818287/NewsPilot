USE news_app;

-- main.py 启动时会幂等执行同等迁移；本文件用于手动部署和审计。
ALTER TABLE news ADD COLUMN source_url VARCHAR(1000) NULL COMMENT '原文链接';
ALTER TABLE news ADD COLUMN source_name VARCHAR(100) NULL COMMENT '来源站点';
ALTER TABLE news ADD COLUMN is_ai_fetched TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否由AI抓取';
ALTER TABLE news ADD COLUMN fetched_at TIMESTAMP NULL COMMENT '抓取时间';
CREATE UNIQUE INDEX uq_news_source_url ON news (source_url(255));

CREATE TABLE news_comment (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  news_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_comment_news_created (news_id, created_at),
  INDEX idx_comment_user (user_id),
  CONSTRAINT fk_comment_news FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE,
  CONSTRAINT fk_comment_user FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE ai_chat ADD COLUMN conversation_id VARCHAR(64) NOT NULL DEFAULT 'legacy' AFTER user_id;
ALTER TABLE ai_chat ADD COLUMN sources_json LONGTEXT NULL AFTER response;
ALTER TABLE ai_chat ADD COLUMN actions_json LONGTEXT NULL AFTER sources_json;
CREATE INDEX idx_ai_chat_user_conversation_created ON ai_chat (user_id, conversation_id, created_at);
INSERT IGNORE INTO news_category (name, sort_order) VALUES ('AI推荐', 0);
