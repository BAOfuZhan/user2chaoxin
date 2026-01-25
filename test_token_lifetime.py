import time
import logging
import datetime
from zoneinfo import ZoneInfo

from utils import reserve as Reserve


# ======================= 使用说明 =======================
# 1. 在下面填写你要用于测试的账号、密码、房间号、座位号、时间段
# 2. 这个文件只在本地手动运行，用于测试 token 和滑块验证码的有效时间
# 3. 不会影响项目原有逻辑，也不会读取 config.json
# 4. 建议选择一个“不重要”的时间段/座位，避免真正抢到座位
# ======================================================

# TODO: 在这里填写你的测试账号信息
TEST_USERNAME = "18295178271"
TEST_PASSWORD = "suyu940513"

# 教室/房间、座位、时间段
TEST_ROOM_ID = "9928"          # 房间号，例如 9928
TEST_SEAT_ID = "060"           # 座位号，例如 060
TEST_TIMES = ["09:30", "22:00"]  # [开始时间, 结束时间]，格式 HH:MM

# 是否启用滑块验证（如果学校当前环境有滑块，就设为 True）
TEST_ENABLE_SLIDER = True


class BeijingFormatter(logging.Formatter):
    """和 main.py 一样，把日志时间格式化为北京时间，便于观察。"""

    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, ZoneInfo("Asia/Shanghai"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()


_formatter = BeijingFormatter(
    fmt="%(asctime)s.%(msecs)03d [Asia/Shanghai] - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_handler = logging.StreamHandler()
_handler.setFormatter(_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_handler])


def _build_session():
    """登录并返回已登录的 Reserve 实例和首个座位号。"""
    if not TEST_USERNAME or not TEST_PASSWORD:
        logging.error("请先在 test_token_lifetime.py 中填写 TEST_USERNAME / TEST_PASSWORD")
        return None, None

    s = Reserve(
        sleep_time=0.1,
        max_attempt=10,
        enable_slider=TEST_ENABLE_SLIDER,
        reserve_next_day=False,
    )
    s.get_login_status()
    s.login(TEST_USERNAME, TEST_PASSWORD)
    s.requests.headers.update({"Host": "office.chaoxing.com"})

    first_seat = TEST_SEAT_ID
    return s, first_seat


def test_login_token_lifetime(delays=None):
    """验证“登录后获取的页面 token”在多长时间内仍然可用。

    策略：
    - 登录一次，获取 token/value；
    - 每个延迟点重新做滑块（如果启用），但一直复用同一个 token；
    - 观察在多长时间后，需要重新获取 token 才能正常提交。
    """

    if delays is None:
        delays = [0, 5, 10, 20, 30, 45, 60 ,70,80,90,100]

    s, first_seat = _build_session()
    if s is None:
        return

    token, value = s._get_page_token(
        s.url.format(TEST_ROOM_ID, first_seat), require_value=True
    )
    if not token:
        logging.error("[test-token] Failed to get page token, abort test")
        return
    logging.info(f"[test-token] Got token={token}, value={value}")

    start_ts = time.time()
    logging.info("[test-token] Start login-token lifetime test")

    for d in delays:
        # 等到当前 delay 的时间点
        while time.time() - start_ts < d:
            time.sleep(0.1)

        captcha = ""
        if TEST_ENABLE_SLIDER:
            captcha = s.resolve_captcha()

        resp = s.burst_submit_once(
            times=TEST_TIMES,
            roomid=TEST_ROOM_ID,
            seatid=first_seat,
            captcha=captcha,
            token=token,
            value=value,
        )
        elapsed = time.time() - start_ts
        logging.info(f"[test-token] target_delay={d}s, elapsed={elapsed:.3f}s, resp={resp}")

    logging.info("[test-token] Login-token lifetime test finished")


def test_captcha_lifetime(delays=None):
    """验证“滑块验证码 captcha”在多长时间内仍然可用（首用时间）。

    策略：
    - 登录一次，先做一次滑块，获取 captcha；
    - 每个延迟点重新获取 token/value，但一直复用同一个 captcha；
    - 观察在多长时间后，首用 captcha 会从“业务失败”变成“验证码校验未通过”。
    """

    if delays is None:
        delays = [0, 5, 10, 20, 30, 45, 60]

    if not TEST_ENABLE_SLIDER:
        logging.error("[test-captcha] 当前未启用滑块验证(TEST_ENABLE_SLIDER=False)，无法测试 captcha 有效期")
        return

    s, first_seat = _build_session()
    if s is None:
        return

    captcha = s.resolve_captcha()
    logging.info("[test-captcha] Got initial captcha")

    start_ts = time.time()
    logging.info("[test-captcha] Start captcha lifetime test")

    for d in delays:
        while time.time() - start_ts < d:
            time.sleep(0.1)

        token, value = s._get_page_token(
            s.url.format(TEST_ROOM_ID, first_seat), require_value=True
        )
        if not token:
            logging.error(f"[test-captcha] delay={d}s, failed to get token, skip this point")
            continue

        resp = s.burst_submit_once(
            times=TEST_TIMES,
            roomid=TEST_ROOM_ID,
            seatid=first_seat,
            captcha=captcha,
            token=token,
            value=value,
        )
        elapsed = time.time() - start_ts
        logging.info(f"[test-captcha] target_delay={d}s, elapsed={elapsed:.3f}s, resp={resp}")

    logging.info("[test-captcha] Captcha lifetime test finished")


def test_captcha_single_use(rounds: int = 3):
    """验证 captcha 是否“一次性”。

    策略：
    - 连续多轮(rounds)：
      * 每轮获取一个新的 captcha；
      * 用同一个 captcha 连续提交 2 次；
      * 记录第 1 次 / 第 2 次的返回，看是否第 2 次固定变为“验证码校验未通过”。
    """
    if not TEST_ENABLE_SLIDER:
        logging.error("[test-captcha-single] 当前未启用滑块验证(TEST_ENABLE_SLIDER=False)，无法测试 captcha 一次性")
        return

    s, first_seat = _build_session()
    if s is None:
        return

    logging.info(f"[test-captcha-single] Start single-use test, rounds={rounds}")

    for i in range(1, rounds + 1):
        captcha = s.resolve_captcha()
        logging.info(f"[test-captcha-single] Round {i}: got new captcha")

        token, value = s._get_page_token(
            s.url.format(TEST_ROOM_ID, first_seat), require_value=True
        )
        if not token:
            logging.error(f"[test-captcha-single] Round {i}: failed to get token, skip")
            continue

        # 同一个 captcha 连续提交两次
        for attempt in (1, 2):
            resp = s.burst_submit_once(
                times=TEST_TIMES,
                roomid=TEST_ROOM_ID,
                seatid=first_seat,
                captcha=captcha,
                token=token,
                value=value,
            )
            logging.info(
                f"[test-captcha-single] Round {i}, attempt {attempt}, resp={resp}"
            )

    logging.info("[test-captcha-single] Single-use test finished")


def test_captcha_first_use_delay(delay_sec: float = 20.0):
    """测试“首次使用 captcha 时延迟 delay_sec 秒”是否仍然有效。

    测试步骤：
    - 登录一次，获取新的 captcha；
    - 等待 delay_sec 秒；
    - 获取一次 token/value，并使用这个 captcha 提交一次；
    - 打印实际等待时间和返回结果。
    """
    if not TEST_ENABLE_SLIDER:
        logging.error("[test-captcha-first] 当前未启用滑块验证(TEST_ENABLE_SLIDER=False)，无法测试 captcha 首次延迟使用")
        return

    s, first_seat = _build_session()
    if s is None:
        return

    captcha = s.resolve_captcha()
    logging.info(f"[test-captcha-first] Got captcha, will first-use after {delay_sec}s")

    start_ts = time.time()
    target_ts = start_ts + delay_sec

    # 等到 delay_sec 秒后
    while time.time() < target_ts:
        time.sleep(0.1)

    token, value = s._get_page_token(
        s.url.format(TEST_ROOM_ID, first_seat), require_value=True
    )
    if not token:
        logging.error("[test-captcha-first] Failed to get token after delay, abort")
        return

    resp = s.burst_submit_once(
        times=TEST_TIMES,
        roomid=TEST_ROOM_ID,
        seatid=first_seat,
        captcha=captcha,
        token=token,
        value=value,
    )
    elapsed = time.time() - start_ts
    logging.info(
        f"[test-captcha-first] delay_target={delay_sec}s, elapsed={elapsed:.3f}s, resp={resp}"
    )


def test_captcha_stash_two(interval_sec: float = 1.0):
    """测试是否可以“囤”两份 captcha，并间隔 interval_sec 秒各用一次。

    策略：
    - 登录一次，连续获取 captcha1 和 captcha2；
    - 记录起始时间；
    - 立刻用 captcha1 + 新 token 提交一次（attempt 1）；
    - 等待 interval_sec 秒，再用 captcha2 + 新 token 提交一次（attempt 2）；
    - 观察两次是否都是正常业务错误，而不是“验证码校验未通过”。
    """
    if not TEST_ENABLE_SLIDER:
        logging.error("[test-captcha-stash] 当前未启用滑块验证(TEST_ENABLE_SLIDER=False)，无法测试囤两份 captcha")
        return

    s, first_seat = _build_session()
    if s is None:
        return

    logging.info(f"[test-captcha-stash] Start stash-two test, interval={interval_sec}s")

    # 连续获取两份 captcha
    captcha1 = s.resolve_captcha()
    logging.info("[test-captcha-stash] Got captcha1")
    captcha2 = s.resolve_captcha()
    logging.info("[test-captcha-stash] Got captcha2")

    start_ts = time.time()

    # 使用 captcha1（第一次）
    token1, value1 = s._get_page_token(
        s.url.format(TEST_ROOM_ID, first_seat), require_value=True
    )
    if not token1:
        logging.error("[test-captcha-stash] Failed to get token1, abort")
        return
    resp1 = s.burst_submit_once(
        times=TEST_TIMES,
        roomid=TEST_ROOM_ID,
        seatid=first_seat,
        captcha=captcha1,
        token=token1,
        value=value1,
    )
    elapsed1 = time.time() - start_ts
    logging.info(
        f"[test-captcha-stash] attempt1 (captcha1), elapsed={elapsed1:.3f}s, resp={resp1}"
    )

    # 间隔 interval_sec 秒后使用 captcha2
    target_ts = start_ts + interval_sec
    while time.time() < target_ts:
        time.sleep(0.1)

    token2, value2 = s._get_page_token(
        s.url.format(TEST_ROOM_ID, first_seat), require_value=True
    )
    if not token2:
        logging.error("[test-captcha-stash] Failed to get token2, abort")
        return
    resp2 = s.burst_submit_once(
        times=TEST_TIMES,
        roomid=TEST_ROOM_ID,
        seatid=first_seat,
        captcha=captcha2,
        token=token2,
        value=value2,
    )
    elapsed2 = time.time() - start_ts
    logging.info(
        f"[test-captcha-stash] attempt2 (captcha2), elapsed={elapsed2:.3f}s, resp={resp2}"
    )


if __name__ == "__main__":
    print("================ Token/Captcha 测试菜单 ================")
    print("1. 测试登录后的页面 token 有效时间 (token lifetime)")
    print("2. 测试滑块验证码 captcha 有效时间 (captcha lifetime)")
    print("3. 测试滑块验证码是否一次性 (captcha single-use)")
    print("4. 测试滑块验证码首次在指定延迟后使用 (captcha first-use delay)")
    print("5. 测试是否可以囤两份 captcha 并间隔 1 秒使用 (captcha stash two)")
    choice = input("请输入选项 (1/2/3/4/5): ").strip()

    if choice == "1":
        test_login_token_lifetime()
    elif choice == "2":
        test_captcha_lifetime()
    elif choice == "3":
        test_captcha_single_use()
    elif choice == "4":
        # 默认测试 20 秒后首次使用；你也可以在这里改成其他秒数
        test_captcha_first_use_delay(20.0)
    elif choice == "5":
        # 默认两次间隔 1 秒，可以在函数调用里改间隔
        test_captcha_stash_two(1.0)
    else:
        print("无效选项，已退出。")
