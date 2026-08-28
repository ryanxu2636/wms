<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button type="success" @click="openWarehouse">新增仓库</el-button>
        <el-button type="primary" @click="openShelf">新增货架</el-button>
        <el-button type="primary" @click="openLocation">新增库位</el-button>
      </div>

      <el-tabs v-model="tab">
        <el-tab-pane label="仓库" name="wh">
          <el-table :data="warehouses" border stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="name" label="名称" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="库位" name="loc">
          <el-table :data="locations" border stripe v-loading="loadingLoc">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="code" label="库位码（货架-列-层）" min-width="160" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag>{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="whVisible" title="新增仓库" width="400px">
      <el-form :model="whForm" label-width="70px">
        <el-form-item label="编码" required><el-input v-model="whForm.code" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="whForm.name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="whVisible = false">取消</el-button>
        <el-button type="primary" @click="submitWh">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="shelfVisible" title="新增货架" width="400px">
      <el-form :model="shelfForm" label-width="90px">
        <el-form-item label="仓库" required>
          <el-select v-model="shelfForm.warehouse_id" style="width: 100%">
            <el-option v-for="w in warehouses" :key="w.id" :label="`${w.code} - ${w.name}`" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="货架编码" required><el-input v-model="shelfForm.code" placeholder="如 A07" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shelfVisible = false">取消</el-button>
        <el-button type="primary" @click="submitShelf">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="locVisible" title="新增库位" width="400px">
      <el-form :model="locForm" label-width="90px">
        <el-form-item label="仓库" required>
          <el-select v-model="locForm.warehouse_id" style="width: 100%" @change="fetchShelves">
            <el-option v-for="w in warehouses" :key="w.id" :label="`${w.code} - ${w.name}`" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="货架" required>
          <el-select v-model="locForm.shelf_id" style="width: 100%">
            <el-option v-for="s in shelves" :key="s.id" :label="s.code" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="库位码" required><el-input v-model="locForm.code" placeholder="如 A07-03-04" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="locVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLoc">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listWarehouses, listLocations, createWarehouse, createShelf, createLocation } from '../api'

const tab = ref('wh')
const warehouses = ref([])
const locations = ref([])
const shelves = ref([])
const loadingLoc = ref(false)

const whVisible = ref(false)
const whForm = ref({ code: '', name: '' })
const shelfVisible = ref(false)
const shelfForm = ref({ warehouse_id: null, code: '' })
const locVisible = ref(false)
const locForm = ref({ warehouse_id: null, shelf_id: null, code: '' })

async function fetchWh() {
  warehouses.value = await listWarehouses()
}
async function fetchLoc() {
  loadingLoc.value = true
  try {
    locations.value = await listLocations()
  } finally {
    loadingLoc.value = false
  }
}
async function fetchShelves() {
  // 简化为从后端取；这里直接用仓库下的货架（P0 简化，货架列表接口后续补）
  shelves.value = []
}

function openWarehouse() {
  whForm.value = { code: '', name: '' }
  whVisible.value = true
}
function openShelf() {
  shelfForm.value = { warehouse_id: null, code: '' }
  shelfVisible.value = true
}
function openLocation() {
  locForm.value = { warehouse_id: null, shelf_id: null, code: '' }
  locVisible.value = true
}

async function submitWh() {
  try {
    await createWarehouse(whForm.value)
    ElMessage.success('已创建')
    whVisible.value = false
    fetchWh()
  } catch (e) {
    ElMessage.error(e.message)
  }
}
async function submitShelf() {
  try {
    await createShelf(shelfForm.value)
    ElMessage.success('已创建')
    shelfVisible.value = false
  } catch (e) {
    ElMessage.error(e.message)
  }
}
async function submitLoc() {
  try {
    await createLocation(locForm.value)
    ElMessage.success('已创建')
    locVisible.value = false
    fetchLoc()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(() => {
  fetchWh()
  fetchLoc()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
