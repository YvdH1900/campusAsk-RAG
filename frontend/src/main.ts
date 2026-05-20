/**
 * Vue 应用入口文件
 * ===============
 * 这是前端应用的主入口，负责：
 * 1. 创建 Vue 应用实例
 * 2. 注册全局插件（Pinia、Router、Element Plus）
 * 3. 注册 Element Plus 图标组件
 * 4. 挂载应用到 DOM
 */

// ==================== Vue 核心导入 ====================
// createApp: 创建 Vue 应用实例的工厂函数
import { createApp } from 'vue'

// ==================== 状态管理导入 ====================
// createPinia: 创建 Pinia 状态管理实例
// Pinia 是 Vue 3 官方推荐的状态管理库，替代 Vuex
import { createPinia } from 'pinia'

// ==================== UI 组件库导入 ====================
// ElementPlus: Element Plus 组件库主模块
// 'element-plus/dist/index.css': Element Plus 的样式文件
// zhCn: Element Plus 的中文语言包
// * as ElementPlusIconsVue: 导入所有 Element Plus 图标组件
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// ==================== 应用核心模块导入 ====================
// App: 根组件，所有其他组件的父组件
// router: Vue Router 路由实例，管理页面路由
import App from './App.vue'
import router from './router'
import './assets/global.css'

// ==================== 创建并配置应用 ====================
// createApp(App): 使用根组件创建应用实例
const app = createApp(App)

// 注册 Pinia 状态管理
// 注册后可以在组件中使用 defineStore 定义和使用状态
app.use(createPinia())

// 注册 Vue Router 路由
// 注册后可以使用 <router-view> 和 <router-link> 组件
app.use(router)

// 注册 Element Plus UI 组件库
// { locale: zhCn }: 设置组件库语言为中文
app.use(ElementPlus, { locale: zhCn })

// ==================== 注册 Element Plus 图标 ====================
// 遍历所有导入的图标组件，全局注册
// 注册后可以在模板中直接使用 <el-icon><Edit /></el-icon>
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// ==================== 挂载应用到 DOM ====================
// '#app': 选择器，对应 index.html 中的 <div id="app"></div>
// 应用将替换或挂载到这个元素上
app.mount('#app')
