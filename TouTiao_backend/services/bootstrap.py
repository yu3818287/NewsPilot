from sqlalchemy import text

from config.db_conf import async_engine


CREATE_COMMENTS_SQL = """
CREATE TABLE IF NOT EXISTS news_comment (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  news_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_comment_news_created (news_id, created_at),
  INDEX idx_comment_user (user_id),
  CONSTRAINT fk_comment_news FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE,
  CONSTRAINT fk_comment_user FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻评论表'
"""


async def _column_exists(connection, table: str, column: str) -> bool:
    result = await connection.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
        ),
        {"table": table, "column": column},
    )
    return bool(result.scalar_one())


async def bootstrap_database() -> None:
    """Apply small idempotent upgrades without requiring a separate migration command."""
    async with async_engine.begin() as connection:
        news_columns = {
            "source_url": "ALTER TABLE news ADD COLUMN source_url VARCHAR(1000) NULL COMMENT '原文链接'",
            "source_name": "ALTER TABLE news ADD COLUMN source_name VARCHAR(100) NULL COMMENT '来源站点'",
            "is_ai_fetched": "ALTER TABLE news ADD COLUMN is_ai_fetched TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否由AI抓取'",
            "fetched_at": "ALTER TABLE news ADD COLUMN fetched_at TIMESTAMP NULL COMMENT '抓取时间'",
        }
        for column, ddl in news_columns.items():
            if not await _column_exists(connection, "news", column):
                await connection.execute(text(ddl))

        index_result = await connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='news' AND INDEX_NAME='uq_news_source_url'"
            )
        )
        if not index_result.scalar_one():
            await connection.execute(text("CREATE UNIQUE INDEX uq_news_source_url ON news (source_url(255))"))

        await connection.execute(text(CREATE_COMMENTS_SQL))

        if not await _column_exists(connection, "ai_chat", "conversation_id"):
            await connection.execute(
                text(
                    "ALTER TABLE ai_chat ADD COLUMN conversation_id VARCHAR(64) "
                    "NOT NULL DEFAULT 'legacy' AFTER user_id"
                )
            )
        ai_chat_columns = {
            "sources_json": "ALTER TABLE ai_chat ADD COLUMN sources_json LONGTEXT NULL AFTER response",
            "actions_json": "ALTER TABLE ai_chat ADD COLUMN actions_json LONGTEXT NULL AFTER sources_json",
        }
        for column, ddl in ai_chat_columns.items():
            if not await _column_exists(connection, "ai_chat", column):
                await connection.execute(text(ddl))

        ai_index_result = await connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='ai_chat' "
                "AND INDEX_NAME='idx_ai_chat_user_conversation_created'"
            )
        )
        if not ai_index_result.scalar_one():
            await connection.execute(
                text(
                    "CREATE INDEX idx_ai_chat_user_conversation_created "
                    "ON ai_chat (user_id, conversation_id, created_at)"
                )
            )

        await connection.execute(
            text(
                "INSERT INTO news_category (name, sort_order) "
                "SELECT 'AI推荐', 0 WHERE NOT EXISTS "
                "(SELECT 1 FROM news_category WHERE name='AI推荐')"
            )
        )
        await connection.execute(
            text("UPDATE news_category SET sort_order=9 WHERE name='AI推荐'")
        )
