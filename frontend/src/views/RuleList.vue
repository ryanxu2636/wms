<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button type="success" @click="openCreate">新增规则</el-button>
      </div>
      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="rule_key" label="规则 Key" min-width="220" />
        <el-table-column prop="rule_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.rule_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="match_mode" label="匹配" width="90" />
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column prop="enabled" label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="180" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" title="新增规则" width="500px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="规则 Key" required>
          <el-input v-model="form.rule_key" placeholder="如 YUN / CS99-No!!!!!!!!!!!!!" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.rule_type" style="width: 100%">
            <el-option label="虚拟（免拣免库存免面单）" value="虚拟" />
            <el-option label="拦截出库" value="拦截" />
            <el-option label="强制人工复核" value="复核" />
            <el-option label="采购跳过" value="采购跳过" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-select v-model="form.match_mode" style="width: 100%">
            <el-option label="精确" value="精确" />
            <el-option label="前缀" value="前缀" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listRules, createRule, deleteRule } from '../api'

const list = ref([])
const loading = ref(false)
const visible = ref(false)
const form = ref({ rule_key: '', rule_type: '虚拟', match_mode: '精确', priority: 1, description: '' })

async function fetch() {
  loading.value = true
  try {
    list.value = await listRules()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { rule_key: '', rule_type: '虚拟', match_mode: '精确', priority: 1, description: '' }
  visible.value = true
}

async function submit() {
  if (!form.value.rule_key) return ElMessage.warning('请填写规则 Key')
  try {
    await createRule(form.value)
    ElMessage.success('已创建')
    visible.value = false
    fetch()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除规则「${row.rule_key}」？`, '提示', { type: 'warning' })
  try {
    await deleteRule(row.id)
    ElMessage.success('已删除')
    fetch()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(fetch)
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}
</style>
