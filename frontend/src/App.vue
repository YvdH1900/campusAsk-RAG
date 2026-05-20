<!--
  根组件 (App.vue)
  ================
  这是整个应用的根组件，所有其他组件的父组件。
  主要职责：
  1. 提供路由视图容器 (<router-view>)
  2. 定义全局样式
-->

<template>
  <!-- 
    router-view: 路由视图占位符
    当前路由匹配的组件会渲染到这个位置
    当路由变化时，router-view 中的内容会自动更新
  -->
  <router-view />
</template>

<!-- 
  script setup: Vue 3 组合式 API 语法糖
  这是推荐的组件编写方式，更简洁直观
  当前根组件不需要额外逻辑，所以为空
-->
<script setup lang="ts">
</script>

<!-- 
  全局样式
  注意：这里的样式没有 scoped 属性，会影响整个页面
  通常用于设置全局基础样式
-->
<style>
#app {
  width: 100%;
  height: 100vh;
  margin: 0;
  padding: 0;
  background: var(--bg-base);
}

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: var(--bg-base);
  color: var(--text-primary);
}

* {
  box-sizing: border-box;
}

*:focus {
  outline: none;
}

input:focus,
textarea:focus,
select:focus,
button:focus {
  outline: none;
}

.el-input__wrapper:focus-within {
  box-shadow: 0 0 0 3px var(--primary-glow) !important;
  border-color: var(--primary) !important;
}

.el-textarea__inner:focus {
  box-shadow: 0 0 0 3px var(--primary-glow) !important;
  border-color: var(--primary) !important;
}
</style>
