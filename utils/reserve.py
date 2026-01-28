from utils import AES_Encrypt, enc, generate_captcha_key, verify_param
import json
import requests
import re
import time
import logging
import datetime
from urllib3.exceptions import InsecureRequestWarning


def get_date(day_offset: int = 0):
    """基于北京时间获取日期字符串，避免时区混乱。"""
    beijing_today = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date()
    offset_day = beijing_today + datetime.timedelta(days=day_offset)
    return offset_day.strftime("%Y-%m-%d")


class reserve:
    def __init__(
        self,
        sleep_time=0.2,
        max_attempt=50,
        enable_slider=False,
        reserve_next_day=False,
    ):
        self.login_page = (
            "https://passport2.chaoxing.com/mlogin?loginType=1&newversion=true&fid="
        )
        self.url = (
            "https://office.chaoxing.com/front/third/apps/seat/code?id={}&seatNum={}"
        )
        self.submit_url = "https://office.chaoxing.com/data/apps/seat/submit"
        self.seat_url = "https://office.chaoxing.com/data/apps/seat/getusedtimes"
        self.login_url = "https://passport2.chaoxing.com/fanyalogin"
        self.token = ""
        self.success_times = 0
        self.fail_dict = []
        self.submit_msg = []
        self.requests = requests.session()
        # 预编译 submit_enc 提取正则，避免每次重新解析
        self.submit_enc_pattern = re.compile(r'id="submit_enc"\s+value="(.*?)"')
        self.headers = {
            "Referer": "https://office.chaoxing.com/",
            "Host": "captcha.chaoxing.com",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        }
        self.login_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "cache-control": "no-cache",
            "Connection": "keep-alive",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.3 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1 wechatdevtools/1.05.2109131 MicroMessenger/8.0.5 Language/zh_CN webview/16364215743155638",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "passport2.chaoxing.com",
        }

        self.sleep_time = sleep_time
        self.max_attempt = max_attempt
        self.enable_slider = enable_slider
        self.reserve_next_day = reserve_next_day
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # login and page token
    def _get_page_token(self, url, require_value=False):
        """从页面提取提交用的 token。

        新版页面只有一个隐藏字段 submit_enc，不再有单独的 algorithm。
        实测行为是：submit_enc 既作为页面 token，也作为 enc 算法的"算法值"。
        因此这里直接用 submit_enc 作为两者。
        """
        response = self.requests.get(url=url, verify=False)
        # 直接使用 requests 的 text 解码，并用预编译正则提取，提高一点点性能
        html = response.text
        match = self.submit_enc_pattern.search(html)
        if not match:
            logging.error(f"Failed to get token from {url}")
            return "", ""
        token = match.group(1)
        # 现在页面没有单独的 algorithm 字段，直接复用 submit_enc
        algorithm_value = token if require_value else ""
        return token, algorithm_value

    def get_login_status(self):
        self.requests.headers = self.login_headers
        self.requests.get(url=self.login_page, verify=False)

    def login(self, username, password):
        username = AES_Encrypt(username)
        password = AES_Encrypt(password)
        parm = {
            "fid": -1,
            "uname": username,
            "password": password,
            "refer": "http%3A%2F%2Foffice.chaoxing.com%2Ffront%2Fthird%2Fapps%2Fseat%2Fcode%3Fid%3D4219%26seatNum%3D380",
            "t": True,
        }
        jsons = self.requests.post(url=self.login_url, params=parm, verify=False)
        obj = jsons.json()
        if obj["status"]:
            logging.info(f"User {username} login successfully")
            return (True, "")
        else:
            logging.info(
                f"User {username} login failed. Please check you password and username! "
            )
            return (False, obj["msg2"])

    # extra: get roomid
    def roomid(self, encode):
        url = f"https://office.chaoxing.com/data/apps/seat/room/list?cpage=1&pageSize=100&firstLevelName=&secondLevelName=&thirdLevelName=&deptIdEnc={encode}"
        json_data = self.requests.get(url=url).content.decode("utf-8")
        ori_data = json.loads(json_data)
        for i in ori_data["data"]["seatRoomList"]:
            info = f'{i["firstLevelName"]}-{i["secondLevelName"]}-{i["thirdLevelName"]} id为：{i["id"]}'
            print(info)

    # solve captcha

    def resolve_captcha(self):
        logging.info(f"Start to resolve captcha token")
        captcha_token, bg, tp = self.get_slide_captcha_data()
        logging.info(f"Successfully get prepared captcha_token {captcha_token}")
        logging.info(f"Captcha Image URL-small {tp}, URL-big {bg}")
        x = self.x_distance(bg, tp)
        logging.info(f"Successfully calculate the captcha distance {x}")

        params = {
            "callback": "jQuery33109180509737430778_1716381333117",
            "captchaId": "42sxgHoTPTKbt0uZxPJ7ssOvtXr3ZgZ1",
            "type": "slide",
            "token": captcha_token,
            "textClickArr": json.dumps([{"x": x}]),
            "coordinate": json.dumps([]),
            "runEnv": "10",
            "version": "1.1.18",
            "_": int(time.time() * 1000),
        }
        response = self.requests.get(
            f"https://captcha.chaoxing.com/captcha/check/verification/result",
            params=params,
            headers=self.headers,
        )
        text = response.text.replace(
            "jQuery33109180509737430778_1716381333117(", ""
        ).replace(")", "")
        data = json.loads(text)
        logging.info(f"Successfully resolve the captcha token {data}")
        try:
            validate_val = json.loads(data["extraData"])["validate"]
            return validate_val
        except KeyError as e:
            logging.info("Can't load validate value. Maybe server return mistake.")
            return ""

    def get_slide_captcha_data(self):
        url = "https://captcha.chaoxing.com/captcha/get/verification/image"
        timestamp = int(time.time() * 1000)
        capture_key, token = generate_captcha_key(timestamp)
        referer = f"https://office.chaoxing.com/front/third/apps/seat/code?id=3993&seatNum=0199"
        params = {
            "callback": f"jQuery33107685004390294206_1716461324846",
            "captchaId": "42sxgHoTPTKbt0uZxPJ7ssOvtXr3ZgZ1",
            "type": "slide",
            "version": "1.1.18",
            "captchaKey": capture_key,
            "token": token,
            "referer": referer,
            "_": timestamp,
            "d": "a",
            "b": "a",
        }
        response = self.requests.get(url=url, params=params, headers=self.headers)
        content = response.text

        data = content.replace(
            "jQuery33107685004390294206_1716461324846(", ")"
        ).replace(")", "")
        data = json.loads(data)
        captcha_token = data["token"]
        bg = data["imageVerificationVo"]["shadeImage"]
        tp = data["imageVerificationVo"]["cutoutImage"]
        return captcha_token, bg, tp

    def x_distance(self, bg, tp):
        import numpy as np
        import cv2
        import os
        import time as _time

        def cut_slide(slide):
            slider_array = np.frombuffer(slide, np.uint8)
            slider_image = cv2.imdecode(slider_array, cv2.IMREAD_UNCHANGED)
            slider_part = slider_image[:, :, :3]
            mask = slider_image[:, :, 3]
            mask[mask != 0] = 255
            x, y, w, h = cv2.boundingRect(mask)
            cropped_image = slider_part[y : y + h, x : x + w]
            return cropped_image

        c_captcha_headers = {
            "Referer": "https://office.chaoxing.com/",
            "Host": "captcha-b.chaoxing.com",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        }
        bgc = self.requests.get(bg, headers=c_captcha_headers)
        tpc = self.requests.get(tp, headers=c_captcha_headers)
        bg_bytes, tp_bytes = bgc.content, tpc.content

        # 调试：把当前验证码图片保存到本地，方便人工查看和调试
        try:
            ts = int(_time.time() * 1000)
            debug_dir = os.path.join(os.path.dirname(__file__), "..", "captcha_debug")
            os.makedirs(debug_dir, exist_ok=True)
            bg_path = os.path.join(debug_dir, f"bg_{ts}.jpg")
            tp_path = os.path.join(debug_dir, f"tp_{ts}.png")
            with open(bg_path, "wb") as f:
                f.write(bg_bytes)
            with open(tp_path, "wb") as f:
                f.write(tp_bytes)
            logging.info(f"Saved captcha images to {bg_path} and {tp_path}")
        except Exception as e:
            logging.warning(f"Failed to save captcha images: {e}")

        bg_img = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
        tp_img = cut_slide(tp_bytes)
        bg_edge = cv2.Canny(bg_img, 100, 200)
        tp_edge = cv2.Canny(tp_img, 100, 200)
        bg_pic = cv2.cvtColor(bg_edge, cv2.COLOR_GRAY2RGB)
        tp_pic = cv2.cvtColor(tp_edge, cv2.COLOR_GRAY2RGB)
        res = cv2.matchTemplate(bg_pic, tp_pic, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(res)
        tl = max_loc
        return tl[0]

    def submit(self, times, roomid, seatid, action, endtime_hms: str | None = None):
        for seat in seatid:
            suc = False
            while ~suc and self.max_attempt > 0:
                # 如果配置了结束时间，并且在 GitHub Actions 模式下，达到或超过结束时间就立刻停止循环
                if endtime_hms and action:
                    beijing_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
                    current_hms = beijing_now.strftime("%H:%M:%S")
                    if current_hms >= endtime_hms:
                        logging.info(
                            f"[submit] Current Beijing time {current_hms} >= ENDTIME {endtime_hms}, stop submit loop"
                        )
                        return suc

                token, value = self._get_page_token(
                    self.url.format(roomid, seat), require_value=True
                )
                logging.info(f"Get token: {token}")
                captcha = self.resolve_captcha() if self.enable_slider else ""
                logging.info(f"Captcha token {captcha}")
                suc = self.get_submit(
                    self.submit_url,
                    times=times,
                    token=token,
                    roomid=roomid,
                    seatid=seat,
                    captcha=captcha,
                    action=action,
                    value=value,
                )
                if suc:
                    return suc
                time.sleep(self.sleep_time)
                self.max_attempt -= 1
        return suc

    def get_submit(
        self, url, times, token, roomid, seatid, captcha="", action=False, value=""
    ):
        # 统一以北京时间（UTC+8）的"今天"为基准，不再区分本地 / GitHub Actions，
        # 是否预约明天仅由 self.reserve_next_day 决定。
        beijing_today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)).date()
        delta_day = 1 if self.reserve_next_day else 0
        day = beijing_today + datetime.timedelta(days=delta_day)
        parm = {
            "roomId": roomid,
            "startTime": times[0],
            "endTime": times[1],
            "day": str(day),
            "seatNum": seatid,
            "captcha": captcha,
            "token": token,
            "type": "1",
            "verifyData": "1",
        }
        logging.info(f"submit parameter {parm} ")
        # parm["enc"] = enc(parm)
        parm["enc"] = verify_param(parm, value)
        html = self.requests.post(url=url, params=parm, verify=True).content.decode(
            "utf-8"
        )
        self.submit_msg.append(
            times[0] + "~" + times[1] + ":  " + str(json.loads(html))
        )
        logging.info(json.loads(html))
        return json.loads(html)["success"]

    def burst_submit_once(self, times, roomid, seatid, captcha, token, value):
        """单次提交，返回完整响应 dict，用于 1.8 秒高频窗口内的逻辑判断。"""
        beijing_today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)).date()
        delta_day = 1 if self.reserve_next_day else 0
        day = beijing_today + datetime.timedelta(days=delta_day)
        parm = {
            "roomId": roomid,
            "startTime": times[0],
            "endTime": times[1],
            "day": str(day),
            "seatNum": seatid,
            "captcha": captcha,
            "token": token,
            "type": "1",
            "verifyData": "1",
        }
        logging.info(f"[burst] submit parameter {parm} ")
        parm["enc"] = verify_param(parm, value)
        html = self.requests.post(url=self.submit_url, params=parm, verify=True).content.decode(
            "utf-8"
        )
        data = json.loads(html)
        self.submit_msg.append(times[0] + "~" + times[1] + ":  " + str(data))
        logging.info(data)
        return data
