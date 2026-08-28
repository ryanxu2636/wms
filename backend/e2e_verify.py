"""端到端联调验证脚本：通过 HTTP API 走通完整履约链路。

链路：待分配 → 分配 → 拣货任务 → 拣货完成 → 复核 → 打包 → 标记面单 → 出库
并验证：库存守恒、缺货挂起、出库硬卡点、库位上架推荐。
"""
import json
import sys
import requests

BASE = "http://localhost:8000/api"


def call(method, path, **kwargs):
    url = f"{BASE}{path}"
    r = requests.request(method, url, **kwargs)
    try:
        body = r.json()
    except Exception:
        body = r.text
    return r.status_code, body


def show(title, status, body):
    print(f"\n### {title}")
    print(f"    HTTP {status}: {json.dumps(body, ensure_ascii=False, default=str)}")
    return body


def main():
    results = []
    ok = lambda name, cond: results.append((name, cond))

    # 1. 健康检查
    s, b = call("GET", "/../health")
    ok("health", s == 200)

    # 2. 库存列表
    s, b = call("GET", "/stock")
    ok("库存列表", s == 200 and len(b) >= 2)
    show("库存列表（初始）", s, b)

    # 3. 订单 P1 分配
    s, b = call("POST", "/orders/allocate", json={"package_id": 1})
    ok("订单P1分配", s == 200)
    show("订单P1分配", s, b)

    # 4. 订单 P2 分配（缺货 → shortage_hold）
    s, b = call("POST", "/orders/allocate", json={"package_id": 2})
    ok("订单P2缺货挂起", s == 200)
    show("订单P2分配（缺货）", s, b)

    # 5. 状态机：P1 应为 assigned，P2 应为 shortage_hold
    s1, b1 = call("GET", "/orders/1/state")
    s2, b2 = call("GET", "/orders/2/state")
    ok("P1状态=assigned", b1.get("status") == "assigned")
    ok("P2状态=shortage_hold", b2.get("status") == "shortage_hold")
    show("P1 状态", s1, b1)
    show("P2 状态", s2, b2)

    # 6. 库存守恒：分配后 base 的 allocated 应增加
    # 动态获取 base SKU 的 id（seed 数据 sku_id 可能不是 1，因期初数据占用了低 id）
    s, b = call("GET", "/sku", params={"keyword": "SKU-BASE-001"})
    base_sku_id = b[0]["id"] if isinstance(b, list) and b else None
    s, b = call("GET", "/stock")
    base_stock = [x for x in b if x.get("sku_id") == base_sku_id]
    show("分配后 base 库存", s, base_stock)
    ok("base库存守恒(available+allocated=100)", any(
        x.get("available_qty", 0) + x.get("allocated_qty", 0) == 100 for x in base_stock
    ))

    # 7. 创建拣货任务（P1 assigned → picking）
    s, b = call("POST", "/picking/tasks", json={"package_id": 1, "assignee_id": 100})
    task_id = b.get("task_id") if isinstance(b, dict) else None
    ok("创建拣货任务", s == 200 and task_id is not None)
    show("创建拣货任务", s, b)

    # 8. 拣货项（含路径排序）
    s, b = call("GET", "/picking/1/items")
    ok("拣货项列表", s == 200 and len(b) >= 1)
    show("拣货项（路径排序）", s, b)

    # 9. 拣货完成（picking → checked）
    s, b = call("POST", "/picking/tasks/complete", json={"task_id": task_id})
    ok("拣货完成", s == 200)
    show("拣货完成", s, b)

    # 10. 复核（checked 状态）
    s, b = call("POST", "/picking/check", json={"package_id": 1, "packer_id": 200})
    ok("复核", s == 200)
    show("复核", s, b)

    # 11. 打包（checked → packed）
    s, b = call("POST", "/picking/1/pack")
    ok("打包", s == 200)
    show("打包", s, b)

    # 12. 出库硬卡点：未打印面单应 409
    s, b = call("POST", "/outbound/ship", json={"outbound_id": 1})
    ok("出库硬卡点(未打印=409)", s == 409)
    show("出库(未打印面单，应409)", s, b)

    # 13. 标记面单已打印
    s, b = call("POST", "/outbound/mark_printed", json={"outbound_id": 1})
    ok("标记面单已打印", s == 200)
    show("标记面单已打印", s, b)

    # 14. 出库（packed → outbound）
    s, b = call("POST", "/outbound/ship", json={"outbound_id": 1})
    ok("出库成功", s == 200)
    show("出库", s, b)

    # 15. 终态验证
    s, b = call("GET", "/orders/1/state")
    ok("P1终态=outbound", b.get("status") == "outbound")
    show("P1 终态", s, b)

    # 16. 出库后库存守恒：allocated 归零，available 减少
    s, b = call("GET", "/stock")
    base_stock = [x for x in b if x.get("sku_id") == base_sku_id]
    show("出库后 base 库存", s, base_stock)
    ok("出库后 base allocated=0", any(x.get("allocated_qty") == 0 for x in base_stock))

    # 17. 库存流水留痕
    s, b = call("GET", f"/stock/{base_stock[0]['id']}/transactions")
    ok("库存流水留痕", s == 200 and len(b) >= 1)
    show("库存流水", s, b)

    # 18. 上架推荐（空库位）
    s, b = call("GET", "/putaway/recommend", params={"sku_id": base_sku_id})
    ok("上架推荐", s == 200)
    show("上架推荐", s, b)

    # 19. 库位列表
    s, b = call("GET", "/putaway/locations")
    ok("库位列表", s == 200 and len(b) >= 1)
    show("库位列表", s, b)

    # 汇总
    print("\n\n================ 端到端联调结果汇总 ================")
    passed = sum(1 for _, c in results if c)
    total = len(results)
    for name, cond in results:
        print(f"  [{'✓' if cond else '✗'}] {name}")
    print(f"\n通过 {passed}/{total}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
