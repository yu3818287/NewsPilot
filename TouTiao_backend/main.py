import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import ai, comments, news, users, favorite, history
from fastapi.middleware.cors import CORSMiddleware

from utils.exception_handlers import register_exception_handlers
from config.db_conf import AsyncSessionLocal
from config.settings import settings
from services.bootstrap import bootstrap_database
from services.news_fetcher import sync_default_feeds


async def scheduled_news_sync():
    # Give user-triggered Agent requests priority immediately after startup.
    await asyncio.sleep(60)
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await sync_default_feeds(session)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[news-sync] {type(exc).__name__}: {exc}")
        await asyncio.sleep(settings.news_sync_interval_minutes * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bootstrap_database()
    settings.avatar_dir.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(scheduled_news_sync())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

app = FastAPI(title="NewsPilot API", version="2.0.0", lifespan=lifespan)

# 注册异常处理器
register_exception_handlers(app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # 允许携带cookie
    allow_methods=["*"],     # 允许的请求方法
    allow_headers=["*"],     # 允许的请求头
)


@app.get("/")
async def root():
    return {"message": "Hello World"}

# 挂载路由/注册路由
app.include_router(news.router)
app.include_router(users.router)
app.include_router(favorite.router)
app.include_router(history.router)
app.include_router(comments.router)
app.include_router(ai.router)
app.mount("/uploads", StaticFiles(directory=settings.avatar_dir.parent), name="uploads")
