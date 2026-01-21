import json
import time
import argparse
import os
import logging
import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


from utils import reserve, get_user_credentials


def _now(action: bool) -> datetime.datetime:
    """在本地和 GitHub Actions 使用不同的时间基准.

    - 本地模式(action=False): 使用系统本地时间, 方便你本机调试;
    - GitHub Actions(action=True): 明确使用 UTC+8(北京时间), 不依赖 runner 的时区设置.
    """
    if action:
        # GitHub Actions 上统一用 UTC+8 作为逻辑时间(北京时间)
        return datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    # 本地直接用系统时间
    return datetime.datetime.now()


get_current_time = lambda action: _now(action).strftime("%H:%M:%S")
get_current_dayofweek = lambda action: _now(action).strftime("%A")


SLEEPTIME = 0.2  # 每次抢座的间隔
ENDTIME = "19:10:00"  # 根据学校的预约座位时间+1min即可

ENABLE_SLIDER = True  # 是否有滑块验证（调试阶段先关闭）
MAX_ATTEMPT = 205  # 最大尝试次数
RESERVE_NEXT_DAY = True  # 预约明天而不是今天的


def login_and_reserve(users, usernames, passwords, action, success_list=None):
    logging.info(
        f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )

    usernames_list, passwords_list = None, None
    if action:
        if not usernames or not passwords:
            raise Exception("USERNAMES or PASSWORDS not configured correctly in env")
        usernames_list = usernames.split(",")
        passwords_list = passwords.split(",")
        if len(usernames_list) != len(passwords_list):
            raise Exception("USERNAMES and PASSWORDS count mismatch")

    if success_list is None:
        success_list = [False] * len(users)
    current_dayofweek = get_current_dayofweek(action)
    for index, user in enumerate(users):
        username = user["username"]
        password = user["password"]
        times = user["times"]
        roomid = user["roomid"]
        seatid = user["seatid"]
        daysofweek = user["daysofweek"]

        # 如果今天不在该配置的 daysofweek 中，直接跳过
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue

        if action:
            if len(usernames_list) == 1:
                # 只有一个账号，所有配置都用这个账号
                username = usernames_list[0]
                password = passwords_list[0]
            elif index < len(usernames_list):
                username = usernames_list[index]
                password = passwords_list[index]
            else:
                logging.error(
                    "Index out of range for USERNAMES/PASSWORDS, skipping this config."
                )
                continue

        if not success_list[index]:
            logging.info(
                f"----------- {username} -- {times} -- {seatid} try -----------"
            )
            s = reserve(
                sleep_time=SLEEPTIME,
                max_attempt=MAX_ATTEMPT,
                enable_slider=ENABLE_SLIDER,
                reserve_next_day=RESERVE_NEXT_DAY,
            )
            s.get_login_status()
            s.login(username, password)
            s.requests.headers.update({"Host": "office.chaoxing.com"})
            suc = s.submit(times, roomid, seatid, action)
            success_list[index] = suc
    return success_list


def main(users, action=False):
    current_time = get_current_time(action)
    logging.info(f"start time {current_time}, action {'on' if action else 'off'}")
    attempt_times = 0
    usernames, passwords = None, None
    if action:
        usernames, passwords = get_user_credentials(action)
    success_list = None
    current_dayofweek = get_current_dayofweek(action)
    today_reservation_num = sum(
        1 for d in users if current_dayofweek in d.get("daysofweek")
    )
    while current_time < ENDTIME:
        attempt_times += 1
        # try:
        success_list = login_and_reserve(
            users, usernames, passwords, action, success_list
        )
        # except Exception as e:
        #     print(f"An error occurred: {e}")
        print(
            f"attempt time {attempt_times}, time now {current_time}, success list {success_list}"
        )
        current_time = get_current_time(action)
        if sum(success_list) == today_reservation_num:
            print(f"reserved successfully!")
            return


def debug(users, action=False):
    logging.info(
        f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )
    suc = False
    logging.info(f" Debug Mode start! , action {'on' if action else 'off'}")

    usernames_list, passwords_list = None, None
    if action:
        usernames, passwords = get_user_credentials(action)
        if not usernames or not passwords:
            logging.error("USERNAMES or PASSWORDS not configured correctly in env.")
            return
        usernames_list = usernames.split(",")
        passwords_list = passwords.split(",")
        if len(usernames_list) != len(passwords_list):
            logging.error("USERNAMES and PASSWORDS count mismatch.")
            return

    current_dayofweek = get_current_dayofweek(action)
    for index, user in enumerate(users):
        username = user["username"]
        password = user["password"]
        times = user["times"]
        roomid = user["roomid"]
        seatid = user["seatid"]
        daysofweek = user["daysofweek"]
        if type(seatid) == str:
            seatid = [seatid]

        # 如果今天不在该配置的 daysofweek 中，直接跳过，不处理账号
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue

        # 在 GitHub Actions 中，从环境变量获取账号密码
        if action:
            if len(usernames_list) == 1:
                # 只有一个账号时，所有配置都用这个账号
                username = usernames_list[0]
                password = passwords_list[0]
            elif index < len(usernames_list):
                username = usernames_list[index]
                password = passwords_list[index]
            else:
                logging.error(
                    "Index out of range for USERNAMES/PASSWORDS, skipping this config."
                )
                continue

        logging.info(f"----------- {username} -- {times} -- {seatid} try -----------")
        s = reserve(
            sleep_time=SLEEPTIME,
            max_attempt=MAX_ATTEMPT,
            enable_slider=ENABLE_SLIDER,
            reserve_next_day=RESERVE_NEXT_DAY,
        )
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({"Host": "office.chaoxing.com"})
        suc = s.submit(times, roomid, seatid, action)
        if suc:
            return


def get_roomid(args1, args2):
    username = input("请输入用户名：")
    password = input("请输入密码：")
    s = reserve(
        sleep_time=SLEEPTIME,
        max_attempt=MAX_ATTEMPT,
        enable_slider=ENABLE_SLIDER,
        reserve_next_day=RESERVE_NEXT_DAY,
    )
    s.get_login_status()
    s.login(username=username, password=password)
    s.requests.headers.update({"Host": "office.chaoxing.com"})
    encode = input("请输入deptldEnc：")
    s.roomid(encode)


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    parser = argparse.ArgumentParser(prog="Chao Xing seat auto reserve")
    parser.add_argument("-u", "--user", default=config_path, help="user config file")
    parser.add_argument(
        "-m",
        "--method",
        default="reserve",
        choices=["reserve", "debug", "room"],
        help="for debug",
    )
    parser.add_argument(
        "-a",
        "--action",
        action="store_true",
        help="use --action to enable in github action",
    )
    args = parser.parse_args()
    func_dict = {"reserve": main, "debug": debug, "room": get_roomid}
    with open(args.user, "r+") as data:
        usersdata = json.load(data)["reserve"]
    func_dict[args.method](usersdata, args.action)
