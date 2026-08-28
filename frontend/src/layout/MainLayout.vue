<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">WMS 仓储管理</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#c0c4cc" active-text-color="#ffffff">
        <el-menu-item index="/sku">
          <el-icon><Box /></el-icon>
          <span>SKU 主数据</span>
        </el-menu-item>
        <el-menu-item index="/import">
          <el-icon><Upload /></el-icon>
          <span>订单导入</span>
        </el-menu-item>
        <el-menu-item index="/rules">
          <el-icon><SetUp /></el-icon>
          <span>规则配置</span>
        </el-menu-item>
        <el-menu-item index="/warehouse">
          <el-icon><OfficeBuilding /></el-icon>
          <span>库位管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>{{ $route.meta.title }}</span>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
</script>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background-color: #001529;
}
.logo {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  padding: 18px 0;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}
.main {
  background: #f5f7fa;
}
</style>
