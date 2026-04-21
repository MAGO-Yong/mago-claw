#!/usr/bin/env python3
"""
Meal Order CLI - 订餐命令行工具
Usage: python meal.py {config|guide|reserve|order|pay|book|cancel|history|position} [options]

所有命令默认输出 JSON，供 AI skill 解析。
"""

import argparse
import datetime
import json
import os
import secrets
import sys
import time
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置文件固定在脚本所在目录，不依赖运行时工作目录
CONFIG_FILE = Path(__file__).parent.parent / ".meal_config.json"
BASE_URL = "https://hefan.youfantech.cn"

# 公共请求参数
COMMON_PARAMS = {
    "appNum": 0,
    "corpId": 0,
    "appType": "Android",
}

# 订单状态映射
STATUS_MAP = {
    "IS_SENDING": "配送中",
    "IS_COMPLETE": "已完成",
    "IS_CANCEL":   "已取消",
    "IS_WAIT":     "待配送",
    "IS_DONE":     "已送达",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def die(msg: str, code: int = 1):
    """打印错误到 stderr 并退出"""
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


def output(data):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def is_success(result: dict) -> bool:
    """判断 API 响应是否成功"""
    if not result or "error" in result:
        return False
    code = str(result.get("code", ""))
    # 明确的失败码
    if code in ("500", "400", "401", "403"):
        return False
    # data 为 None 且有 message 通常是业务失败
    if result.get("data") is None and result.get("message") and code != "200":
        return False
    return True


# ---------------------------------------------------------------------------
# 配置管理
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        die(f"配置文件损坏，请删除 {CONFIG_FILE} 后重新配置")


def save_config(code: str, client_type: str = "sso", jsessionid: str = None):
    config = {"code": code, "client_type": client_type}
    if jsessionid:
        config["jsessionid"] = jsessionid
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    os.chmod(CONFIG_FILE, 0o600)
    output({"success": True, "message": "配置已保存", "config_file": str(CONFIG_FILE)})


# ---------------------------------------------------------------------------
# 配置检查装饰器
# ---------------------------------------------------------------------------

def require_config(func):
    def wrapper(args):
        config = load_config()
        if not config.get("code"):
            die("未配置认证信息，请先运行: python meal.py config --code <code>")
        args.client = MealClient(
            code=config["code"],
            client_type=config.get("client_type", "sso"),
            jsessionid=config.get("jsessionid"),
        )
        return func(args)
    return wrapper


# ---------------------------------------------------------------------------
# HTTP 客户端
# ---------------------------------------------------------------------------

class MealClient:
    def __init__(self, code: str, client_type: str = "sso", jsessionid: str = None):
        self.code = code
        self.client_type = client_type
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "DNT": "1",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/m/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
        })
        cookies = {"old_client_type": client_type, "client_type": client_type, "code": code}
        if jsessionid:
            cookies["JSESSIONID"] = jsessionid
        self.session.cookies.update(cookies)

    def _common(self) -> dict:
        """返回每次请求都需要携带的公共参数"""
        return {**COMMON_PARAMS, "code": self.code, "client_type": self.client_type}

    def _request(self, method: str, endpoint: str, extra: dict = None) -> dict:
        """发送请求，公共参数统一在此注入，不在调用方重复构建"""
        url = f"{BASE_URL}{endpoint}"
        params = {**self._common(), **(extra or {})}
        m = method.upper()
        try:
            resp = self.session.request(
                method=m,
                url=url,
                params=params if m == "GET" else None,
                data=params if m == "POST" else None,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            return {"error": str(e), "status_code": e.response.status_code}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    # --- API 方法 ---

    def get_reserve(self, use_date: str, interval_no: int = 2) -> dict:
        return self._request("POST", "/ufanMenu/reserve", {
            "intervalNo": interval_no,
            "useDate": use_date,
        })

    def get_guide(self, use_date: str) -> dict:
        return self._request("POST", "/ufanMenu/getGuide", {"useDate": use_date})

    def confirm_order(self, cart_items: list, staff_coupon_id: int = -1, use_subsidy: int = 0) -> dict:
        return self._request("POST", "/ufanMenu/confirmOrder", {
            "shoppingCartVoListJson": json.dumps(cart_items),
            "staffCouponId": staff_coupon_id,
            "useSubsidy": use_subsidy,
        })

    def pay_order(self, cart_items: list) -> dict:
        return self._request("POST", "/ufanCore/payCartForFree", {
            "shoppingCartVoListJson": json.dumps(cart_items),
            "nonceStr": secrets.token_hex(10),
            "timestamp": int(time.time()),
        })

    def cancel_order(self, order_id) -> dict:
        return self._request("POST", "/ufanOrder/cancelOrder", {"orderId": order_id})

    def get_position_list(self) -> dict:
        return self._request("POST", "/ufanMenu/positionList")

    def bind_position(self, position_id: int) -> dict:
        return self._request("POST", "/ufanMenu/bindPosition", {"positionId": position_id})

    def get_history_orders(self) -> dict:
        return self._request("POST", "/ufanOrder/orders/history")

    def get_order_evaluate_form(self, order_id: int) -> dict:
        """获取评价表单（含菜品名、商家名等信息）"""
        return self._request("POST", "/ufanAssist/orderEvaluate", {"orderId": order_id})

    def do_evaluate(self, order_id: int, zt_star: int, taste_star: int, fl_star: int, content: str = "") -> dict:
        """提交评价：三个维度星级（1-5）+ 可选文字评论
        ztStar=总体, star=口味, flStar=份量
        isAnno=false 是前端必传字段，缺失会导致 ztStar 被服务端忽略
        """
        return self._request("POST", "/ufanAssist/doEvaluate", {
            "orderId":  order_id,
            "isAnno":   "false",    # 必须传，否则总体星不生效
            "ztStar":   zt_star,    # 总体
            "star":     taste_star, # 口味
            "flStar":   fl_star,    # 份量
            "content":  content,
        })


# ---------------------------------------------------------------------------
# 购物车构建（统一入口，消除三处重复）
# ---------------------------------------------------------------------------

def build_cart_items(goods_id: int, store_id: int, use_date: str,
                     interval_no: int, for_pay: bool = False) -> list:
    item = {
        "goodId": goods_id,
        "goodNum": 1,
        "useDate": use_date,
        "merchantStoreId": store_id,
        "intervalNo": str(interval_no),
        "isTaste": False,
        "numberOfPurchased": 0,
        "orderLimit": 0,
        "hidePrice": 1,
    }
    if for_pay:
        item.update({
            "goodPrice": 3000,
            "companyPrice": 3000,
            "actualPrice": 0,
            "needPersonPay": False,
            "couponPrice": 0,
            "walletPrice": 0,
            "thirdWalletPrice": 0,
            "staffCouponId": 0,
            "availableMoney": 0,
            "remainAvailableMoney": 0,
        })
    return [item]


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def cmd_config(args):
    save_config(args.code, args.client_type or "sso", args.jsessionid)


@require_config
def cmd_guide(args):
    use_date = args.date or time.strftime("%Y-%m-%d")
    result = args.client.get_guide(use_date)
    output(result)


@require_config
def cmd_reserve(args):
    use_date = args.date or time.strftime("%Y-%m-%d")

    if args.interval:
        output(args.client.get_reserve(use_date, args.interval))
    else:
        lunch = args.client.get_reserve(use_date, 2)
        dinner = args.client.get_reserve(use_date, 3)
        output({"lunch": lunch, "dinner": dinner})


@require_config
def cmd_order(args):
    if not all([args.goods, args.date, args.store]):
        die("缺少必要参数: --goods, --date, --store")
    cart = build_cart_items(int(args.goods), int(args.store), args.date, args.interval or 2)
    output(args.client.confirm_order(cart))


@require_config
def cmd_pay(args):
    if not all([args.goods, args.date, args.store]):
        die("缺少必要参数: --goods, --date, --store")
    cart = build_cart_items(int(args.goods), int(args.store), args.date, args.interval or 2, for_pay=True)
    output(args.client.pay_order(cart))


@require_config
def cmd_book(args):
    if not all([args.goods, args.date, args.store]):
        die("缺少必要参数: --goods, --date, --store")

    interval = args.interval or 2
    goods_id, store_id = int(args.goods), int(args.store)

    # 1. 确认订单
    confirm_cart = build_cart_items(goods_id, store_id, args.date, interval)
    order_result = args.client.confirm_order(confirm_cart)
    if not is_success(order_result):
        output({"success": False, "step": "confirm", "result": order_result})
        sys.exit(1)

    # 2. 支付
    pay_cart = build_cart_items(goods_id, store_id, args.date, interval, for_pay=True)
    pay_result = args.client.pay_order(pay_cart)
    if not is_success(pay_result):
        output({"success": False, "step": "pay", "result": pay_result})
        sys.exit(1)

    output({"success": True, "confirm": order_result, "pay": pay_result})


@require_config
def cmd_history(args):
    days = args.days or 7
    today = datetime.date.today()
    all_orders = []

    for i in range(days):
        target = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        result = args.client.get_guide(target)
        if not is_success(result):
            continue
        intervals = (result.get("data") or {}).get("currentDatePeriod", {}).get("timeIntervalList", [])
        for interval in intervals:
            order_id = interval.get("orderId")
            if not order_id:
                continue
            late = interval.get("lateOrder") or {}
            all_orders.append({
                "orderId":    order_id,
                "mealType":   interval.get("name"),
                "goodName":   interval.get("goodName"),
                "useDate":    target,
                "status":     late.get("orderStatus"),
                "statusText": STATUS_MAP.get(late.get("orderStatus", ""), late.get("orderStatus")),
                "boxNumber":  late.get("boxNumber"),
            })

    output({"total": len(all_orders), "orders": all_orders})


@require_config
def cmd_cancel(args):
    if not args.order_id:
        # 查询当日可取消订单列表，正常返回 0 退出码
        use_date = time.strftime("%Y-%m-%d")
        guide = args.client.get_guide(use_date)
        if not is_success(guide):
            output({"success": False, "result": guide})
            sys.exit(1)

        intervals = (guide.get("data") or {}).get("currentDatePeriod", {}).get("timeIntervalList", [])
        orders = [
            {
                "orderId":  iv.get("orderId"),
                "mealType": iv.get("name"),
                "goodName": iv.get("goodName"),
                "status":   STATUS_MAP.get((iv.get("lateOrder") or {}).get("orderStatus", ""), "未知"),
            }
            for iv in intervals if iv.get("orderId")
        ]
        output({"hint": "请使用 --order-id 指定要取消的订单", "orders": orders})
        return

    result = args.client.cancel_order(args.order_id)
    output({"success": is_success(result), "result": result})


@require_config
def cmd_evaluate(args):
    """评价命令：列出待评价订单，或提交评价"""
    # --list 或不带 --order-id：列出待评价订单
    if args.list or not args.order_id:
        result = args.client.get_history_orders()
        if not is_success(result):
            output({"success": False, "result": result})
            sys.exit(1)
        orders = (result.get("data") or {}).get("dataList", [])
        pending = [
            {
                "orderId":     o["id"],
                "goodName":    o["goodName"],
                "storeName":   o.get("storeName", ""),
                "sendDate":    o.get("sendDate", ""),
                "hasEvaluate": o.get("hasEvaluate", False),
                "evaluated":   o.get("isEvaluate", False) or o.get("evaluateStar", 0) > 0,
                "evaluateStar": o.get("evaluateStar", 0),
            }
            for o in orders
            if o.get("hasEvaluate") and not o.get("isEvaluate", False) and o.get("evaluateStar", 0) == 0
        ]
        output({"total": len(pending), "pendingEvaluations": pending})
        return

    # 提交评价
    for label, s in [("zt-star(总体)", args.zt_star), ("taste-star(口味)", args.taste_star), ("fl-star(份量)", args.fl_star)]:
        if not (1 <= s <= 5):
            die(f"{label} 必须在 1-5 之间")

    # 直接提交评价（跳过表单预检，避免接口时序问题导致"暂无评价数据"）
    form_data = {}
    result = args.client.do_evaluate(
        args.order_id,
        zt_star=args.zt_star,
        taste_star=args.taste_star,
        fl_star=args.fl_star,
        content=args.content or "",
    )
    success = is_success(result) and result.get("code") != "500"
    output({
        "success": success,
        "orderId":   args.order_id,
        "goodName":  form_data.get("goodName", ""),
        "storeName": form_data.get("shortName", ""),
        "stars": {
            "总体(ztStar)":    args.zt_star,
            "口味(tasteStar)": args.taste_star,
            "份量(flStar)":    args.fl_star,
        },
        "content": args.content or "",
        "result":  result,
    })


@require_config
def cmd_position(args):
    output(args.client.get_position_list())


@require_config
def cmd_bind_position(args):
    output(args.client.bind_position(int(args.position_id)))


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Meal Order CLI - 订餐命令行工具（所有命令输出 JSON）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python meal.py config --code xxx
  python meal.py position
  python meal.py reserve
  python meal.py reserve --interval 2        # 只查午餐
  python meal.py guide
  python meal.py book --goods 1025596 --date 2026-03-12 --store 11534 --interval 2
  python meal.py cancel
  python meal.py cancel --order-id 210336461
  python meal.py history
  python meal.py history --days 14
        """
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # config
    p = sub.add_parser("config", help="配置认证信息")
    p.add_argument("--code", required=True, help="用户授权码")
    p.add_argument("--client-type", default="sso")
    p.add_argument("--jsessionid", help="JSESSIONID（从浏览器 Cookie 获取）")
    p.set_defaults(func=cmd_config)

    # position
    p = sub.add_parser("position", help="查询可用取餐地点")
    p.set_defaults(func=cmd_position)

    # bind-position
    p = sub.add_parser("bind-position", help="绑定用餐地点")
    p.add_argument("--position-id", required=True, help="地点ID（从 position 命令获取）")
    p.set_defaults(func=cmd_bind_position)

    # reserve
    p = sub.add_parser("reserve", help="查询可预订菜单")
    p.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--interval", type=int, choices=[2, 3], help="2=午餐 3=晚餐，不填则同时查两餐")
    p.set_defaults(func=cmd_reserve)

    # guide
    p = sub.add_parser("guide", help="查看当日订餐状态")
    p.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    p.set_defaults(func=cmd_guide)

    # order
    p = sub.add_parser("order", help="确认订单")
    p.add_argument("--goods", required=True, help="商品ID")
    p.add_argument("--date", required=True, help="日期 YYYY-MM-DD")
    p.add_argument("--store", required=True, help="门店ID")
    p.add_argument("--interval", type=int, default=2, choices=[2, 3])
    p.set_defaults(func=cmd_order)

    # pay
    p = sub.add_parser("pay", help="支付订单")
    p.add_argument("--goods", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--interval", type=int, default=2, choices=[2, 3])
    p.set_defaults(func=cmd_pay)

    # book
    p = sub.add_parser("book", help="一键订餐（确认+支付）")
    p.add_argument("--goods", required=True, help="商品ID")
    p.add_argument("--date", required=True, help="日期 YYYY-MM-DD")
    p.add_argument("--store", required=True, help="门店ID")
    p.add_argument("--interval", type=int, default=2, choices=[2, 3])
    p.set_defaults(func=cmd_book)

    # cancel
    p = sub.add_parser("cancel", help="取消订单")
    p.add_argument("--order-id", help="订单ID，不填则列出可取消订单")
    p.set_defaults(func=cmd_cancel)

    # history
    p = sub.add_parser("history", help="查询历史订单")
    p.add_argument("--days", type=int, default=7, help="查询最近 N 天，默认 7")
    p.set_defaults(func=cmd_history)

    # evaluate
    p = sub.add_parser("evaluate", help="评价订单（不带参数时列出待评价）")
    p.add_argument("--list",       action="store_true", help="列出所有待评价订单")
    p.add_argument("--order-id",   type=int, help="订单ID")
    p.add_argument("--zt-star",    type=int, default=4, choices=[1,2,3,4,5], help="总体评分 1-5（默认4）")
    p.add_argument("--taste-star", type=int, default=4, choices=[1,2,3,4,5], help="口味评分 1-5（默认4）")
    p.add_argument("--fl-star",    type=int, default=4, choices=[1,2,3,4,5], help="份量评分 1-5（默认4）")
    p.add_argument("--content",    default="食品卫生好 食品卫生好 食品卫生好 食品卫生好 食品卫生好", help="评价文字")
    p.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
