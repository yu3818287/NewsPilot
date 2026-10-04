/**
 * API配置文件
 * 包含API基础URL和AI问答功能所需的API参数
 */

// API基础URL配置
export const apiConfig = {
  // 后端API基础URL（与 uvicorn --port 8001 保持一致）
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001',
}
