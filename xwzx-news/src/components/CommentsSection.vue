<template>
  <section class="comments">
    <div class="comments-title">
      <h3>读者讨论</h3><span>{{ total }} 条</span>
    </div>
    <div class="comment-composer">
      <van-image round width="34" height="34" :src="currentAvatar" />
      <van-field v-model="content" rows="1" autosize type="textarea" maxlength="1000" placeholder="留下你的观点…" />
      <van-button size="small" type="primary" :loading="submitting" @click="submitComment">发布</van-button>
    </div>
    <van-empty v-if="!loading && !comments.length" image-size="64" description="还没有评论，来写第一条吧" />
    <article v-for="comment in comments" :key="comment.id" class="comment-item">
      <van-image round width="36" height="36" :src="resolveAvatar(comment.avatar)" />
      <div class="comment-body">
        <div class="comment-meta">
          <strong>{{ comment.nickname || comment.username }}</strong>
          <time>{{ formatTime(comment.createdAt) }}</time>
        </div>
        <p>{{ comment.content }}</p>
        <button v-if="comment.isMine" type="button" @click="removeComment(comment.id)">删除</button>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { showConfirmDialog, showFailToast, showSuccessToast, showToast } from 'vant'
import { useRouter } from 'vue-router'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'

const props = defineProps({ newsId: { type: Number, required: true } })
const router = useRouter()
const userStore = useUserStore()
const comments = ref([])
const total = ref(0)
const content = ref('')
const loading = ref(false)
const submitting = ref(false)
const headers = computed(() => userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {})
const resolveAvatar = (avatar) => {
  const value = avatar || 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
  return value.startsWith('/') ? `${apiConfig.baseURL}${value}` : value
}
const currentAvatar = computed(() => resolveAvatar(userStore.userInfo?.avatar))
const formatTime = (value) => new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })

const loadComments = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${apiConfig.baseURL}/api/news/${props.newsId}/comments`, { headers: headers.value })
    comments.value = response.data.data.list
    total.value = response.data.data.total
  } catch { showFailToast('评论加载失败') } finally { loading.value = false }
}
const submitComment = async () => {
  if (!userStore.getLoginStatus) {
    showToast('登录后才能评论')
    router.push('/login')
    return
  }
  if (!content.value.trim()) return
  submitting.value = true
  try {
    const response = await axios.post(`${apiConfig.baseURL}/api/news/${props.newsId}/comments`, { content: content.value.trim() }, { headers: headers.value })
    comments.value.unshift(response.data.data)
    total.value += 1
    content.value = ''
    showSuccessToast('评论成功')
  } catch (error) { showFailToast(error.response?.data?.detail || '评论失败') } finally { submitting.value = false }
}
const removeComment = async (id) => {
  try {
    await showConfirmDialog({ title: '删除评论', message: '确定删除这条评论吗？' })
    await axios.delete(`${apiConfig.baseURL}/api/news/comments/${id}`, { headers: headers.value })
    comments.value = comments.value.filter((item) => item.id !== id)
    total.value -= 1
  } catch (error) {
    if (error?.response) showFailToast('删除失败')
  }
}
onMounted(loadComments)
</script>

<style scoped>
.comments { margin-top:28px; padding-top:22px; border-top:8px solid #f4f7fb; }
.comments-title { display:flex; align-items:baseline; gap:8px; margin-bottom:16px; }
.comments-title h3 { font-family:"Songti SC",serif; font-size:20px; color:#102a43; }
.comments-title span { color:#8493a5; font-size:12px; }
.comment-composer { display:flex; align-items:flex-start; gap:8px; padding:10px; border:1px solid #dfe8f2; border-radius:14px; background:#f8fafc; }
.comment-composer :deep(.van-cell) { padding:5px 8px; background:transparent; }
.comment-item { display:flex; gap:10px; padding:17px 2px; border-bottom:1px solid #edf1f5; }
.comment-body { flex:1; min-width:0; }
.comment-meta { display:flex; justify-content:space-between; gap:8px; }
.comment-meta strong { color:#274863; font-size:13px; }
.comment-meta time { color:#9aa8b7; font-size:11px; }
.comment-body p { margin-top:7px; color:#334e68; font-size:14px; line-height:1.6; word-break:break-word; }
.comment-body button { float:right; margin-top:5px; border:0; color:#9a5960; background:transparent; font-size:11px; }
</style>
