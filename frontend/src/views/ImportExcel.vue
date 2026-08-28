<template>
  <div>
    <!-- 上传区 -->
    <el-card>
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        :on-change="onFileChange"
        :on-remove="() => (file = null)"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽订单 Excel 到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">店小秘订单导出模板（.xlsx），支持形态 A/B、YUN 虚拟品、标记 SKU</div>
        </template>
      </el-upload>
      <div class="actions">
        <el-button type="primary" :disabled="!file" :loading="previewing" @click="doPreview">解析预览</el-button>
      </div>
    </el-card>

    <!-- 预览结果 -->
    <el-card v-if="preview" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>预览结果</span>
          <div>
            <el-tag type="success">正常 {{ preview.normal_count }}</el-tag>
            <el-tag type="warning" style="margin-left: 8px">复核 {{ preview.review_count }}</el-tag>
            <el-tag type="danger" style="margin-left: 8px">错误 {{ preview.error_count }}</el-tag>
            <el-button type="success" style="margin-left: 16px" :loading="committing" @click="doCommit">确认导入</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="tab">
        <el-tab-pane :label="`正常明细 (${preview.items.length})`" name="normal">
          <el-table :data="preview.items" border stripe max-height="400">
            <el-table-column prop="package_no" label="包裹号" width="150" />
            <el-table-column prop="sku" label="SKU" min-width="200" />
            <el-table-column prop="qty" label="数量" width="80" />
            <el-table-column prop="tracking_no" label="运单号" width="140" />
            <el-table-column label="规则" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.rule_action" type="info">{{ row.rule_action }}</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`待复核 (${preview.reviews.length})`" name="review">
          <el-table :data="preview.reviews" border stripe max-height="400">
            <el-table-column prop="package_no" label="包裹号" width="150" />
            <el-table-column prop="sku" label="SKU" min-width="200" />
            <el-table-column label="原因" min-width="260">
              <template #default="{ row }">
                <span v-for="r in row.reviews" :key="r" class="review-reason">{{ r }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`错误 (${preview.errors.length})`" name="error">
          <el-table :data="preview.errors" border stripe max-height="400">
            <el-table-column prop="package_no" label="包裹号" width="150" />
            <el-table-column prop="sku" label="SKU" min-width="200" />
            <el-table-column label="错误" min-width="260">
              <template #default="{ row }">
                <span v-for="e in row.errors" :key="e" class="error-reason">{{ e }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 人工复核队列 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>人工复核队列</span>
          <el-button @click="fetchReviews">刷新</el-button>
        </div>
      </template>
      <el-table :data="reviews" border stripe v-loading="loadingReviews">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="package_no" label="包裹号" width="150" />
        <el-table-column prop="reason_code" label="原因码" width="90" />
        <el-table-column prop="reason_detail" label="详情" min-width="220" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button v-if="row.status === '待处理'" link type="success" @click="resolve(row, '放行')">放行</el-button>
            <el-button v-if="row.status === '待处理'" link type="danger" @click="resolve(row, '拦截')">拦截</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { previewImport, commitImport, listReviews, resolveReview } from '../api'

const file = ref(null)
const previewing = ref(false)
const committing = ref(false)
const preview = ref(null)
const tab = ref('normal')
const reviews = ref([])
const loadingReviews = ref(false)

function onFileChange(uploadFile) {
  file.value = uploadFile.raw
}

async function doPreview() {
  if (!file.value) return ElMessage.warning('请先选择文件')
  previewing.value = true
  try {
    preview.value = await previewImport(file.value)
    tab.value = 'normal'
    ElMessage.success(`解析完成：正常 ${preview.value.normal_count}，复核 ${preview.value.review_count}，错误 ${preview.value.error_count}`)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    previewing.value = false
  }
}

async function doCommit() {
  if (!file.value) return
  committing.value = true
  try {
    const r = await commitImport(file.value, false)
    ElMessage.success(`导入成功：批次 ${r.batch_no}，成功 ${r.success_rows} 条`)
    fetchReviews()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    committing.value = false
  }
}

async function fetchReviews() {
  loadingReviews.value = true
  try {
    reviews.value = await listReviews()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loadingReviews.value = false
  }
}

async function resolve(row, resolution) {
  try {
    await resolveReview(row.id, resolution)
    ElMessage.success('已处理')
    fetchReviews()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(fetchReviews)
</script>

<style scoped>
.actions {
  margin-top: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.review-reason,
.error-reason {
  display: block;
  color: #e6a23c;
  font-size: 13px;
}
.error-reason {
  color: #f56c6c;
}
</style>
