#!/usr/bin/env python3
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from flask import Flask, render_template, make_response
import time, datetime, os, pickle
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


# Edit this function to choose what appends when new modules are added
def on_new_modules(new_modules):
    try:
        headers = {'Access-Token': os.getenv("ACCESS_TOKEN"),
                   'Content-Type': 'application/json'}
        text = 'New modules have been added\n\n'
        for module in new_modules:
            text += module['title'] + '\n' + module['url'] + '\n'
        requests.post('https://api.pushbullet.com/v2/pushes', json={'body': text, 'type': 'note'},
                      headers=headers)
    except:
        print('new modules action failed')


def init():
    if not os.path.exists('save/modules.save'):
        print('first start may take about 15s please wait...')
        refresh_modules(old_dates)
    threading.Timer(10, refresh_job).start()


def refresh_job():
    thread = threading.Timer(60 * 10, refresh_job)
    thread.setDaemon(True)
    thread.start()
    print("'.'")
    refresh_modules()


def to_time(string):
    try:
        return time.mktime(datetime.datetime.strptime(string,
                                                      "%Y-%m-%d").timetuple())
    except:
        try:
            return time.mktime(datetime.datetime.strptime(string,
                                                          "%Y-%m-%d %H:%M:%S").timetuple())
        except:
            pass


def merge_activities(item, module_data, url):
    item['activites'] = list(map(
        lambda activity: {'chart_array': [activity['title'], activity['begin'], activity['end']],
                          'url': url + '/' + activity['codeacti'] + '/project'}, module_data['activites']))


def retrieve_module_data(item):
    item['url'] = os.getenv("AUTOLOGIN") + '/module/' + str(item['scolaryear']) + '/' + item['code'] + '/' + item[
        'codeinstance']
    res = requests.get(item['url'] + '/?format=json')
    module_data = res.json()
    merge_activities(item, module_data, item['url'])
    item['project_start'] = module_data['activites'][0]['start'] if len(module_data['activites']) else item['begin']
    item['registered'] = True if module_data['student_registered'] else False
    return 'done ' + item['title']


def find_old_module(module, saved_modules):
    for i, saved in enumerate(saved_modules):
        if saved['id'] == module['id']:
            return i
    return -1


def finding_additions(modules):
    saved_modules = load_modules()
    new_modules = []
    for module in modules:
        index = find_old_module(module, saved_modules)
        if index == -1:
            module['created'] = time.time()
            new_modules.append(module)
            threading.Thread(target=on_new_modules, args=[new_modules]).start()
        else:
            module['created'] = saved_modules[index]['created']


def old_dates(modules):
    for module in modules:
        module['created'] = 0


def refresh_modules(postprocess=finding_additions):
    print('Refreshing data...')
    res = requests.get(os.getenv(
        "AUTOLOGIN") + '/course/filter?format=json&preload=1&location%5B%5D=FR&location%5B%5D=FR%2FPAR&course%5B%5D=master%2Fclassic&scolaryear%5B%5D=2020')
    modules = res.json()['items']
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = map(lambda module: executor.submit(retrieve_module_data, item=module), modules)
        for future in as_completed(futures):
            future.result()
    print('done')
    modules.sort(key=lambda module: to_time(module['project_start']))
    data = map(lambda module: {'chart_array': [module['title'], module['project_start'], module['end']],
                               'activities': module['activites'],
                               'url': module['url'],
                               'title': module['title'],
                               'id': module['id'],
                               'registered': module['registered']}, modules)
    data = list(data)
    postprocess(data)
    with open('save/modules.save', 'wb') as module_save:
        pickle.dump(data, module_save)
    print('data saved')
    return data


def load_modules():
    with open('save/modules.save', 'rb') as module_save:
        return pickle.load(module_save)


@app.route('/modules')
def modules_route():
    response = make_response(json.dumps(load_modules()))
    response.headers['Content-Type'] = 'application/json'
    return response


@app.route('/')
def timeline():
    threading.Thread(target=refresh_modules).start()
    return render_template('index.html')


init()

if __name__ == "__main__":
    app.run(host='0.0.0.0')
