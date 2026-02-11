import os
import pickle
import datetime
import logging
import ssl
from datetime import timedelta
from prometheus_client import Counter, Histogram, Gauge
from view.mail_server import mailconf
from view.dingding import ding_sender
from conf import config

logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus 指标定义
# =============================================================================

url_check_success_total = Counter(
    "url_check_success_total",
    "Total number of URL check requests",
    ["task_name", "status_code", "method"],
)

url_check_response_time_seconds = Histogram(
    "url_check_response_time_seconds",
    "URL check response time in seconds",
    ["task_name", "method"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
)

url_check_timeout_total = Counter(
    "url_check_timeout_total",
    "Total number of URL check timeouts",
    ["task_name", "method"],
)

# url_check_ssl_expiry_days: SSL 证书剩余天数
# 标签: task_name, method
# 用法: 当剩余天数小于 warning_days 时告警
url_check_ssl_expiry_days = Gauge(
    "url_check_ssl_expiry_days",
    "SSL certificate expiry days remaining",
    ["task_name", "method"],
)

# url_check_ssl_verified: SSL 证书验证状态
# 标签: task_name, method, verified ("true" / "false")
# 用法: 区分是否跳过 SSL 验证
url_check_ssl_verified = Counter(
    "url_check_ssl_verified",
    "SSL certificate verification status",
    ["task_name", "method", "verified"],
)

# url_check_json_valid: JSON 解析结果
# 标签: task_name, method, status ("success" / "failed")
# 用法: 统计 JSON 解析成功率
url_check_json_valid = Counter(
    "url_check_json_valid",
    "JSON validation results",
    ["task_name", "method", "status"],
)

# url_check_json_path: JSON Path 验证结果
# 标签: task_name, method, matched ("true" / "false")
# 用法: 统计 JSON Path 字段匹配成功率
url_check_json_path = Counter(
    "url_check_json_path",
    "JSON Path validation results",
    ["task_name", "method", "matched"],
)


class cherker:
    def __init__(
        self,
        delay=0,
        stat_code=0,
        math_str=0,
        timeout=0,
        method=None,
        expect_json=False,
        json_path=None,
        json_path_value=None,
    ):
        """
        URL 检查结果处理器初始化

        功能：
            - 处理 URL 检查后的结果数据
            - 判定是否触发告警
            - 更新 Prometheus 指标

        属性：
            delay: 响应时间是否超阈值（0=正常，1=超时）
            stat_code: 状态码是否匹配（0=匹配，1=不匹配）
            stat_math_str: 关键字是否匹配（0=匹配，1=不匹配）
            timeout: 是否超时（0=正常，1=超时）
            method: HTTP 方法（"get" 或 "post"）
            task_name: 任务名称
            now_alarm: 当前告警状态字典
            message: 告警消息字典
            expect_json: 是否期望 JSON 响应
            json_path: JSON Path 表达式
            json_path_value: 期望的 JSON Path 值（字符串比较）
        """
        self.delay = delay
        self.stat_code = stat_code
        self.stat_math_str = math_str
        self.timeout = timeout
        self.task_name = None
        self.method = method
        self.expect_json = expect_json
        self.json_path = json_path
        self.json_path_value = json_path_value
        self.now_alarm = {
            "code_warm": 0,
            "delay_warm": 0,
            "math_warm": 0,
            "timeout_warm": 0,
        }
        self.message = {}

    def validate_json(
        self, content, expect_json=False, json_path_expr=None, json_path_value=None
    ):
        """
        JSON 验证方法

        功能：
            1. 尝试解析响应内容为 JSON
            2. 如果配置了 json_path，验证字段是否存在
            3. 如果配置了 json_path_value，验证值是否匹配（字符串比较）
            4. 更新 Prometheus 指标

        Args:
            content: 响应文本内容
            expect_json: 是否期望 JSON 响应
            json_path_expr: JSON Path 表达式（如 "$.status"）
            json_path_value: 期望的 JSON Path 值（字符串比较）

        Returns:
            tuple: (json_parse_ok, json_path_ok)
                - json_parse_ok: JSON 解析是否成功
                - json_path_ok: JSON Path 验证是否通过
        """
        json_parse_ok = False
        json_path_ok = False
        json_data = None

        url_check_json_valid.labels(
            task_name=self.task_name or "", method=self.method or "", status="pending"
        )

        if not expect_json:
            url_check_json_valid.labels(
                task_name=self.task_name or "",
                method=self.method or "",
                status="skipped",
            ).inc()
            return True, True

        try:
            import json

            json_data = json.loads(content)
            json_parse_ok = True
            url_check_json_valid.labels(
                task_name=self.task_name or "",
                method=self.method or "",
                status="success",
            ).inc()
        except (json.JSONDecodeError, TypeError):
            url_check_json_valid.labels(
                task_name=self.task_name or "",
                method=self.method or "",
                status="failed",
            ).inc()
            return False, False

        if not json_path_expr:
            return True, True

        try:
            from jsonpath_ng import parse

            matcher = parse(json_path_expr)
            match = matcher.find(json_data)
            if match:
                if json_path_value is not None:
                    match_value = match[0].value
                    # JSON 特殊值转换（JSON 原始值 → 字符串）
                    if match_value is True:
                        actual_value = "true"
                    elif match_value is False:
                        actual_value = "false"
                    elif match_value is None:
                        actual_value = "null"
                    else:
                        actual_value = str(match_value)

                    expected_value = str(json_path_value)
                    json_path_ok = actual_value == expected_value
                    logger.debug(
                        f"JSON Path 值比较: '{actual_value}' == '{expected_value}' -> {json_path_ok}"
                    )
                else:
                    json_path_ok = True
            else:
                json_path_ok = False
        except Exception as e:
            logger.warning(f"JSON Path 验证失败: {json_path_expr}, 错误: {e}")
            json_path_ok = False
        except Exception as e:
            logger.warning(f"JSON Path 验证失败: {json_path_expr}, 错误: {e}")
            json_path_ok = False

        url_check_json_path.labels(
            task_name=self.task_name or "",
            method=self.method or "",
            matched=str(json_path_ok).lower(),
        ).inc()

        return json_parse_ok, json_path_ok

    def send_warm(self, alarm=None, threshold=None):
        """
        发送告警通知（钉钉/邮件）

        功能：
            - 检测告警状态变化（从故障到恢复，或从恢复到故障）
            - 根据配置开关决定是否发送钉钉/邮件通知

        告警类型：
            - code_warm: 状态码错误
            - timeout_warm: 请求超时
            - math_warm: 关键字未匹配
            - delay_warm: 响应时间过长

        触发逻辑：
            - now_alarm=1 且 alarm=0：故障发生（发送告警）
            - now_alarm=0 且 alarm=1：故障恢复（发送恢复通知）

        配置开关（conf/config.py）：
            - enable_alerts: 总开关
            - enable_dingding: 钉钉开关
            - enable_mail: 邮件开关
        """
        # 状态码错误告警
        if self.now_alarm["code_warm"] == 1 and alarm["code_warm"] == 0:
            subject = "{} 状态码错误".format(self.task_name)
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_code"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_code"],
                )
        if self.now_alarm["timeout_warm"] == 1 and alarm["timeout_warm"] == 0:
            subject = "{} timeout".format(self.task_name)
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_timeout"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_timeout"],
                )
        if self.now_alarm["math_warm"] == 1 and alarm["math_warm"] == 0:
            subject = "{}没有匹配到关键字 {}".format(
                self.task_name, threshold["math_str"]
            )
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_math_str"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_math_str"],
                )
        if self.now_alarm["delay_warm"] == 1 and alarm["delay_warm"] == 0:
            subject = "{} 响应时间过长".format(self.task_name)
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_delay"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_delay"],
                )

        # 状态恢复通知
        if self.now_alarm["code_warm"] == 0 and alarm["code_warm"] == 1:
            subject = "{}  状态码错误:已经恢复".format(self.task_name)
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_code"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_code"],
                )
        if self.now_alarm["timeout_warm"] == 0 and alarm["timeout_warm"] == 1:
            subject = "{} timeout:已经恢复".format(self.task_name)
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_timeout"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_timeout"],
                )

        if self.now_alarm["math_warm"] == 0 and alarm["math_warm"] == 1:
            subject = "{}  没有匹配到关键字:{}  已经恢复".format(
                self.task_name, threshold["math_str"]
            )
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_math_str"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_math_str"],
                )
        if self.now_alarm["delay_warm"] == 0 and alarm["delay_warm"] == 1:
            subject = "{}  响应时间过长状态改变".format(self.task_name)
            if config.enable_dingding:
                ding_sender(title=subject, msg=self.message["stat_delay"])
            if config.enable_mail:
                mailconf(
                    tos=config.send_to,
                    subject=subject,
                    content=self.message["stat_delay"],
                )

    def first_run_task(self, status_data, threshold, time, datafile):
        """
        首次运行任务初始化

        功能：
            - 第一次检查某 URL 时调用
            - 初始化告警状态（默认都是正常）
            - 持久化首次检查结果到文件

        Args:
            status_data: 检查结果数据字典
            threshold: 配置阈值字典
            time: 检查时间字符串
            datafile: 持久化文件路径（data/{task_name}.pkl）
        """
        temp_dict = {}
        # 开始设置为0,都是对的，如果出现错误则修改状态码

        if status_data[self.task_name]["stat_code"] == 1:
            print("{} 状态码故障".format(self.task_name))
            self.now_alarm["code_warm"] = 1

        if status_data[self.task_name]["timeout"] == 1:
            self.now_alarm["timeout_warm"] = 1
            print("{} is timeout".format(self.task_name))

        if status_data[self.task_name]["stat_math_str"] == 1:
            self.now_alarm["math_warm"] = 1
            print("{} 不存在 {}这个字段".format(self.task_name, threshold["math_str"]))

        if status_data[self.task_name]["stat_delay"] == 1:
            self.now_alarm["delay_warm"] = 1
            print(
                "{},第一次运行{}响应时间超过预定设计的阈值，请检查阈值是否合理".format(
                    self.task_name, status_data[self.task_name]["delay"]
                )
            )

        # 根据内容发送消息
        alarm = {"code_warm": 0, "delay_warm": 0, "math_warm": 0, "timeout_warm": 0}
        self.send_warm(alarm=alarm, threshold=threshold)

        # 录入当前检查的alarm状态信息
        temp_dict["alarm"] = self.now_alarm
        print("录入", temp_dict)
        # 录入原始信息
        temp_dict[time.split()[0]] = [(status_data)]
        # print(temp_dict)

        with open(datafile, "wb") as f:
            pickle.dump(temp_dict, f)
            print("写入完毕")

    def make_data(self, data_dict):
        """
        处理 URL 检查结果数据

        功能：
            1. 从 data_dict 提取检查结果（状态码、响应时间、超时等）
            2. 与配置阈值对比，判定各项检查是否通过
            3. 验证 JSON 响应（如果配置了 expect_json）
            4. 持久化结果到 pickle 文件
            5. 触发告警（钉钉通知）
            6. 更新 Prometheus 指标

        Args:
            data_dict: URL 检查结果字典，包含以下字段：
                - url_name: 任务名称
                - url: 检查的 URL
                - stat_code: HTTP 状态码
                - timeout: 是否超时（0=否，1=是）
                - resp_time: 响应时间（毫秒）
                - contents: 响应内容
                - time: 检查时间
                - threshold: 配置阈值字典
                - expect_json: 是否期望 JSON 响应
                - json_path: JSON Path 表达式

        成功/失败判定逻辑：
            - 成功：timeout=0 且 stat_code == threshold['stat_code']
            - 失败（任一即失败）：
                * stat_code != threshold['stat_code']（状态码不匹配）
                * timeout == 1（请求超时）
                * stat_math_str == 1（关键字未匹配）
                * stat_delay == 1（响应时间超阈值）
                * json_parse_ok == False（JSON 解析失败）
                * json_path_ok == False（JSON Path 验证失败）
        """
        self.task_name = data_dict["url_name"]
        time = data_dict["time"]
        threshold = data_dict.get("threshold", {})
        expect_json = data_dict.get("expect_json", False)
        json_path = data_dict.get("json_path")
        json_path_value = data_dict.get("json_path_value")

        if data_dict["timeout"] == 0:
            code = data_dict["stat_code"]
            content = data_dict["contents"]
            rs_time = data_dict["resp_time"]

            if code != threshold.get("stat_code", 200):
                self.stat_code = 1

            if "math_str" in threshold:
                self.stat_math_str = 0 if threshold["math_str"] in content else 1

            if "delay" in threshold:
                self.delay = 0 if rs_time < threshold["delay"][0] else 1

            json_parse_ok, json_path_ok = self.validate_json(
                content,
                expect_json=expect_json,
                json_path_expr=json_path,
                json_path_value=json_path_value,
            )

            if expect_json and json_path:
                if not json_parse_ok or not json_path_ok:
                    self.stat_math_str = 1
        else:
            self.timeout = 1
            code = "timeout"
            rs_time = "timeout"
        # 生成状态数据
        status_data = {
            self.task_name: {
                "url": data_dict["url"],
                "code": code,
                "stat_code": self.stat_code,
                "delay": rs_time,
                "stat_delay": self.delay,
                "stat_math_str": self.stat_math_str,
                "timeout": self.timeout,
                "time": time,
            }
        }
        # 有了状态数据，就可以生成消息信息
        self.message["stat_code"] = "code:{}，threshold:{} URL:{}".format(
            status_data[self.task_name]["code"],
            threshold["stat_code"],
            status_data[self.task_name]["url"],
        )
        self.message["stat_timeout"] = "stat_timeout:{}，threshold: 0 URL:{}".format(
            status_data[self.task_name]["timeout"], status_data[self.task_name]["url"]
        )
        self.message["stat_math_str"] = (
            "匹配字段:{}, stat_math_str:{} threshold: 0 URL:{}".format(
                threshold["math_str"],
                status_data[self.task_name]["stat_math_str"],
                status_data[self.task_name]["url"],
            )
        )
        self.message["stat_delay"] = (
            "目前响应时间:{} 预设响应时间:{}  stat_delay:{}  threshold: 0  URL:{}".format(
                status_data[self.task_name]["delay"],
                threshold["delay"][0],
                status_data[self.task_name]["stat_delay"],
                status_data[self.task_name]["url"],
            )
        )

        # 根据任务分类，才不会出现io 冲突
        datafile = "data/{}.pkl".format(self.task_name)  # 文件名字
        # 一开始设计状态都是好的，生成一个现在的状态和之前的状态，两个对比，发出故障警告或者恢复警告
        # 第一次运行的时候没有文件，那么先生成文件并存入数据

        if not os.path.exists(datafile):
            self.first_run_task(status_data, threshold, time, datafile)

        else:
            f = open(datafile, "rb")
            temp_dict = pickle.load(f)
            f.close()
            # 保留时间数目
            histroy_day = (
                datetime.datetime.now()
                + datetime.timedelta(days=-config.history_datat_day)
            ).strftime("%Y-%m-%d")
            # 插入的key是当天时间
            key = str(time.split()[0])
            if key in temp_dict:
                # 取出当天数据
                today_list = temp_dict[time.split()[0]]
                # print(today_list)

                # 如果响应时间超时,我们设置连续超时多少次才告警
                if status_data[self.task_name]["stat_delay"] == 1:
                    # 检查次数
                    num = threshold["delay"][1]
                    # 检查
                    if len(today_list) + 1 >= num:
                        # 切割出最后的几次检查的次数的list
                        temp_list = today_list[-(num - 1) :]
                        # 初始超时次数为0，如果循环后发现都是超时的那么告警，设置delay_warm =1
                        c = 0
                        for his_data in temp_list:
                            if his_data[self.task_name]["stat_delay"] == 1:
                                c += 1
                        if c == num - 1:
                            print(
                                "{} 检查{}次，超过设定时间最后一次{}毫秒".format(
                                    self.task_name,
                                    num,
                                    status_data[self.task_name]["delay"],
                                )
                            )
                            self.now_alarm["delay_warm"] = 1

                    else:
                        # 如果今天检查的次数不够设置告警，则取出昨天的来计算
                        yes_time = (
                            datetime.datetime.now() + datetime.timedelta(days=-1)
                        ).strftime("%Y-%m-%d")
                        neednum = num - len(today_list) - 1
                        if (
                            yes_time in temp_dict
                            and len(temp_dict[yes_time]) >= neednum
                        ):
                            temp_list = temp_dict[yes_time][-(neednum):]
                            temp_list.extend(today_list)
                            c = 0
                            for his_data in temp_list:
                                if his_data[self.task_name]["stat_delay"] != 1:
                                    break
                                else:
                                    c += 1
                            if c == num - 1:
                                print(
                                    "{} 检查{}次，超过设定时间最后一次{}毫秒".format(
                                        self.task_name,
                                        num,
                                        status_data[self.task_name]["delay"],
                                    )
                                )
                                self.now_alarm["delay_warm"] = 1

                # temp_dict 之前保存的所有数据
                temp_dict[key].append(status_data)
                # print(temp_dict)

            # key不在现有的字典
            else:
                yes_time = (
                    datetime.datetime.now() + datetime.timedelta(days=-1)
                ).strftime("%Y-%m-%d")
                if status_data[self.task_name]["stat_delay"] == 1:
                    num = threshold["delay"][1]
                    if yes_time in temp_dict and len(temp_dict[yes_time]) >= num - 1:
                        c = 0
                        temp_list = temp_dict[yes_time][-(num - 1) :]
                        for his_data in temp_list:
                            if his_data[self.task_name]["stat_delay"] != 1:
                                break
                            else:
                                c += 1
                        if c == num - 1:
                            print(
                                "{} 检查{}次，超过设定时间最后一次{}毫秒".format(
                                    self.task_name,
                                    num,
                                    status_data[self.task_name]["delay"],
                                )
                            )
                            self.now_alarm["delay_warm"] = 1
                # 设置今天的第一个字典为空
                temp_dict[key] = []
                temp_dict[key].append(status_data)

            if status_data[self.task_name]["stat_code"] == 1:
                print(
                    "{} stat_code is wrong 不是第一次运行   {}".format(
                        self.task_name, code
                    )
                )
                self.now_alarm["code_warm"] = 1

            if status_data[self.task_name]["timeout"] == 1:
                print("{} is timeout".format(self.task_name))
                self.now_alarm["timeout_warm"] = 1

            if status_data[self.task_name]["stat_math_str"] == 1:
                print(
                    "{} 不存在 {}这个字段".format(self.task_name, threshold["math_str"])
                )
                self.now_alarm["math_warm"] = 1

            # 根据开关决定是否发送告警通知
            # enable_alerts = True: 发送钉钉/邮件告警
            # enable_alerts = False: 仅收集 Prometheus 指标（通过 Alertmanager 告警）
            if config.enable_alerts:
                self.send_warm(alarm=temp_dict["alarm"], threshold=threshold)
            else:
                logger.debug("告警通知已禁用（enable_alerts=False），跳过 send_warm")
            temp_dict["alarm"] = self.now_alarm
            if histroy_day in temp_dict:
                # 根据配置文件删除历史数据保留天数
                del temp_dict[histroy_day]
            print("第二次写入")
            # print(temp_dict)
            with open(datafile, "wb") as f:
                pickle.dump(temp_dict, f)

        # ==========================================================================
        # 更新 Prometheus 指标（告警开关不影响指标收集）
        # ==========================================================================
        # 根据检查结果更新对应的指标

        # 获取 HTTP 方法（优先使用 self.method，否则为 unknown）
        method = self.method if self.method else "unknown"

        # 超时情况：更新 timeout 计数器（status_code 字段不存在）
        if self.timeout == 1:
            url_check_timeout_total.labels(
                task_name=self.task_name, method=method
            ).inc()
        else:
            # 正常响应：更新 success 计数器（使用实际状态码作为标签）
            status_code = str(code)
            url_check_success_total.labels(
                task_name=self.task_name, status_code=status_code, method=method
            ).inc()

            # 记录响应时间（转换为秒）
            if isinstance(rs_time, (int, float)):
                url_check_response_time_seconds.labels(
                    task_name=self.task_name, method=method
                ).observe(rs_time / 1000.0)
