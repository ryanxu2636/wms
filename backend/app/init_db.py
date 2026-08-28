"""初始化数据库：建表 + 预置种子数据（仓库 + 4 条虚拟/标记规则）。

用法：python -m app.init_db
"""

from app.core.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import VirtualRule, Warehouse


def seed_rules(db):
    rules = [
        {"rule_type": "virtual", "match_type": "exact", "match_value": "YUN",
         "action": "skip", "priority": 1, "enabled": 1,
         "description": "运费虚拟品：免拣货、免库存校验、免面单"},
        {"rule_type": "marker", "match_type": "prefix", "match_value": "CS99",
         "action": "intercept", "priority": 2, "enabled": 1,
         "description": "订单不可发货警告：整包裹拦截出库"},
        {"rule_type": "marker", "match_type": "prefix", "match_value": "CS00",
         "action": "manual_review", "priority": 2, "enabled": 1,
         "description": "电器规格匹配错误警告：强制人工复核"},
        {"rule_type": "marker", "match_type": "prefix", "match_value": "CS000",
         "action": "ignore", "priority": 2, "enabled": 1,
         "description": "忽略采购拆链组合发货：采购需求/组合展开时跳过"},
    ]
    for r in rules:
        exists = db.query(VirtualRule).filter(VirtualRule.match_value == r["match_value"]).first()
        if not exists:
            db.add(VirtualRule(**r))
    db.commit()


def seed_warehouse(db):
    exists = db.query(Warehouse).filter(Warehouse.code == "CS").first()
    if not exists:
        db.add(Warehouse(code="CS", name="长沙CS仓"))
        db.commit()


def main():
    print("创建数据表...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_warehouse(db)
        seed_rules(db)
        print("种子数据已写入：长沙CS仓 + 4 条虚拟/标记规则")
    finally:
        db.close()
    print("初始化完成")


if __name__ == "__main__":
    main()
