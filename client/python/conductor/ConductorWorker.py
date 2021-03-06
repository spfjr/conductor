#
#  Copyright 2017 Netflix, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from __future__ import print_function, absolute_import
import sys
import time
from conductor.conductor import WFClientMgr
from threading import Thread
import socket

hostname = socket.gethostname()


class ConductorWorker:
    def __init__(self, server_url, thread_count, polling_interval, worker_id=None):
        wfcMgr = WFClientMgr(server_url)
        self.workflowClient = wfcMgr.workflowClient
        self.taskClient = wfcMgr.taskClient
        self.thread_count = thread_count
        self.polling_interval = polling_interval
        self.worker_id = worker_id or hostname

    def execute(self, task, exec_function):
        try:
            resp = exec_function(task)
            if resp is None:
                raise Exception('Task execution function MUST return a response as a dict with status and output fields')
            task['status'] = resp['status']
            task['outputData'] = resp['output']
            task['logs'] = resp['logs']
            self.taskClient.updateTask(task)
        except Exception as err:
            print('Error executing task: ' + str(err))
            task['status'] = 'FAILED'
            self.taskClient.updateTask(task)

    def poll_and_execute(self, taskType, exec_function, domain=None):
        while True:
            time.sleep(float(self.polling_interval))
            polled = self.taskClient.pollForTask(taskType, self.worker_id, domain)
            if polled is not None:
                self.taskClient.ackTask(polled['taskId'], self.worker_id)
                self.execute(polled, exec_function)

    def start(self, taskType, exec_function, wait, domain=None):
        print('Polling for task %s at a %f ms interval with %d threads for task execution, with worker id as %s' % (taskType, self.polling_interval * 1000, self.thread_count, self.worker_id))
        for x in range(0, int(self.thread_count)):
            thread = Thread(target=self.poll_and_execute, args=(taskType, exec_function, domain,))
            thread.daemon = True
            thread.start()
        if wait:
            while 1:
                time.sleep(1)


def exc(taskType, inputData, startTime, retryCount, status, callbackAfterSeconds, pollCount):
    print('Executing the function')
    return {'status': 'COMPLETED', 'output': {}}


def main():
    cc = ConductorWorker('http://localhost:8080/api', 5, 0.1)
    cc.start(sys.argv[1], exc, False)
    cc.start(sys.argv[2], exc, True)


if __name__ == '__main__':
    main()
