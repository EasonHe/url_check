from flask import Flask,request
from view.mail_server import geturl
from  view.make_check_instan import load_config


app = Flask(__name__)
#global lt
lt = load_config()
lt.loading_task()

@app.route('/sender/mail',methods=['POST'])
def  sender_mail():
   return geturl.sender()


@app.route('/job/opt',methods=['POST'])
def task_opt():
    if request.method == 'POST':
        data=eval(request.get_data())
        if 'list_jobs'in data and data['list_jobs'] == 1  :
            job_list = lt.get_jobs()#  这个一个list对象

            return '{}'.format(job_list) #'{}'.format(job_list)

        if  'remove_job' in data:
             try:
                lt.remove_job(task_name=data['remove_job'])
             except Exception as e:
                 print(e)
                 return '{}'.format(e)
        if  'stop_job' in data:
            try:
                lt.stop_job(task_name=data['stop_job'])

            except Exception as e:
                return '{}'.format(e)
        if  'resume_job' in data:
            try:
                lt.resume_job(task_name=data['resume_job'])

            except Exception as e:
                return '{}'.format(e)
        if 'shut_sched' in data and data['shut_sched'] == 1:
            try:
                lt.shut_sched()

            except Exception as e:
                return '{}'.format(e)

        if 'add_job'  in data:
            print(type(data))
            task_info = data['add_job']
            print(task_info)
            return "{}".format(lt.add_job(task_info=data['add_job']))

        if 'start_sched' in data and['start_sched'] == 1:
            lt.start_sched()

        return 'ok'
    return '{} False'.format(data)

if __name__ == '__main__':

    app.run(host="127.0.0.1",port=4000)
