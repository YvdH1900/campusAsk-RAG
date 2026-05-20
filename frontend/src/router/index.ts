/**
 * Vue Router 路由配置文件
 * ========================
 * 定义应用的所有路由规则，包括：
 * 1. 路由路径与组件的映射关系
 * 2. 路由嵌套（布局组件 + 页面组件）
 * 3. 路由守卫（权限验证）
 * 4. 路由懒加载（按需加载组件）
 */

// ==================== Vue Router 核心导入 ====================
// createRouter: 创建路由实例的工厂函数
// createWebHistory: 使用 HTML5 History 模式（URL 不带 # 号）
// RouteRecordRaw: 路由配置的类型定义
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/History.vue'),
      },
      {
        path: 'documents',
        name: 'TeacherDocuments',
        component: () => import('@/views/TeacherDocuments.vue'),
        meta: { requiresAuth: true, requiresTeacher: true },
      },
    ],
  },

  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },

  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPassword.vue'),
  },

  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/ResetPassword.vue'),
  },

  {
    path: '/profile',
    component: () => import('@/layouts/ProfileLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
      },
    ],
  },

  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { 
      requiresAuth: true,
      requiresAdmin: true,
    },
    children: [
      {
        path: '',
        name: 'AdminDashboard',
        component: () => import('@/views/Admin/Dashboard.vue'),
      },
      {
        path: 'documents',
        name: 'AdminDocuments',
        component: () => import('@/views/Admin/Documents.vue'),
      },
      {
        path: 'upload',
        name: 'AdminUpload',
        component: () => import('@/views/Admin/Upload.vue'),
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/Admin/Users.vue'),
      },
      {
        path: 'site',
        name: 'AdminSite',
        component: () => import('@/views/Admin/SiteManagement.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const token = sessionStorage.getItem('token')
  
  console.log(`Route guard: navigating to ${to.path} from ${from.path}`)
  console.log(`Route guard: token exists: ${!!token}, user exists: ${!!userStore.user}`)
  
  if (to.meta.requiresAuth && !token) {
    console.log('Route guard: no token, redirect to Login')
    next({ name: 'Login' })
    return
  }
  
  if (token && !userStore.user) {
    console.log('Route guard: token exists but no user, fetching user...')
    try {
      await userStore.fetchUser()
      console.log('Route guard: user fetched successfully')
    } catch (error) {
      console.error('Route guard: Failed to fetch user:', error)
      userStore.logout()
      next({ name: 'Login' })
      return
    }
  }
  
  if (to.meta.requiresAdmin) {
    console.log('Route guard: checking admin requirement')
    if (!userStore.user) {
      console.log('Route guard: no user, redirect to Login')
      next({ name: 'Login' })
      return
    }
    const role = userStore.user.role?.toLowerCase() || ''
    console.log(`Route guard: user role is ${role}`)
    if (role !== 'admin') {
      console.log(`Route guard: User role is ${role}, not admin, redirect to Home`)
      next({ name: 'Home' })
      return
    }
    console.log('Route guard: admin check passed')
  }
  
  if (to.meta.requiresTeacher) {
    const role = userStore.user?.role?.toLowerCase() || ''
    if (role !== 'teacher' && role !== 'admin') {
      next({ name: 'Home' })
      return
    }
  }
  
  console.log('Route guard: all checks passed, proceeding to next route')
  next()
})

export default router
