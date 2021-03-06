# Licensed to the StackStorm, Inc ('StackStorm') under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import eventlet
import logging
import Queue

from .triggerdispatcher import TriggerDispatcher


class ContainerService(object):
    _base_logger_name = 'st2reactor.sensorcontainer.sensors.'

    def __init__(self, dispatcher=None, dispatch_pool_size=50, monitor_thread_empty_q_sleep_time=5,
                 monitor_thread_no_workers_sleep_time=1):
        if dispatcher is None:
            dispatcher = TriggerDispatcher()
        self._dispatcher = dispatcher
        self._pool_limit = dispatch_pool_size
        self._dispatcher_pool = eventlet.GreenPool(dispatch_pool_size)
        self._dispatch_monitor_thread = eventlet.greenthread.spawn(self._flush_triggers)
        self._monitor_thread_empty_q_sleep_time = monitor_thread_empty_q_sleep_time
        self._monitor_thread_no_workers_sleep_time = monitor_thread_no_workers_sleep_time
        self._triggers_buffer = Queue.Queue()

    def get_dispatcher(self):
        return self._dispatcher

    def dispatch(self, trigger, payload):
        self._triggers_buffer.put((trigger, payload), block=True, timeout=1)
        self._flush_triggers_now()

    def get_logger(self, name):
        logger = logging.getLogger(self._base_logger_name + name)
        logger.propagate = True
        return logger

    def _dispatch(self, trigger_tuple):
        self._dispatcher.dispatch(*trigger_tuple)

    def _flush_triggers_now(self):
        if self._dispatcher_pool.free() <= 0:
            return
        while not self._triggers_buffer.empty() and self._dispatcher_pool.free() > 0:
            trigger_tuple = self._triggers_buffer.get_nowait()
            self._dispatcher_pool.spawn(self._dispatch, trigger_tuple)

    def _flush_triggers(self):
        while True:
            while self._triggers_buffer.empty():
                eventlet.greenthread.sleep(self._monitor_thread_empty_q_sleep_time)
            while self._dispatcher_pool.free() <= 0:
                eventlet.greenthread.sleep(self._monitor_thread_no_workers_sleep_time)
            self._flush_triggers_now()

    def shutdown(self):
        self._dispatch_monitor_thread.kill()
