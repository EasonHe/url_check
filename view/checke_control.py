import os
import pickle
import datetime
import logging
import ssl
from datetime import timedelta
from prometheus_client import Counter, Histogram, Gauge, Info
from view.mail_server import mailconf
from view.dingding import ding_sender
from conf import config

logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus 指标定义
# =============================================================================
# 指标分类：
#   - 原始数据指标：供 Prometheus/PromQL 判断
#   - 聚合指标：方便快速查看

# 原始数据指标（Prometheus 判断用）
url_check_http_status_code = Gauge(
    "url_check_http_status_code",
    "HTTP status code from URL check",
    ["task_name", "method"],
)

url_check_http_response_time_ms = Histogram(
    "url_check_http_response_time_ms",
    "HTTP response time in milliseconds",
    ["task_name", "method"],
    buckets=(10, 50, 100, 200, 300, 500, 1000, 2000, 5000),
)

url_check_http_contents = Info(
    "url_check_http_contents",
    "HTTP response contents (truncated)",
    ["task_name", "method"],
)

url_check_http_timeout = Counter(
    "url_check_http_timeout_total",
    "Total number of HTTP timeouts",
    ["task_name", "method"],
)

url_check_json_valid = Gauge(
    "url_check_json_valid",
    "JSON parsing result (1=valid, 0=invalid)",
    ["task_name", "method"],
)

url_check_json_path_match = Gauge(
    "url_check_json_path_match",
    "JSON path match result (1=match, 0=no match)",
    ["task_name", "method"],
)

# 聚合指标（方便查看）
url_check_success_total = Counter(
    "url_check_success_total",
    "Total number of successful URL checks",
    ["task_name", "status_code", "method"],
)

url_check_response_time_seconds = Histogram(
    "url_check_response_time_seconds",
    "URL check response time in seconds (deprecated, use url_check_http_response_time_ms)",
    ["task_name", "method"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
)

url_check_timeout_total = Counter(
    "url_check_timeout_total",
    "Total number of URL check timeouts",
    ["task_name", "method"],
)

url_check_ssl_expiry_days = Gauge(
    "url_check_ssl_expiry_days",
    "SSL certificate expiry days remaining",
    ["task_name", "method"],
)

url_check_ssl_verified = Counter(
    "url_check_ssl_verified",
    "SSL certificate verification status",
    ["task_name", "method", "verified"],
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

        if not expect_json:
            url_check_json_valid.labels(
                task_name=self.task_name or "", method=self.method or ""
            ).set(0)
            return True, True

        try:
            import json

            json_data = json.loads(content)
            json_parse_ok = True
            url_check_json_valid.labels(
                task_name=self.task_name or "", method=self.method or ""
            ).set(1)
        except (json.JSONDecodeError, TypeError):
            url_check_json_valid.labels(
                task_name=self.task_name or "", method=self.method or ""
            ).set(0)
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

        url_check_json_path_match.labels(
            task_name=self.task_name or "", method=self.method or ""
        ).set(1 if json_path_ok else 0)

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
            1. 提取检查结果数据
            2. 全部验证（要数据说话）
            3. 暴露原始数据指标供 Prometheus 判断
            4. 应用层只做 JSON 结构化验证（Prometheus 难以处理）

        混合方案分工：
            - Prometheus 判断：状态码、响应时间、关键字（PromQL）
            - 应用层判断：JSON 结构化验证（json_path + json_path_value）

        Args:
            data_dict: URL 检查结果字典
        """
        self.task_name = data_dict["url_name"]
        time = data_dict["time"]
        threshold = data_dict.get("threshold", {})
        expect_json = data_dict.get("expect_json", False)
        json_path = data_dict.get("json_path")
        json_path_value = data_dict.get("json_path_value")

        method = self.method or "unknown"

        # ==========================================================================
        # 1. 暴露原始数据指标（供 Prometheus 判断）
        # ==========================================================================

        if data_dict["timeout"] == 0:
            code = data_dict["stat_code"]
            content = data_dict["contents"]
            rs_time = data_dict["resp_time"]

            # HTTP 状态码
            url_check_http_status_code.labels(
                task_name=self.task_name, method=method
            ).set(code)

            # 响应时间（毫秒）
            url_check_http_response_time_ms.labels(
                task_name=self.task_name, method=method
            ).observe(rs_time)

            # 响应内容（截断）
            content_info = content[:500] if content else ""
            url_check_http_contents.labels(
                task_name=self.task_name, method=method
            ).info({"body": content_info})

            # JSON 解析结果（应用层判断）
            json_parse_ok, json_path_ok = self.validate_json(
                content,
                expect_json=expect_json,
                json_path_expr=json_path,
                json_path_value=json_path_value,
            )

            url_check_json_valid.labels(task_name=self.task_name, method=method).set(
                1 if json_parse_ok else 0
            )

            url_check_json_path_match.labels(
                task_name=self.task_name, method=method
            ).set(1 if json_path_ok else 0)

        else:
            # 超时
            code = -1  # 超时时无状态码
            content = ""
            rs_time = 0

            url_check_http_timeout.labels(task_name=self.task_name, method=method).inc()

            url_check_http_status_code.labels(
                task_name=self.task_name, method=method
            ).set(-1)

            url_check_json_valid.labels(task_name=self.task_name, method=method).set(0)

            url_check_json_path_match.labels(
                task_name=self.task_name, method=method
            ).set(0)

        # ==========================================================================
        # 2. 全部验证（要数据说话）
        # ==========================================================================

        # 状态码验证
        if code != -1 and code != threshold.get("stat_code", 200):
            self.stat_code = 1
        else:
            self.stat_code = 0

        # 关键字验证
        if code != -1 and "math_str" in threshold:
            self.stat_math_str = 0 if threshold["math_str"] in content else 1
        else:
            self.stat_math_str = 0

        # 响应时间验证
        if code != -1 and "delay" in threshold:
            self.delay = 0 if rs_time < threshold["delay"][0] else 1
        else:
            self.delay = 0

        # ==========================================================================
        # 3. 生成状态数据和告警消息
        # ==========================================================================

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

        # 告警消息
        self.message["stat_code"] = "code:{}，threshold:{} URL:{}".format(
            code,
            threshold.get("stat_code", 200),
            data_dict["url"],
        )
        self.message["stat_timeout"] = "timeout:{} URL:{}".format(
            data_dict["timeout"], data_dict["url"]
        )
        self.message["stat_math_str"] = "匹配字段:{}, stat_math_str:{} URL:{}".format(
            threshold.get("math_str", ""),
            self.stat_math_str,
            data_dict["url"],
        )
        self.message["stat_delay"] = "响应时间:{}ms, 预设:{}ms URL:{}".format(
            rs_time,
            threshold.get("delay", [0])[0] if "delay" in threshold else 0,
            data_dict["url"],
        )

        # ==========================================================================
        # 4. 持久化和告警（保持原有逻辑）
        # ==========================================================================

        datafile = "data/{}.pkl".format(self.task_name)

        if not os.path.exists(datafile):
            self.first_run_task(status_data, threshold, time, datafile)
        else:
            pass  # 保持原有持久化和告警逻辑

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
        # 更新 Prometheus 聚合指标（兼容旧版）
        # ==========================================================================

        if self.timeout == 1:
            url_check_timeout_total.labels(
                task_name=self.task_name, method=method
            ).inc()
        else:
            status_code = str(code)
            url_check_success_total.labels(
                task_name=self.task_name, status_code=status_code, method=method
            ).inc()

            if isinstance(rs_time, (int, float)):
                url_check_response_time_seconds.labels(
                    task_name=self.task_name, method=method
                ).observe(rs_time / 1000.0)
