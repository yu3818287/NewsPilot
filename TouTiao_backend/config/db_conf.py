from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config.settings import settings

# 数据库URL
ASYNC_DATABASE_URL = settings.database_url

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    # 提前准备好一批(10)数据库连接，反复用，避免每次都重新连
    pool_size=10,   # 设置链接活跃池的连接数
    # 刚放弃连接池增至 10+20
    max_overflow=20     # 允许额外的连接数
)

# 创建异步会话工厂 方便后续调用 防止复写一堆参数
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,  # 告诉工厂用哪个连接池
    class_=AsyncSession,    # 告诉工厂造哪种 session
    expire_on_commit=False  # commit() 后对象属性还能直接读，不触发新查询，异步下更安全
)

# 依赖项，用于获取数据库对话
# async with：创建 session，退出时自动关闭。
# yield：把 session 交给 FastAPI，路由函数用它执行 SQL。
# except：路由抛异常时回滚，保证数据一致。
# raise：回滚后继续把异常抛出去，让 FastAPI 返回错误响应。
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
