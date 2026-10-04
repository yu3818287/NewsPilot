<template>
  <div class="agent-page">
    <div v-if="historyOpen" class="drawer-backdrop" @click="historyOpen = false"></div>
    <aside :class="['history-drawer', { open: historyOpen }]" aria-label="对话记录">
      <div class="drawer-header">
        <div><span>MY NEWS DESK</span><h2>对话案卷</h2></div>
        <button type="button" aria-label="关闭对话记录" @click="historyOpen = false"><van-icon name="cross" /></button>
      </div>
      <div v-if="!userStore.getLoginStatus" class="login-notice">
        <van-icon name="contact-o" />
        <strong>登录后保存全部对话</strong>
        <p>问答内容、新闻来源和检索过程都会跟随你的账号。</p>
        <button type="button" @click="$router.push('/login')">去登录</button>
      </div>
      <div v-else-if="historyLoading" class="history-state">正在整理你的案卷…</div>
      <div v-else-if="!conversations.length" class="history-state">还没有历史对话，从一个问题开始吧。</div>
      <div v-else class="history-list">
        <article v-for="item in conversations" :key="item.id" :class="['history-item', { active: item.id === conversationId }]">
          <button class="history-main" type="button" @click="openConversation(item.id)">
            <strong>{{ item.title }}</strong><span>{{ item.preview }}</span>
            <small>{{ formatHistoryTime(item.updatedAt) }} · {{ item.messageCount }} 条消息</small>
          </button>
          <button class="history-delete" type="button" aria-label="删除这条对话" @click="removeConversation(item)"><van-icon name="delete-o" /></button>
        </article>
      </div>
    </aside>

    <header class="agent-header">
      <div class="headline-copy">
        <p class="eyebrow"><span class="live-dot"></span> NEWS AGENT · 2026</p>
        <h1>让新闻自己来找你</h1>
        <p class="subtitle">实时检索、入库、筛选，再用本地新闻库回答。</p>
      </div>
      <div class="header-actions">
        <button type="button" aria-label="打开对话记录" @click="openHistory"><van-icon name="records-o" /><b v-if="conversations.length">{{ conversations.length }}</b></button>
        <button class="new-chat-button" type="button" aria-label="新建对话" @click="newConversation"><van-icon name="plus" /></button>
      </div>
    </header>

    <main ref="messagesContainer" class="conversation">
      <section v-if="messages.length === 1" class="starter-panel">
        <div class="current-file"><span>NEW FILE</span><strong>新对话</strong></div>
        <span class="starter-label">你可以这样问</span>
        <button v-for="prompt in quickPrompts" :key="prompt" type="button" class="prompt-card" @click="usePrompt(prompt)"><span>{{ prompt }}</span><van-icon name="arrow" /></button>
      </section>
      <article v-for="(message, index) in messages" :key="index" :class="['message-row', message.role]">
        <div v-if="message.role === 'assistant'" class="agent-mark">AI</div>
        <div class="bubble">
          <div v-if="message.pending" class="thinking"><span></span><span></span><span></span><em>正在检索新闻库</em></div>
          <div v-else class="markdown" v-html="formatMessage(message.content)"></div>
          <div v-if="message.actions?.length" class="action-trace"><span v-for="action in message.actions" :key="action"><van-icon name="passed" /> {{ action }}</span></div>
          <div v-if="message.sources?.length" class="source-list">
            <p>本次参考</p>
            <button v-for="source in message.sources.slice(0, 5)" :key="source.id" type="button" @click="$router.push(`/news/detail/${source.id}`)">
              <strong>{{ source.title }}</strong><small>{{ source.source || '本地新闻库' }} · {{ formatDate(source.publishTime) }}</small>
            </button>
          </div>
        </div>
      </article>
    </main>

    <footer class="composer-shell">
      <div class="composer">
        <textarea v-model="userInput" rows="1" maxlength="4000" placeholder="例如：最近三个月人工智能领域有哪些进展？" @keydown.enter.exact.prevent="sendMessage"></textarea>
        <button type="button" class="send-button" :disabled="isLoading || !userInput.trim()" @click="sendMessage"><van-icon name="guide-o" /></button>
      </div>
      <p>{{ userStore.getLoginStatus ? '已登录 · 对话自动保存' : '游客模式 · 登录后可永久保存' }} · DeepSeek V4.1 Flash</p>
    </footer>
    <tab-bar />
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import axios from 'axios'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import TabBar from '../components/TabBar.vue'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'

const userStore = useUserStore()
const messagesContainer = ref(null)
const userInput = ref('')
const isLoading = ref(false)
const historyLoading = ref(false)
const historyOpen = ref(false)
const conversationId = ref(null)
const conversations = ref([])
const quickPrompts = ['推荐今天最值得关注的国内和国际新闻', '最近三个月人工智能领域有哪些重要进展？', '对比不同媒体对同一热点事件的报道差异']
const welcomeMessage = { role: 'assistant', transient: true, content: '你好，我是你的 **AI 新闻编辑**。我会先搜索和更新 2026 年新闻，再用本地新闻库回答；登录后，每次对话都会保存在你的个人案卷中。' }
const messages = ref([{ ...welcomeMessage }])

marked.setOptions({ breaks: true, gfm: true })
const authHeaders = () => userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {}
const storageKey = () => `news-agent-active:${userStore.userInfo?.id || userStore.userInfo?.username || 'guest'}`
const formatMessage = (content) => DOMPurify.sanitize(marked.parse(content || ''))
const formatDate = (value) => value ? new Date(value).toLocaleDateString('zh-CN') : ''
const formatHistoryTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  const today = new Date()
  return date.toDateString() === today.toDateString() ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}
const scrollToBottom = async () => { await nextTick(); if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight }
const usePrompt = (prompt) => { userInput.value = prompt; sendMessage() }

const loadConversations = async () => {
  if (!userStore.getLoginStatus) return
  historyLoading.value = true
  try {
    const response = await axios.get(`${apiConfig.baseURL}/api/ai/conversations`, { headers: authHeaders() })
    conversations.value = response.data.data.list || []
  } catch (error) {
    if (error.response?.status !== 401) showFailToast('对话记录加载失败')
  } finally { historyLoading.value = false }
}

const openConversation = async (id, closeDrawer = true) => {
  if (!id || isLoading.value) return
  try {
    const response = await axios.get(`${apiConfig.baseURL}/api/ai/conversations/${id}`, { headers: authHeaders() })
    conversationId.value = id
    messages.value = response.data.data.messages?.length ? response.data.data.messages : [{ ...welcomeMessage }]
    localStorage.setItem(storageKey(), id)
    if (closeDrawer) historyOpen.value = false
    await scrollToBottom()
  } catch (error) {
    localStorage.removeItem(storageKey())
    showFailToast(error.response?.data?.detail || '这条对话无法打开')
  }
}

const initializeHistory = async () => {
  conversations.value = []; conversationId.value = null; messages.value = [{ ...welcomeMessage }]
  if (!userStore.getLoginStatus) return
  await loadConversations()
  const savedId = localStorage.getItem(storageKey())
  const target = conversations.value.find(item => item.id === savedId)?.id || conversations.value[0]?.id
  if (target) await openConversation(target, false)
}

const newConversation = async () => {
  if (isLoading.value) return
  conversationId.value = null; messages.value = [{ ...welcomeMessage }]; userInput.value = ''; historyOpen.value = false
  localStorage.removeItem(storageKey())
  if (userStore.getLoginStatus) {
    try {
      const response = await axios.post(`${apiConfig.baseURL}/api/ai/conversations`, {}, { headers: authHeaders() })
      conversationId.value = response.data.data.conversationId
      localStorage.setItem(storageKey(), conversationId.value)
    } catch { showFailToast('新对话创建失败，请重试') }
  }
  await scrollToBottom()
}

const openHistory = async () => { historyOpen.value = true; if (userStore.getLoginStatus) await loadConversations() }
const removeConversation = async (item) => {
  try {
    await showConfirmDialog({ title: '删除这条对话？', message: '该对话中的提问、回答和新闻来源都会被删除。' })
    await axios.delete(`${apiConfig.baseURL}/api/ai/conversations/${item.id}`, { headers: authHeaders() })
    if (conversationId.value === item.id) await newConversation()
    await loadConversations(); showSuccessToast('对话已删除')
  } catch (error) {
    if (error !== 'cancel' && error?.message !== 'cancel' && error?.response) showFailToast(error.response.data?.detail || '删除失败')
  }
}

const sendMessage = async () => {
  const content = userInput.value.trim()
  if (!content || isLoading.value) return
  const history = messages.value.filter(message => !message.pending && !message.transient).slice(-10).map(({ role, content: text }) => ({ role, content: text }))
  messages.value.push({ role: 'user', content }, { role: 'assistant', content: '', pending: true })
  userInput.value = ''; isLoading.value = true; await scrollToBottom()
  try {
    const response = await axios.post(`${apiConfig.baseURL}/api/ai/chat`, { message: content, conversationId: conversationId.value, history }, { headers: authHeaders() })
    const result = response.data.data
    conversationId.value = result.conversationId
    localStorage.setItem(storageKey(), conversationId.value)
    messages.value[messages.value.length - 1] = { role: 'assistant', content: result.answer, sources: result.sources, actions: result.actions }
    if (userStore.getLoginStatus) await loadConversations()
  } catch (error) {
    const message = error.response?.data?.message || error.response?.data?.detail || 'AI 服务连接失败，请稍后再试'
    messages.value[messages.value.length - 1] = { role: 'assistant', content: message }; showFailToast(message)
  } finally { isLoading.value = false; await scrollToBottom() }
}

watch(() => userStore.token, initializeHistory, { immediate: true })
</script>

<style scoped>
.agent-page { --ink:#102a43; --blue:#2366f5; --mint:#24aa8a; min-height:100vh; height:100vh; display:flex; flex-direction:column; color:var(--ink); background:#f4f7fb; padding-bottom:50px; }
.agent-header { padding:20px 16px 17px 20px; color:#fff; background:linear-gradient(135deg,#0d2744 0%,#173f76 62%,#2366f5 100%); display:flex; align-items:flex-start; justify-content:space-between; box-shadow:0 8px 28px rgba(16,42,67,.2); }
.headline-copy { min-width:0; padding-right:10px; }.eyebrow { font-size:10px; letter-spacing:.14em; opacity:.82; margin-bottom:7px; }
.live-dot { display:inline-block; width:7px; height:7px; margin-right:6px; border-radius:50%; background:#55e6ba; box-shadow:0 0 0 4px rgba(85,230,186,.14); }
.agent-header h1 { font-family:"Songti SC","Noto Serif SC",serif; font-size:24px; line-height:1.25; letter-spacing:-.02em; }.subtitle { margin-top:7px; font-size:12px; color:rgba(255,255,255,.72); }
.header-actions { display:flex; gap:7px; }.header-actions button,.drawer-header button { position:relative; width:36px; height:36px; border:1px solid rgba(255,255,255,.22); border-radius:11px; color:#fff; background:rgba(255,255,255,.08); }
.header-actions button b { position:absolute; top:-6px; right:-5px; min-width:16px; height:16px; padding:0 4px; display:grid; place-items:center; border-radius:8px; color:#16395e; background:#62e6bd; font-size:9px; }.header-actions .new-chat-button { color:#13395f; background:#62e6bd; border-color:#62e6bd; }
.conversation { flex:1; overflow-y:auto; padding:18px 14px 24px; scroll-behavior:smooth; }.starter-panel { margin:0 0 22px 44px; }
.current-file { display:flex; align-items:center; gap:8px; margin-bottom:15px; padding-bottom:10px; border-bottom:1px solid #d9e2ec; }.current-file span { padding:3px 6px; color:#fff; background:var(--ink); font:700 9px/1 monospace; letter-spacing:.12em; }.current-file strong { font-family:"Songti SC",serif; font-size:17px; }
.starter-label { display:block; margin-bottom:8px; color:#70839a; font-size:12px; }.prompt-card { width:100%; padding:12px 14px; margin-bottom:8px; display:flex; justify-content:space-between; gap:12px; text-align:left; color:var(--ink); background:#fff; border:1px solid #dfe8f2; border-radius:14px; box-shadow:0 4px 12px rgba(34,67,101,.05); }
.message-row { display:flex; gap:9px; margin-bottom:18px; align-items:flex-start; }.message-row.user { justify-content:flex-end; }.agent-mark { flex:0 0 34px; height:34px; display:grid; place-items:center; color:white; background:var(--blue); border-radius:11px 11px 11px 4px; font-size:11px; font-weight:800; box-shadow:0 5px 12px rgba(35,102,245,.25); }
.bubble { max-width:calc(100% - 48px); padding:12px 14px; border-radius:4px 17px 17px 17px; background:#fff; box-shadow:0 5px 18px rgba(34,67,101,.08); font-size:14px; line-height:1.65; }.user .bubble { color:#fff; background:var(--blue); border-radius:17px 17px 4px 17px; box-shadow:0 5px 16px rgba(35,102,245,.2); }
.markdown :deep(p) { margin:0 0 8px; }.markdown :deep(p:last-child) { margin-bottom:0; }.markdown :deep(ul),.markdown :deep(ol) { padding-left:20px; }.markdown :deep(a) { color:var(--blue); }
.thinking { display:flex; align-items:center; gap:4px; color:#6b7e93; }.thinking span { width:6px; height:6px; border-radius:50%; background:var(--mint); animation:pulse 1.1s infinite ease-in-out; }.thinking span:nth-child(2) { animation-delay:.14s; }.thinking span:nth-child(3) { animation-delay:.28s; }.thinking em { margin-left:6px; font-style:normal; font-size:12px; }
@keyframes pulse { 0%,70%,100% { opacity:.3; transform:translateY(0); } 35% { opacity:1; transform:translateY(-3px); } }.action-trace { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; padding-top:10px; border-top:1px solid #edf1f5; }.action-trace span { padding:4px 7px; color:#347967; background:#e9f8f3; border-radius:7px; font-size:10px; }
.source-list { margin-top:12px; }.source-list p { color:#7b8ca0; font-size:11px; margin-bottom:6px; }.source-list button { width:100%; display:block; padding:9px 0; text-align:left; border:0; border-top:1px solid #edf1f5; color:var(--ink); background:transparent; }.source-list strong { display:block; font-size:12px; line-height:1.45; }.source-list small { display:block; margin-top:3px; color:#8493a5; }
.composer-shell { padding:10px 12px 7px; background:rgba(244,247,251,.95); border-top:1px solid #e1e8f0; backdrop-filter:blur(10px); }.composer { display:flex; gap:8px; align-items:flex-end; padding:7px 7px 7px 14px; background:#fff; border:1px solid #d9e2ec; border-radius:17px; box-shadow:0 5px 18px rgba(34,67,101,.08); }.composer textarea { flex:1; max-height:100px; min-height:36px; resize:none; border:0; outline:none; padding:8px 0; color:var(--ink); background:transparent; font:inherit; line-height:1.4; }.send-button { flex:0 0 40px; height:40px; border:0; border-radius:13px; color:#fff; background:var(--blue); font-size:18px; }.send-button:disabled { background:#b9c7d8; }.composer-shell>p { margin-top:5px; text-align:center; color:#8a99aa; font-size:9px; letter-spacing:.04em; }
.drawer-backdrop { position:fixed; inset:0; z-index:1900; background:rgba(7,24,42,.48); backdrop-filter:blur(2px); }.history-drawer { position:fixed; z-index:1901; inset:0 auto 0 0; width:min(86vw,340px); display:flex; flex-direction:column; color:var(--ink); background:#f8fafc; box-shadow:16px 0 50px rgba(4,24,44,.22); transform:translateX(-105%); transition:transform .24s ease; }.history-drawer.open { transform:translateX(0); }
.drawer-header { min-height:94px; padding:20px 16px 16px 22px; display:flex; align-items:flex-start; justify-content:space-between; color:#fff; background:#102a43; border-left:6px solid #62e6bd; }.drawer-header span { display:block; margin-bottom:6px; color:#62e6bd; font:700 9px/1 monospace; letter-spacing:.16em; }.drawer-header h2 { font:700 23px/1.2 "Songti SC",serif; }
.history-list { flex:1; overflow-y:auto; padding:12px; }.history-item { position:relative; display:flex; margin-bottom:9px; overflow:hidden; background:#fff; border:1px solid #e1e8f0; border-radius:12px; }.history-item::before { content:""; width:4px; flex:0 0 4px; background:#d9e3ee; }.history-item.active { border-color:#7ca4ff; box-shadow:0 5px 18px rgba(35,102,245,.1); }.history-item.active::before { background:var(--blue); }
.history-main { flex:1; min-width:0; padding:12px 6px 11px 11px; text-align:left; color:inherit; background:transparent; border:0; }.history-main strong,.history-main span,.history-main small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.history-main strong { font-size:13px; }.history-main span { margin-top:5px; color:#70839a; font-size:11px; }.history-main small { margin-top:7px; color:#9aa8b8; font-size:9px; }.history-delete { align-self:center; flex:0 0 38px; height:38px; color:#9aa8b8; background:transparent; border:0; }
.history-state,.login-notice { margin:18px; padding:20px; color:#70839a; background:#fff; border:1px dashed #cbd8e5; border-radius:14px; text-align:center; font-size:12px; }.login-notice>i { display:block; margin-bottom:10px; color:var(--blue); font-size:28px; }.login-notice strong { display:block; color:var(--ink); font-size:14px; }.login-notice p { margin:7px 0 14px; line-height:1.6; }.login-notice button { padding:8px 18px; color:#fff; background:var(--blue); border:0; border-radius:9px; }
@media (prefers-reduced-motion:reduce) { .thinking span { animation:none; }.conversation { scroll-behavior:auto; }.history-drawer { transition:none; } }
</style>
