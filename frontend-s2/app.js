// WMS S2 前端应用逻辑
const { createApp, ref, reactive, computed, onMounted } = Vue;

const STATUS_MAP = {
  unassigned: { label: "待分配", cls: "pending" },
  assigned: { label: "已分配", cls: "assigned" },
  picking: { label: "拣货中", cls: "picking" },
  checked: { label: "已复核", cls: "checked" },
  packed: { label: "已打包", cls: "packed" },
  outbound: { label: "已出库", cls: "outbound" },
  intercepted: { label: "拦截", cls: "intercepted" },
  manual_review: { label: "待人工复核", cls: "review" },
  shortage_hold: { label: "缺货挂起", cls: "shortage" },
};

const app = createApp({
  setup() {
    const apiBase = ref(localStorage.getItem("wms_api") || "http://localhost:8000");
    const apiOk = ref(false);
    const activeTab = ref("orders");

    const stats = reactive({ unassigned: 0, inProgress: 0, outbound: 0, abnormal: 0 });
    const orders = ref([]);
    const stocks = ref([]);
    const locations = ref([]);
    const pickItems = ref([]);
    const orderFilter = ref("");
    const pickingPackageId = ref("");
    const putawaySkuId = ref("");
    const recommendResult = ref("");
    const loading = reactive({ orders: false, stock: false });

    const statusList = Object.entries(STATUS_MAP).map(([value, v]) => ({ value, label: v.label }));

    const api = axios.create({ baseURL: apiBase.value });
    api.interceptors.request.use((cfg) => {
      cfg.baseURL = apiBase.value;
      return cfg;
    });
    api.interceptors.response.use(
      (r) => r,
      (err) => {
        const detail = err.response?.data?.detail || err.message;
        ElMessage.error(typeof detail === "string" ? detail : JSON.stringify(detail));
        return Promise.reject(err);
      }
    );

    const statusLabel = (s) => STATUS_MAP[s]?.label || s;
    const statusClass = (s) => STATUS_MAP[s]?.cls || "pending";

    async function probeApi() {
      try {
        await api.get("/health", { timeout: 3000 });
        apiOk.value = true;
        localStorage.setItem("wms_api", apiBase.value);
      } catch {
        apiOk.value = false;
      }
    }

    async function loadOrders() {
      loading.orders = true;
      try {
        const params = orderFilter.value ? { status: orderFilter.value } : {};
        const { data } = await api.get("/api/picking/orders", { params });
        orders.value = data;
        refreshStats();
      } finally {
        loading.orders = false;
      }
    }

    function refreshStats() {
      stats.unassigned = orders.value.filter((o) => o.status === "unassigned").length;
      stats.inProgress = orders.value.filter((o) => ["assigned", "picking", "checked", "packed"].includes(o.status)).length;
      stats.outbound = orders.value.filter((o) => o.status === "outbound").length;
      stats.abnormal = orders.value.filter((o) => ["intercepted", "manual_review", "shortage_hold"].includes(o.status)).length;
    }

    async function allocate(row) {
      await api.post("/api/orders/allocate", { package_id: row.id });
      ElMessage.success(`包裹 ${row.package_no} 分配成功`);
      loadOrders();
    }

    async function batchAllocate() {
      const pending = orders.value.filter((o) => o.status === "unassigned");
      if (!pending.length) { ElMessage.info("没有待分配订单"); return; }
      let ok = 0, fail = 0;
      for (const o of pending) {
        try { await api.post("/api/orders/allocate", { package_id: o.id }); ok++; }
        catch { fail++; }
      }
      ElMessage.success(`批量分配完成：成功 ${ok}，失败 ${fail}`);
      loadOrders();
    }

    async function release(row) {
      await api.post("/api/orders/release", { package_id: row.id });
      ElMessage.success(`包裹 ${row.package_no} 已释放`);
      loadOrders();
    }

    async function createTask(row) {
      const { data } = await api.post("/api/picking/tasks", { package_id: row.id });
      ElMessage.success(`拣货任务 ${data.task_no} 已生成`);
      loadOrders();
    }

    async function loadPickItems() {
      if (!pickingPackageId.value) { ElMessage.warning("请输入包裹ID"); return; }
      const { data } = await api.get(`/api/picking/${pickingPackageId.value}/items`);
      pickItems.value = data;
    }

    async function completePick(row) {
      // 按包裹查拣货任务，再调用完成接口
      const { data: t } = await api.get(`/api/picking/package/${row.id}/task`);
      await api.post("/api/picking/tasks/complete", { task_id: t.task_id });
      ElMessage.success(`包裹 ${row.package_no} 拣货完成`);
      loadOrders();
    }

    async function checkPackage(row) {
      // 复核（补充 packing 记录，保持 checked 状态）
      await api.post("/api/picking/check", { package_id: row.id });
      ElMessage.success(`包裹 ${row.package_no} 已复核`);
      loadOrders();
    }

    async function pack(row) {
      await api.post(`/api/picking/${row.id}/pack`);
      ElMessage.success(`包裹 ${row.package_no} 已打包`);
      loadOrders();
    }

    async function markPrinted(row) {
      // 先按包裹查出库单，再标记面单
      const { data: ob } = await api.get(`/api/outbound/by_package/${row.id}`);
      await api.post("/api/outbound/mark_printed", { outbound_id: ob.outbound_id });
      ElMessage.success(`包裹 ${row.package_no} 面单已标记打印`);
    }

    async function ship(row) {
      // 先按包裹查出库单，再出库
      const { data: ob } = await api.get(`/api/outbound/by_package/${row.id}`);
      await api.post("/api/outbound/ship", { outbound_id: ob.outbound_id });
      ElMessage.success(`包裹 ${row.package_no} 已出库`);
      loadOrders();
    }

    async function loadStock() {
      loading.stock = true;
      try {
        const { data } = await api.get("/api/stock");
        stocks.value = data;
      } finally {
        loading.stock = false;
      }
    }

    async function viewTxn(row) {
      const { data } = await api.get(`/api/stock/${row.id}/transactions`);
      const text = data.map((t) => `[${t.change_type}] ${t.change_qty > 0 ? "+" : ""}${t.change_qty} (${t.before_qty}→${t.after_qty})`).join("\n") || "无流水";
      ElMessageBox.alert(text, `库存 ${row.id} 流水`, { confirmButtonText: "关闭" });
    }

    async function loadLocations() {
      const { data } = await api.get("/api/putaway/locations");
      locations.value = data;
    }

    async function recommend() {
      if (!putawaySkuId.value) { ElMessage.warning("请输入 SKU ID"); return; }
      const { data } = await api.post("/api/putaway/recommend", null, { params: { sku_id: putawaySkuId.value } });
      recommendResult.value = data.to_location_id
        ? `SKU ${data.sku_id} 推荐上架库位 ID = ${data.to_location_id}`
        : `SKU ${data.sku_id} 无可用库位，需人工处理`;
      loadLocations();
    }

    onMounted(async () => {
      await probeApi();
      loadOrders();
      loadStock();
      loadLocations();
    });

    return {
      apiBase, apiOk, activeTab, stats, orders, stocks, locations, pickItems,
      orderFilter, pickingPackageId, putawaySkuId, recommendResult, loading, statusList,
      statusLabel, statusClass, probeApi, loadOrders, allocate, batchAllocate, release,
      createTask, loadPickItems, completePick, checkPackage, pack, markPrinted, ship, loadStock,
      viewTxn, loadLocations, recommend,
    };
  },
});

app.use(ElementPlus);
app.mount("#app");
