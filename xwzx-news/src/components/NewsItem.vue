<template>
  <div class="news-item" @click="goToDetail">
    <div class="news-content">
      <h3 class="news-title">{{ news.title }}</h3>
      <span v-if="news.isAiFetched" class="ai-badge">AI 实时采集</span>
      <p class="news-desc">{{ news.description }}</p>
      <div class="news-info">
        <span>{{ news.author }}</span>
        <span>{{ news.publishTime }}</span>
        <span>{{ news.views }} 阅读</span>
      </div>
    </div>
    <div class="news-image" :data-label="news.image ? '' : 'NEWS'">
      <img v-if="news.image" :src="resolveImage(news.image)" :alt="news.title" @error="onImageError">
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'
import { useRouter } from 'vue-router'
import { apiConfig } from '../config/api'

const props = defineProps({
  news: {
    type: Object,
    required: true
  }
})

const router = useRouter()
const resolveImage = (value) => value?.startsWith('/') ? `${apiConfig.baseURL}${value}` : value
const onImageError = (event) => { event.target.style.display = 'none'; event.target.parentElement.dataset.label = 'NEWS' }

const goToDetail = () => {
  router.push(`/news/detail/${props.news.id}`)
}
</script>

<style scoped>
.news-item {
  display: flex;
  padding: 12px 16px;
  border-bottom: 1px solid #f2f2f2;
  background-color: #fff;
}

.news-content {
  flex: 1;
  margin-right: 12px;
  overflow: hidden;
}

.news-title {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 8px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.ai-badge {
  display: inline-block;
  margin: -2px 0 7px;
  padding: 2px 6px;
  color: #25755f;
  background: #e7f7f1;
  border-radius: 5px;
  font-size: 10px;
}

.news-desc {
  font-size: 14px;
  color: #666;
  margin: 0 0 8px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.news-info {
  font-size: 12px;
  color: #999;
  display: flex;
}

.news-info span {
  margin-right: 10px;
}

.news-image {
  width: 110px;
  height: 80px;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
  border-radius: 7px;
  background: linear-gradient(135deg, #dfe9f6, #b7c9df);
}

.news-image::after {
  content: attr(data-label);
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #67809b;
  font: 700 11px/1 monospace;
  letter-spacing: .16em;
}

.news-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
  position: relative;
  z-index: 1;
}
</style>
