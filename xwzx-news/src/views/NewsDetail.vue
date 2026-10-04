<template>
  <div class="news-detail">
    <van-nav-bar
      title="新闻详情"
      left-text="返回"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="detail-content" v-if="newsStore.newsDetail.id">
      <div class="title-container">
        <h1 class="title">{{ newsStore.newsDetail.title }}</h1>
        <van-button 
          class="favorite-btn" 
          :icon="isFavorite ? 'star' : 'star-o'" 
          :class="{ 'is-favorite': isFavorite }"
          @click="toggleFavorite"
        />
      </div>
      
      <div class="info">
        <span>{{ newsStore.newsDetail.author }}</span>
        <span>{{ newsStore.newsDetail.publishTime }}</span>
        <span>{{ newsStore.newsDetail.views }} 阅读</span>
      </div>

      <div class="cover" v-if="newsStore.newsDetail.image">
        <img :src="resolveImage(newsStore.newsDetail.image)" :alt="newsStore.newsDetail.title">
      </div>

      <section v-if="newsStore.newsDetail.description" class="quick-read">
        <div class="quick-read-label"><van-icon name="clock-o" /> 30 秒读完</div>
        <p>{{ newsStore.newsDetail.description }}</p>
      </section>
      
      <div class="content">
        <p v-for="(paragraph, index) in contentParagraphs" :key="index">
          {{ paragraph }}
        </p>
      </div>

      <a v-if="newsStore.newsDetail.sourceUrl" class="source-link" :href="newsStore.newsDetail.sourceUrl" target="_blank" rel="noopener noreferrer">
        <van-icon name="link-o" /> 原始来源：{{ newsStore.newsDetail.sourceName || '查看媒体报道' }}（可选）
      </a>
      
      <div class="related-news" v-if="newsStore.newsDetail.relatedNews?.length">
        <h3>相关推荐</h3>
        <div class="related-list">
          <div 
            class="related-item" 
            v-for="item in newsStore.newsDetail.relatedNews" 
            :key="item.id"
            @click="goToRelatedNews(item.id)"
          >
            <div class="related-image" :data-label="item.image ? '' : 'NEWS'">
              <img v-if="item.image" :src="resolveImage(item.image)" :alt="item.title">
            </div>
            <div class="related-title">{{ item.title }}</div>
          </div>
        </div>
      </div>

      <comments-section :news-id="newsId" />
    </div>
    
    <van-empty v-else description="加载中..." />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNewsStore } from '../store/modules/news'
import { useHistoryStore } from '../store/modules/history'
import { useFavoriteStore } from '../store/modules/favorite'
import { useUserStore } from '../store/user'
import { showToast } from 'vant'
import CommentsSection from '../components/CommentsSection.vue'
import { apiConfig } from '../config/api'

const route = useRoute()
const router = useRouter()
const newsStore = useNewsStore()
const historyStore = useHistoryStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()
const resolveImage = (value) => value?.startsWith('/') ? `${apiConfig.baseURL}${value}` : value

// 获取路由参数中的新闻ID
const newsId = computed(() => Number(route.params.id))

// 将内容拆分为段落
const contentParagraphs = computed(() => {
  if (!newsStore.newsDetail.content) return []
  return newsStore.newsDetail.content.split('\n\n').filter(p => p.trim())
})

// 返回上一页
const onClickLeft = () => {
  router.back()
}

// 跳转到相关新闻
const goToRelatedNews = (id) => {
  router.push(`/news/detail/${id}`)
}

// 判断当前新闻是否已收藏
const isFavorite = computed(() => {
  return favoriteStore.isFavorite(newsId.value)
})

// 切换收藏状态
const toggleFavorite = async () => {
  // 判断用户是否已登录
  if (!userStore.getLoginStatus) {
    // 未登录则跳转到登录页
    showToast({
      message: '请先登录后再收藏',
      position: 'bottom',
    })
    router.push('/login')
    return
  }
  
  // 已登录则调用API切换收藏状态
  const status = await favoriteStore.toggleFavorite(newsStore.newsDetail)
  
  if (status === true) {
    showToast({
      message: '已添加到收藏',
      position: 'bottom',
    })
  } else if (status === false) {
    showToast({
      message: '已取消收藏',
      position: 'bottom',
    })
  } else {
    // status为null表示操作失败
    showToast({
      message: '操作失败，请稍后重试',
      position: 'bottom',
    })
  }
}

// 组件挂载时获取新闻详情并添加到浏览历史
onMounted(async () => {
  await newsStore.getNewsDetail(newsId.value)
  
  // 添加到浏览历史
  if (newsStore.newsDetail.id) {
    // 先调用API记录浏览历史
    if (userStore.getLoginStatus) {
      try {
        const result = await historyStore.addHistoryApi(newsStore.newsDetail.id);
        console.log('记录浏览历史API结果:', result);
      } catch (error) {
        console.error('记录浏览历史API失败:', error);
      }
    }
    
    // 无论API是否成功，都添加到本地浏览历史
    // historyStore.addHistory(newsStore.newsDetail);
  }
  
  // 加载收藏数据
  favoriteStore.loadFavorites()
  
  // 检查文章收藏状态
  if (userStore.getLoginStatus && newsStore.newsDetail.id) {
    const result = await favoriteStore.checkFavoriteStatusApi(newsStore.newsDetail.id)
    if (result.success && !result.isLocal) {
      // 如果API请求成功且不是本地状态，更新本地收藏状态
      if (result.isFavorite && !favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.addFavorite(newsStore.newsDetail)
      } else if (!result.isFavorite && favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.removeFavorite(newsStore.newsDetail.id)
      }
    }
  }
})
</script>

<style scoped>
.news-detail {
  padding-top: 46px;
  background-color: #fff;
  min-height: 100vh;
}

.detail-content {
  padding: 16px;
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin: 4px 0 16px;
  padding: 7px 10px;
  color: #2366f5;
  background: #eef4ff;
  border-radius: 8px;
  font-size: 12px;
  text-decoration: none;
}

.title-container {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title {
  font-size: 22px;
  font-weight: bold;
  line-height: 1.4;
  margin: 0;
  flex: 1;
}

.favorite-btn {
  flex-shrink: 0;
  margin-left: 10px;
  padding: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
}

.favorite-btn.is-favorite {
  color: #ff9500;
}

.info {
  display: flex;
  font-size: 12px;
  color: #999;
  margin-bottom: 16px;
}

.info span {
  margin-right: 12px;
}

.cover {
  margin-bottom: 16px;
}

.cover img {
  width: 100%;
  border-radius: 4px;
}

.quick-read {
  position: relative;
  margin: 2px 0 20px;
  padding: 15px 16px 15px 18px;
  overflow: hidden;
  color: #243b53;
  background: #eef5ff;
  border: 1px solid #d8e7fb;
  border-radius: 10px;
}

.quick-read::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #2366f5;
}

.quick-read-label {
  margin-bottom: 7px;
  color: #2366f5;
  font-size: 12px;
  font-weight: 700;
}

.quick-read p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}

.content {
  font-size: 16px;
  line-height: 1.8;
  color: #333;
}

.content p {
  margin-bottom: 16px;
  text-align: justify;
}

.related-news {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 8px solid #f5f5f5;
}

.related-news h3 {
  font-size: 18px;
  margin: 0 0 16px;
}

.related-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.related-item {
  display: flex;
  align-items: center;
}

.related-image {
  width: 80px;
  height: 60px;
  margin-right: 12px;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
  border-radius: 4px;
  background: linear-gradient(135deg, #dfe9f6, #b7c9df);
}

.related-image::after {
  content: attr(data-label);
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #67809b;
  font: 700 10px/1 monospace;
  letter-spacing: .14em;
}

.related-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
  position: relative;
  z-index: 1;
}

.related-title {
  font-size: 14px;
  line-height: 1.4;
  flex: 1;
}
</style>
