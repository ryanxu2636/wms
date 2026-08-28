import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../layout/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/sku',
    children: [
      {
        path: 'sku',
        name: 'SkuList',
        component: () => import('../views/SkuList.vue'),
        meta: { title: 'SKU 主数据' },
      },
      {
        path: 'import',
        name: 'ImportExcel',
        component: () => import('../views/ImportExcel.vue'),
        meta: { title: '订单导入' },
      },
      {
        path: 'rules',
        name: 'RuleList',
        component: () => import('../views/RuleList.vue'),
        meta: { title: '规则配置' },
      },
      {
        path: 'warehouse',
        name: 'Warehouse',
        component: () => import('../views/Warehouse.vue'),
        meta: { title: '库位管理' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} · WMS` : 'WMS 仓储管理系统'
  next()
})

export default router
