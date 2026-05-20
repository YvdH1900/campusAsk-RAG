/**
 * Vite 构建工具配置文件
 * ======================
 * Vite 是新一代前端构建工具，相比 Webpack 有显著优势：
 * 1. 开发服务器启动快（基于 ES Modules）
 * 2. 热更新速度快
 * 3. 开箱支持 TypeScript、CSS 预处理器等
 *
 * 本配置文件定义了：
 * 1. Vue 插件配置
 * 2. 路径别名（@ 指向 src 目录）
 * 3. 开发服务器配置（端口、代理）
 */

// ==================== 导入配置依赖 ====================
// defineConfig: Vite 配置辅助函数，提供类型提示
// vue: Vite 的 Vue 3 插件
// resolve: Node.js 路径解析模块，用于构建绝对路径
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'


// ==================== 导出 Vite 配置 ====================
// defineConfig: 包装配置对象，提供 TypeScript 类型推断
export default defineConfig({
  // ==================== 插件配置 ====================
  // plugins: 数组，包含所有要使用的 Vite 插件
  // vue(): 启用 Vue 3 单文件组件 (.vue) 支持
  plugins: [vue()],

  // ==================== 模块解析配置 ====================
  // resolve: 配置模块如何解析（导入）
  resolve: {
    // alias: 路径别名配置
    // 作用：简化导入路径，避免使用大量的 ../../
    //
    // 使用示例：
    //   不使用别名: import Button from '../../../components/Button.vue'
    //   使用别名后: import Button from '@/components/Button.vue'
    //
    // '@' 指向 src 目录，是社区约定俗成的别名
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },

  // ==================== CSS 预处理器配置 ====================
  // 使用 sass-embedded 的现代编译器 API，避免 legacy JS API 阻塞 Vite
  // 旧 API 在首次编译大型 SCSS 时同步阻塞 Node.js 事件循环，
  // 导致 API 代理请求挂起，后端表现为无响应
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler',
      },
    },
  },

  // ==================== 开发服务器配置 ====================
  // server: 配置开发环境下的 dev server
  server: {
    // port: 开发服务器监听的端口
    // 启动后访问 http://localhost:5173 查看应用
    port: 5173,

    // proxy: 代理配置
    // 作用：解决开发环境的跨域问题
    //
    // 工作原理：
    //   前端请求 http://localhost:5173/api/chat
    //   Vite 代理将请求转发到 http://localhost:8000/api/chat
    //   后端响应后，Vite 将响应返回给前端
    //
    // 这样前端不需要知道后端的真实地址，避免跨域问题
    proxy: {
      '/api': {
        // target: 代理目标地址（后端服务地址）
        target: 'http://localhost:8000',
        
        // changeOrigin: 修改请求头中的 Host 字段为目标地址
        // 某些后端服务会验证 Host 头，设置为 true 可以避免被拒绝
        changeOrigin: true,
      },
    },
  },
})
