from fastapi import APIRouter, Depends, Query, HTTPException
from config.db_conf import get_db
from crud import news
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


# 接口实现流程
# 1.模块化路由 -> API 接口规范文档
# 2.定义模型类 -> 数据库表
# 3.在crud文件里面创建新文件 封装操作数据库的方法
# 4.在路由处理函数里面调用crud封装好的方法，响应结果

# 参1：这个 router 下所有接口都会自动加上 /api/news 前缀
# 参2：地址 /docs 里，这些接口会归到 news 分组下，方便查看
router = APIRouter(prefix="/api/news", tags=["news"])


def serialize_news_item(item):
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "image": item.image,
        "author": item.author,
        "categoryId": item.category_id,
        "views": item.views,
        "publishTime": item.publish_time,
        "sourceUrl": item.source_url,
        "sourceName": item.source_name,
        "isAiFetched": item.is_ai_fetched,
    }


# 装饰器：使用get方法访问 路径为/categories 最终路径为/api/news/categories
@router.get("/categories")
async def get_categories(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    # 先获取数据库的新闻分类数据 -> 先定义模型类 -> 封装查询数据的方法
    categories = await news.get_categories(db, skip, limit)
    return {
        "code": 200,
        "message": "获取分类成功",
        "data": categories
    }

@router.get("/list")
async def get_news_list(
        category_id: int = Query(..., alias="categoryId"),
        page: int = 1,
        page_size: int = Query(10, alias="pageSize", le=100),
        db: AsyncSession = Depends(get_db)
):
    # 思路：处理分页规则 → 查询新闻列表 → 计算总量 → 计算是否还有更多
    offset = (page - 1) * page_size
    news_list = await news.get_news_list(db, category_id, offset, page_size)
    total = await news.get_news_count(db, category_id)
    # (跳过的 + 当前列表里面的数量) < 总量
    has_more = (offset + len(news_list)) < total
    return {
        "code": 200,
        "message": "获取新闻列表成功",
        "data": {
            "list": [serialize_news_item(item) for item in news_list],
            "total": total,
            "hasMore": has_more
        }
    }


@router.get("/detail")
async def get_news_detail(news_id: int = Query(..., alias="id"), db: AsyncSession = Depends(get_db)):
    # 获取新闻详情 + 浏览量+1 + 相关新闻
    news_detail = await news.get_news_detail(db, news_id)
    if not news_detail:
        raise HTTPException(status_code=404, detail="新闻不存在")

    views_res = await news.increase_news_views(db, news_detail.id)
    if not views_res:
        raise HTTPException(status_code=404, detail="新闻不存在")

    related_news = await news.get_related_news(db, news_detail.id, news_detail.category_id)

    return {
      "code": 200,
      "message": "success",
      "data": {
        "id": news_detail.id,
        "title": news_detail.title,
        "description": news_detail.description,
        "content": news_detail.content,
        "image": news_detail.image,
        "author": news_detail.author,
        "publishTime": news_detail.publish_time,
        "categoryId": news_detail.category_id,
        "views": news_detail.views,
        "sourceUrl": news_detail.source_url,
        "sourceName": news_detail.source_name,
        "isAiFetched": news_detail.is_ai_fetched,
        "relatedNews": related_news
      }
    }
