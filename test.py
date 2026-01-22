# bt_to_cron_interactive.py

def beijing_time_to_cron(time_str: str) -> str:
    """
    输入: 'HH:MM'（24 小时制北京时间）
    输出: 'MM HH * * *' 形式的 cron 表达式
    """
    try:
        hour_str, minute_str = time_str.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError:
        raise ValueError("时间格式必须是 HH:MM，例如 04:50 或 18:30")

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("小时必须在 0-23，分钟必须在 0-59 之间")

    # 假设服务器时区就是北京时间（UTC+8）
    return f"{minute} {hour} * * *"


if __name__ == "__main__":
    while True:
        s = input("请输入北京时间 (HH:MM)，或按回车退出：").strip()
        if not s:
            break
        try:
            cron_expr = beijing_time_to_cron(s)
            print("对应的 cron 表达式是：", cron_expr)
        except Exception as e:
            print("错误：", e)