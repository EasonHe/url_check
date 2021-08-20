import os
import pickle
import  datetime
from  view.mail_server import mailconf
from view.dingding import ding_sender
from  conf import config


class cherker():
    def __init__(self,delay=0,stat_code=0,math_str=0,timeout=0):
        self.delay = delay
        self.stat_code=stat_code
        self.stat_math_str = math_str
        self.timeout = timeout
        self.task_name = None
        self.now_alarm = {'code_warm': 0, 'delay_warm': 0, 'math_warm': 0, 'timeout_warm': 0}
        self.message = {}
    def send_warm(self,alarm=None,threshold=None):
        if self.now_alarm['code_warm'] == 1 and alarm['code_warm'] == 0:
            subject ='{} 状态码错误'.format(self.task_name)
            #mailconf(tos=config.send_to,subject=subject,content=self.message['stat_code'])
            ding_sender(title=subject,msg=self.message['stat_code'])
        if self.now_alarm['timeout_warm'] == 1 and alarm['timeout_warm'] ==0:
            subject = '{} timeout'.format(self.task_name)
            #mailconf(tos=config.send_to,subject=subject,content=self.message['stat_timeout'])
            ding_sender(title=subject, msg=self.message['stat_timeout'])
        if self.now_alarm['math_warm'] == 1 and alarm['math_warm'] == 0:
            subject = '{}没有匹配到关键字 {}'.format(self.task_name,threshold['math_str'])
            #mailconf(tos=config.send_to,subject=subject,content=self.message['stat_math_str'])
            ding_sender(title=subject, msg=self.message['stat_math_str'])
        if self.now_alarm['delay_warm'] == 1 and alarm['delay_warm'] == 0:
            subject = '{} 响应时间过长'.format(self.task_name)
            #mailconf(tos=config.send_to,subject=subject,content=self.message['stat_delay'])
            ding_sender(title=subject, msg=self.message['stat_delay'])
        #恢复发出邮件
        if self.now_alarm['code_warm'] == 0 and alarm['code_warm'] == 1:
            subject = '{}  状态码错误:已经恢复'.format(self.task_name)
            #mailconf(tos=config.send_to, subject=subject, content=self.message['stat_code'])
            ding_sender(title=subject, msg=self.message['stat_code'])
        if self.now_alarm['timeout_warm'] == 0 and alarm['timeout_warm'] == 1:
            subject = '{} timeout:已经恢复'.format(self.task_name)
            #mailconf(tos=config.send_to, subject=subject, content=self.message['stat_timeout'])
            ding_sender(title=subject, msg=self.message['stat_timeout'])

        if self.now_alarm['math_warm'] == 0 and alarm['math_warm'] == 1:
            subject = '{}  没有匹配到关键字:{}  已经恢复'.format(self.task_name,threshold['math_str'])
            #mailconf(tos=config.send_to, subject=subject, content=self.message['stat_math_str'])
            ding_sender(title=subject, msg=self.message['stat_math_str'])
        if self.now_alarm['delay_warm'] == 0 and alarm['delay_warm'] == 1:
            subject = '{}  响应时间过长状态改变'.format(self.task_name)
            #mailconf(tos=config.send_to, subject=subject, content=self.message['stat_delay'])
            ding_sender(title=subject, msg=self.message['stat_delay'])
    def first_run_task(self,status_data,threshold,time,datafile):
        temp_dict = {}
        # 开始设置为0,都是对的，如果出现错误则修改状态码

        if status_data[self.task_name]['stat_code'] == 1:
            print('{} 状态码故障'.format(self.task_name))
            self.now_alarm['code_warm'] = 1


        if status_data[self.task_name]['timeout'] == 1:
            self.now_alarm['timeout_warm'] = 1
            print('{} is timeout'.format(self.task_name))

        if status_data[self.task_name]['stat_math_str'] == 1:
            self.now_alarm['math_warm'] = 1
            print('{} 不存在 {}这个字段'.format(self.task_name, threshold['math_str']))


        if status_data[self.task_name]['stat_delay'] == 1:
            self.now_alarm['delay_warm'] = 1
            print('{},第一次运行{}响应时间超过预定设计的阈值，请检查阈值是否合理'.format(self.task_name, status_data[self.task_name]['delay']))




        # 根据内容发送消息
        alarm = {'code_warm': 0, 'delay_warm': 0, 'math_warm': 0, 'timeout_warm': 0}
        self.send_warm(alarm=alarm,threshold=threshold)

        # 录入当前检查的alarm状态信息
        temp_dict['alarm'] = self.now_alarm
        print('录入',temp_dict)
        # 录入原始信息
        temp_dict[time.split()[0]] = [(status_data)]
        #print(temp_dict)

        with open(datafile, 'wb') as f:
            pickle.dump(temp_dict, f)
            print('写入完毕')


    def make_data(self,data_dict):
        #任务名称
        self.task_name = data_dict['url_name']
        #检查时间
        time = data_dict['time']
        #检查参数比如超时，关键字，状态码，这个是配置参数，或者生成的默认参数
        threshold = data_dict['threshold']
        #如果timout = 0 那么 说明没有超时
        if data_dict['timeout'] == 0:
            #状态吗
            code = data_dict['stat_code']
            #内容
            content = data_dict['contents']
            #响应时间
            rs_time = data_dict['resp_time']
            #如果状态码不等于预设的值，那么stat_code =1 说明为状态码故障
            if code != threshold['stat_code']:
                self.stat_code = 1
            #如果未匹配到关键字，那么math_str =1 说明故障。
            if 'math_str' in threshold:
                self.stat_math_str = 0  if threshold['math_str'] in content else 1
            #如果响应时间超过预设的值，那么 delay = 1
            if  'delay' in  threshold:
                self.delay = 0 if rs_time < threshold['delay'][0] else 1
        else:
            self.timeout = 1
            code='timeout'
            rs_time='timeout'
        #生成状态数据
        status_data = {self.task_name: {'url':data_dict['url'],'code':code,'stat_code':self.stat_code,'delay':rs_time,'stat_delay': self.delay,'stat_math_str':self.stat_math_str,'timeout':self.timeout,'time':time}}
        #有了状态数据，就可以生成消息信息
        self.message['stat_code'] = "code:{}，threshold:{} URL:{}".format(status_data[self.task_name]['code'],threshold['stat_code'],status_data[self.task_name]['url'])
        self.message['stat_timeout'] = "stat_timeout:{}，threshold: 0 URL:{}".format(status_data[self.task_name]['timeout'],status_data[self.task_name]['url'])
        self.message['stat_math_str'] = '匹配字段:{}, stat_math_str:{} threshold: 0 URL:{}'.format(threshold['math_str'],status_data[self.task_name]['stat_math_str'],status_data[self.task_name]['url'])
        self.message['stat_delay'] = '目前响应时间:{} 预设响应时间:{}  stat_delay:{}  threshold: 0  URL:{}'.format(status_data[self.task_name]['delay'],threshold['delay'][0],status_data[self.task_name]['stat_delay'],status_data[self.task_name]['url'])

        #根据任务分类，才不会出现io 冲突
        datafile = 'data/{}.pkl'.format(self.task_name) #文件名字
        # 一开始设计状态都是好的，生成一个现在的状态和之前的状态，两个对比，发出故障警告或者恢复警告
        # 第一次运行的时候没有文件，那么先生成文件并存入数据



        if not os.path.exists(datafile):
            self.first_run_task(status_data,threshold,time,datafile)

        else:
            f = open(datafile,'rb')
            temp_dict = pickle.load(f)
            f.close()
            #保留时间数目
            histroy_day = (datetime.datetime.now() + datetime.timedelta(days=-config.history_datat_day)).strftime("%Y-%m-%d")
            #插入的key是当天时间
            key = (str(time.split()[0]))
            if  key in  temp_dict:
                #取出当天数据
                today_list = temp_dict[time.split()[0]]
                #print(today_list)

                #如果响应时间超时,我们设置连续超时多少次才告警
                if status_data[self.task_name]['stat_delay'] == 1:
                    #检查次数
                   num = threshold['delay'][1]
                   #检查
                   if len(today_list) + 1  >=  num:
                        #切割出最后的几次检查的次数的list
                        temp_list = today_list[-(num-1):]
                        #初始超时次数为0，如果循环后发现都是超时的那么告警，设置delay_warm =1
                        c =0
                        for his_data in temp_list:
                          if  his_data[self.task_name]['stat_delay'] == 1:
                              c +=1
                        if c == num - 1:
                            print('{} 检查{}次，超过设定时间最后一次{}毫秒'.format(self.task_name,num,status_data[self.task_name]['delay']))
                            self.now_alarm['delay_warm'] = 1

                   else:
                       #如果今天检查的次数不够设置告警，则取出昨天的来计算
                       yes_time = (datetime.datetime.now() + datetime.timedelta(days=-1)).strftime("%Y-%m-%d")
                       neednum = num - len(today_list) - 1
                       if  yes_time in  temp_dict and len(temp_dict[yes_time]) >= neednum:
                           temp_list = temp_dict[yes_time][-(neednum):]
                           temp_list.extend(today_list)
                           c = 0
                           for his_data in temp_list:
                               if his_data[self.task_name]['stat_delay'] != 1:
                                       break
                               else:
                                    c += 1
                           if c == num -1:
                               print('{} 检查{}次，超过设定时间最后一次{}毫秒'.format(self.task_name, num,status_data[self.task_name]['delay']))
                               self.now_alarm['delay_warm'] = 1


                #temp_dict 之前保存的所有数据
                temp_dict[key].append(status_data)
                #print(temp_dict)

            #key不在现有的字典
            else:
                yes_time = (datetime.datetime.now() + datetime.timedelta(days=-1)).strftime("%Y-%m-%d")
                if status_data[self.task_name]['stat_delay'] == 1:
                    num = threshold['delay'][1]
                    if yes_time in temp_dict and len(temp_dict[yes_time]) >= num - 1:
                        c = 0
                        temp_list = temp_dict[yes_time][-(num -1):]
                        for his_data in temp_list:
                            if his_data[self.task_name]['stat_delay'] != 1:
                                 break
                            else:
                                c += 1
                        if c == num - 1:
                            print('{} 检查{}次，超过设定时间最后一次{}毫秒'.format(self.task_name, num, status_data[self.task_name]['delay']))
                            self.now_alarm['delay_warm'] = 1
                #设置今天的第一个字典为空
                temp_dict[key] = []
                temp_dict[key].append(status_data)


            if status_data[self.task_name]['stat_code'] ==1:
                print("{} stat_code is wrong 不是第一次运行   {}".format(self.task_name,code))
                self.now_alarm['code_warm'] = 1


            if status_data[self.task_name]['timeout'] == 1:
                print('{} is timeout'.format(self.task_name))
                self.now_alarm['timeout_warm'] = 1

            if status_data[self.task_name]['stat_math_str'] == 1:
                print('{} 不存在 {}这个字段'.format(self.task_name,threshold['math_str']))
                self.now_alarm['math_warm'] = 1


            self.send_warm(alarm=temp_dict['alarm'],threshold=threshold)
            temp_dict['alarm'] = self.now_alarm
            if histroy_day in temp_dict:
                #根据配置文件删除历史数据保留天数
                del temp_dict[histroy_day]
            print('第二次写入')
            #print(temp_dict)
            with open(datafile, 'wb') as f:
                pickle.dump(temp_dict, f)







