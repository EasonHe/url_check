#from apscheduler.schedulers.blocking import BlockingScheduler
from  apscheduler.schedulers.background import BackgroundScheduler
import  configparser
import requests
from  requests import  exceptions
from  conf import config
import sys
import datetime
from  view.checke_control import cherker

class get_method():

    def __init__(self,task_name,url, headers=None,cookies=None,payload=None,timeout=10,threshold=None):
        """"初始化方法"""
        self.task_name =task_name
        self.url = url
        self.header = headers
        self.payload = payload
        self.timeout = timeout
        self.cookies = cookies
        self.threshold =threshold

    def get_instan(self):

        try:
            name = self.task_name
            data = {}
            now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r = requests.get(self.url,headers=self.header,cookies=self.cookies,data=self.payload,timeout=self.timeout)
            r.encoding = 'utf-8'
            retime = r.elapsed.microseconds / 1000
            statuscode = r.status_code
            data = {'url_name': self.task_name,'url': self.url , 'stat_code': statuscode, 'timeout': 0,'resp_time': retime,
                    'contents': r.text,'time':now_time,'threshold': self.threshold}
            print(data)
            ck = cherker()
            ck.make_data(data)
        #如果访问出现超时那么是没有响应时间，同时time = 1
        except  exceptions.ConnectTimeout:
            data = {'url_name': self.task_name,'url': self.url ,'threshold': self.threshold , 'timeout':1 ,'time':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            print(data)
            ck = cherker()
            ck.make_data(data)
        except exceptions.TooManyRedirects:
            print(TooManyRedirects)


class post_method():
    def __init__(self,task_name,url,headers=None,cookies=None,payload=None,timeout=None,threshold=None):
        self.url = url
        self.header = headers
        self.payload = payload
        self.timeout = timeout
        self.name = task_name
        self.cookies = cookies
        self.threshold = threshold
    def post_instan(self):
        print("{},{},{},'post method'".format(self.url,self.header, self.payload))
        name = self.name
        try:
            data = {}

            r = requests.post(self.url,headers=self.header, cookies=self.cookies,data=self.payload, timeout=self.timeout)
            r.encoding = 'utf-8'
            retime = r.elapsed.microseconds / 1000
            statuscode = r.status_code

            data = {'url_name': self.name,'url': self.url ,'stat_code': statuscode,'timeout':0 ,'resp_time': retime,
                    'contents': r.text ,'threshold': self.threshold,'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

            #print(data)
            ck =cherker()
            ck.make_data(data)
        except  exceptions.ConnectTimeout:
            data = {'url_name': self.name,'url': self.url ,'timeout':1 ,'threshold': self.threshold,'time':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

            print(data)
            ck = cherker()
            ck.make_data(data)

        except exceptions.TooManyRedirects:
            print(TooManyRedirects)

class load_config:
    def __init__(self):
        self.config =  configparser.ConfigParser()
        self.config.read(config.task_conf)
        self.sched = BackgroundScheduler()
    #如果提交的参数没有值或者缺少参数，会添加参数并设置默认值
    def config_set(self,name):
        url = self.config.get(name, 'url')
        if not self.config.has_option(name, 'threshold'):
            threshold ={}
            #正常会去校验状态码，如果这个字段不写默认值200
            threshold['stat_code'] = 200
        else:
            threshold = eval(self.config.get(name,'threshold'))
        timeout = int(self.config.get(name, 'timeout')) if self.config.has_option(name, 'timeout') else 10
        headers = (eval(self.config.get(name, 'headers'))) if self.config.has_option(name, 'headers') else  None
        cookies = (eval(self.config.get(name, 'cookies'))) if self.config.has_option(name, 'cookies') else  None
        payload = (eval(self.config.get(name, 'payload'))) if self.config.has_option(name, 'payload') else None
        interval = int(self.config.get(name, 'interval')) if self.config.has_option(name, 'interval')else  10


        #delay = self.config.get(name,'delay') if self.config.has_option(name,'delay')  else  200
        #math_str =self.config.get(name,'math_str') if self.config.has_option(name,'math_str') else None
        print('timeout',timeout)
        return {'Url':url,'Headers':headers,'Cookies':cookies,'Payload':payload,'Interval':interval,'Timeout':timeout,'threshold':threshold}

    def  add_task(self,task):
        if self.config.get(task, 'method') == 'post':
            print('task {} post method'.format(task))
            task_name = task
            dic_post = self.config_set(name=task_name)

            task = post_method(task_name=task_name,url=dic_post['Url'],headers=dic_post['Headers'],cookies=dic_post['Cookies'],payload=dic_post['Payload'],timeout=dic_post['Timeout'],threshold=dic_post['threshold'])
            self.sched.add_job(task.post_instan, 'interval',seconds=dic_post['Interval'],id=task_name,max_instances=10,replace_existing=True)

        elif self.config.get(task, 'method') == 'get':
            print('task {} get method'.format(task))
            task_name = task
            dict_conf=self.config_set(name=task_name)
            task = get_method(task_name,dict_conf['Url'],headers=dict_conf['Headers'],cookies=dict_conf['Cookies'],payload=dict_conf['Payload'],timeout=dict_conf['Timeout'],threshold=dict_conf['threshold'])
            self.sched.add_job(task.get_instan,'interval',seconds=dict_conf['Interval'],id=task_name,max_instances=10,replace_existing=True)

        else:
            print('{}........配置文件错误:请检查你的的请求方法，method = post ,method = get'.format(task))

    #启动加载配置，同时启动检查任务
    def loading_task(self):
        task_list = self.config.sections()
        for task in  task_list:
            self.add_task(task=task)
        self.sched.start()
        print('start')

    def get_jobs(self):
        job_list =[]
        for  instan  in self.sched.get_jobs():
            job_list.append(instan.id)
        return job_list
    def remove_job(self,task_name):
        self.sched.remove_job(task_name)

    def stop_job(self,task_name):

        self.sched.pause_job(job_id=task_name)
        return True
    def resume_job(self,task_name):
        self.sched.resume_job(job_id=task_name)
        return True
    def shut_sched(self):
        self.sched.shutdown()
        return True

    def add_job(self,task_info):
        job_list = self.get_jobs()
        print(job_list)
        task_name = task_info['section']
        if  task_name not in job_list:
            if not self.config.has_section(task_name):
                self.config.add_section(task_name)
            if 'url' in task_info:
                self.config.set(task_name,'url',task_info['url'])
            else:
                raise 'wrong must exist url'
            if 'method' in task_info:
                self.config.set(task_name,'method',task_info['method'])
            else:
                raise "wrong must exist method"

            if 'headers' in task_info:
                self.config.set(task_name,'headers',task_info['headers'])
            if  'cookies' in task_info:
                self.config.set(task_name,'cookies',task_info['cookies'])
            if  'payload' in task_info:
                self.config.set(task_name,'payload',task_info['payload'])
            if 'threshold' in task_info:
                self.config.set(task_name, 'threshold', str(task_info['threshold']))


            print(self.config.sections())
            self.add_task(task=task_name)
            self.config.write(open(config.task_conf,'w'))
            self.config.write(sys.stdout)
            return "add success"
        else:
            print(task_name,"is exits")

            return False




    def start_sched(self):
        self.sched.start()

