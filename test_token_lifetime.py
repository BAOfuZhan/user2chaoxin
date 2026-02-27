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
TEST_USERNAME = "18339439007"
TEST_PASSWORD = "2802909619a@"

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


def test_captcha_stash_three(interval_sec: float = 2.0):
    """测试是否可以“囤”三份 captcha，先整体等待 12 秒，再按 interval_sec 秒间隔依次用掉。

    策略：
    - 登录一次，连续获取 captcha1、captcha2、captcha3；
    - 记录起始时间；
    - 等待 12 秒；
    - 然后用 captcha1 + 同一个 token 提交一次（attempt 1）；
    - 等待 interval_sec 秒，用 captcha2 + 同一个 token 提交一次（attempt 2）；
    - 再等待 interval_sec 秒，用 captcha3 + 同一个 token 提交一次（attempt 3）；
    - 观察三次是否都是正常业务错误，而不是“验证码校验未通过”。
    """
    if not TEST_ENABLE_SLIDER:
        logging.error("[test-captcha-stash] 当前未启用滑块验证(TEST_ENABLE_SLIDER=False)，无法测试囤多份 captcha")
        return

    s, first_seat = _build_session()
    if s is None:
        return

    logging.info(f"[test-captcha-stash] Start stash-three test, interval={interval_sec}s")

    # 连续获取三份 captcha
    captcha1 = s.resolve_captcha()
    logging.info("[test-captcha-stash] Got captcha1")
    captcha2 = s.resolve_captcha()
    logging.info("[test-captcha-stash] Got captcha2")
    captcha3 = s.resolve_captcha()
    logging.info("[test-captcha-stash] Got captcha3")

    start_ts = time.time()

    # 先整体等待 12 秒，再开始第一次使用 captcha
    initial_delay = 11.0
    target_initial = start_ts + initial_delay
    logging.info(
        f"[test-captcha-stash] wait {initial_delay}s before first use of captchas (until {target_initial:.3f})"
    )
    while time.time() < target_initial:
        time.sleep(0.1)

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
    attempt1_ts = time.time()
    elapsed1 = attempt1_ts - start_ts
    logging.info(
        f"[test-captcha-stash] attempt1 (captcha1), elapsed={elapsed1:.3f}s, resp={resp1}"
    )

    # 间隔 interval_sec 秒后使用 captcha2（第二次）
    target_ts = attempt1_ts + interval_sec
    logging.info(
        f"[test-captcha-stash] waiting until {target_ts:.3f} for attempt2 (interval={interval_sec}s)"
    )
    while time.time() < target_ts:
        time.sleep(0.1)

    resp2 = s.burst_submit_once(
        times=TEST_TIMES,
        roomid=TEST_ROOM_ID,
        seatid=first_seat,
        captcha=captcha2,
        token=token1,
        value=value1,
    )
    attempt2_ts = time.time()
    elapsed2 = attempt2_ts - start_ts
    logging.info(
        f"[test-captcha-stash] attempt2 (captcha2), elapsed={elapsed2:.3f}s, resp={resp2}"
    )

    # 再间隔 interval_sec 秒后使用 captcha3（第三次）
    target_ts = attempt2_ts + interval_sec
    logging.info(
        f"[test-captcha-stash] waiting until {target_ts:.3f} for attempt3 (interval={interval_sec}s)"
    )
    while time.time() < target_ts:
        time.sleep(0.1)

    resp3 = s.burst_submit_once(
        times=TEST_TIMES,
        roomid=TEST_ROOM_ID,
        seatid=first_seat,
        captcha=captcha3,
        token=token1,
        value=value1,
    )
    elapsed3 = time.time() - start_ts
    logging.info(
        f"[test-captcha-stash] attempt3 (captcha3), elapsed={elapsed3:.3f}s, resp={resp3}"
    )


def test_textclick_captcha(attempts: int = 3):
    """测试选字验证码（文字点击验证）。
    
    策略：
    - 登录一次
    - 获取选字验证码
    - 使用 OCR 识别文字位置
    - 提交验证并检查结果
    - 可以多次尝试以测试稳定性
    """
    s, first_seat = _build_session()
    if s is None:
        return
    
    logging.info(f"[test-textclick] Start textclick CAPTCHA test, attempts={attempts}")
    
    successes = 0
    failures = 0
    
    for attempt in range(1, attempts + 1):
        logging.info(f"\n[test-textclick] Attempt {attempt}/{attempts}")
        
        try:
            # 获取选字验证码数据
            logging.info("[test-textclick] Getting textclick captcha data...")
            captcha_token, image_url, target_text = s.get_textclick_captcha_data()
            
            if not captcha_token or not image_url:
                logging.error("[test-textclick] Failed to get captcha data")
                failures += 1
                continue
            
            logging.info(f"[test-textclick] Token: {captcha_token}")
            logging.info(f"[test-textclick] Target text: {target_text}")
            logging.info(f"[test-textclick] Image URL: {image_url}")
            
            # 使用 OCR 识别坐标
            logging.info("[test-textclick] Recognizing text positions with OCR...")
            positions = s._recognize_textclick_positions(image_url, target_text)
            
            if not positions:
                logging.error("[test-textclick] Failed to recognize positions")
                failures += 1
                continue
            
            logging.info(f"[test-textclick] Recognized positions: {positions}")
            
            # 提交验证
            logging.info("[test-textclick] Submitting verification...")
            validate_token = s._submit_captcha("textclick", captcha_token, positions)
            
            if validate_token:
                logging.info(f"✅ [test-textclick] Attempt {attempt} SUCCESS! Token: {validate_token}")
                successes += 1
            else:
                logging.warning(f"❌ [test-textclick] Attempt {attempt} FAILED (result=false)")
                failures += 1
        
        except Exception as e:
            logging.error(f"[test-textclick] Attempt {attempt} ERROR: {e}", exc_info=True)
            failures += 1
        
        # 间隔等待
        if attempt < attempts:
            logging.info("[test-textclick] Waiting 2 seconds before next attempt...")
            time.sleep(2)
    
    # 测试总结
    logging.info("\n" + "=" * 60)
    logging.info("[test-textclick] Test Summary")
    logging.info("=" * 60)
    logging.info(f"Total attempts: {attempts}")
    logging.info(f"Successes: {successes}")
    logging.info(f"Failures: {failures}")
    logging.info(f"Success rate: {successes}/{attempts} ({100*successes//attempts if attempts > 0 else 0}%)")
    logging.info("=" * 60)


if __name__ == "__main__":
    print("================ Token/Captcha 测试菜单 ================")
    print("1. 测试登录后的页面 token 有效时间 (token lifetime)")
    print("2. 测试滑块验证码 captcha 有效时间 (captcha lifetime)")
    print("3. 测试滑块验证码是否一次性 (captcha single-use)")
    print("4. 测试滑块验证码首次在指定延迟后使用 (captcha first-use delay)")
    print("5. 测试是否可以囤三份 captcha 并间隔 2 秒依次使用 (captcha stash three)")
    print("6. 测试选字验证码（文字点击）⭐ NEW")
    choice = input("请输入选项 (1/2/3/4/5/6): ").strip()

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
        # 默认三次间隔 2 秒，可以在函数调用里改间隔
        test_captcha_stash_three(2.0)
    elif choice == "6":
        # 测试选字验证码，默认尝试 3 次
        test_textclick_captcha(attempts=3)
    else:
        print("无效选项，已退出。")
