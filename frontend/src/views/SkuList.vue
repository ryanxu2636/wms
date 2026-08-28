<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索 SKU 编码 / 名称" clearable style="width: 260px" @keyup.enter="fetch" />
        <el-select v-model="skuType" placeholder="类型" clearable style="width: 140px" @change="fetch">
          <el-option label="基础" value="基础" />
          <el-option label="组合" value="组合" />
          <el-option label="虚拟" value="虚拟" />
          <el-option label="标记" value="标记" />
        </el-select>
        <el-button type="primary" @click="fetch">查询</el-button>
        <el-button type="success" @click="openCreate">新增 SKU</el-button>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="sku_code" label="SKU 编码" min-width="220" />
        <el-table-column prop="name" label="中文名称" min-width="160" />
        <el-table-column prop="sku_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.sku_type)">{{ row.sku_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="openBom(row)" v-if="row.sku_type === '组合'">BOM</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新增 SKU" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="SKU 编码" required>
          <el-input v-model="form.sku_code" placeholder="含空格/特殊字符请原样保留" />
        </el-form-item>
        <el-form-item label="中文名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.sku_type" style="width: 100%">
            <el-option label="基础" value="基础" />
            <el-option label="组合" value="组合" />
            <el-option label="虚拟" value="虚拟" />
            <el-option label="标记" value="标记" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片 URL">
          <el-input v-model="form.image_url" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="bomVisible" :title="`BOM：${current?.sku_code}`" width="520px">
      <el-form :model="bomForm" label-width="90px">
        <el-form-item label="子 SKU" required>
          <el-input v-model="bomForm.component_sku_code" placeholder="子 SKU 编码" />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="bomForm.qty" :min="1" />
        </el-form-item>
      </el-form>
      <div class="bom-tip">注：组合 SKU 名可含 `*`，BOM 导入时按「最后一个 *」切分数量。</div>
      <template #footer>
        <el-button @click="bomVisible = false">关闭</el-button>
        <el-button type="primary" @click="submitBom">添加组件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listSkus, createSku, createBom } from '../api'

const list = ref([])
const loading = ref(false)
const keyword = ref('')
const skuType = ref('')

const createVisible = ref(false)
const form = ref({ sku_code: '', name: '', sku_type: '基础', image_url: '' })

const bomVisible = ref(false)
const current = ref(null)
const bomForm = ref({ component_sku_code: '', qty: 1 })

function typeTag(t) {
  return { 基础: '', 组合: 'warning', 虚拟: 'info', 标记: 'danger' }[t] || ''
}

async function fetch() {
  loading.value = true
  try {
    list.value = await listSkus({ keyword: keyword.value || undefined, sku_type: skuType.value || undefined })
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { sku_code: '', name: '', sku_type: '基础', image_url: '' }
  createVisible.value = true
}

async function submitCreate() {
  if (!form.value.sku_code) return ElMessage.warning('请填写 SKU 编码')
  try {
    await createSku(form.value)
    ElMessage.success('已创建')
    createVisible.value = false
    fetch()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function openBom(row) {
  current.value = row
  bomForm.value = { component_sku_code: '', qty: 1 }
  bomVisible.value = true
}

async function submitBom() {
  if (!bomForm.value.component_sku_code) return ElMessage.warning('请填写子 SKU')
  try {
    await createBom({
      combo_sku_code: current.value.sku_code,
      components: [bomForm.value],
    })
    ElMessage.success('BOM 组件已添加')
    bomForm.value = { component_sku_code: '', qty: 1 }
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(fetch)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.bom-tip {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}
</style>
