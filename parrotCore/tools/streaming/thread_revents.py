import redis
from datetime import datetime
import functools
from utils.redis_tools import RedisWrapper
from typing import Dict, Any
import threading
from concurrent.futures import ThreadPoolExecutor
from utils.logger_tools import get_general_logger
from utils import abspath
from configs.environment import MAX_STREAM_WORKER

logger = get_general_logger('stream_log', path=abspath('logs', 'core_stream'))

class Worker:
    def __init__(self):
        self._events = {}
        self._executor = ThreadPoolExecutor(max_workers=MAX_STREAM_WORKER)

    def consume_past_messages(self, listen_name="broker"):
        threading.Thread(target=self._consume_past_messages_thread, args=(listen_name,)).start()

    def _consume_past_messages_thread(self, listen_name):
        self._r = RedisWrapper(listen_name).redis_client
        streams = " ".join(self._events.keys())
        messages = self._r.xread({streams: '0-0'}, block=None)
        for stream, msgs in messages:
            for msg_id, msg in msgs:
                event = [[stream, [(msg_id, msg)]]]
                if self._dispatch(event):
                    self._r.xdel(stream, msg_id)

    def on(self, stream, action, **options):
        def decorator(func):
            self.register_event(stream, action, func, **options)
            return func
        return decorator

    def register_event(self, stream, action, func, **options):
        if stream in self._events.keys():
            self._events[stream][action] = func
        else:
            self._events[stream] = {action: func}

    def listen(self, listen_name="broker"):
        self._r = RedisWrapper(listen_name).redis_client
        streams = {stream: '$' for stream in self._events.keys()}  # Prepare streams for xread

        while True:
            events = self._r.xread(streams, block=5000)  # Consider adjusting the block time as needed
            for stream, msgs in events:
                for msg_id, msg in msgs:
                    # Submit each message to the executor for processing
                    self._executor.submit(self._process_message, stream, msg_id, msg, listen_name)
            logger.info("继续监听....")

    def _process_message(self, stream, msg_id, msg, listen_name):
        self._r = RedisWrapper(listen_name).redis_client
        result = self._dispatch([[stream, [(msg_id, msg)]]])
        if result:
            self._r.xdel(stream, msg_id)

    def _dispatch(self, event):
        """
        Call a function given an event
        If the event has been registered, the registered function will be called with the passed params.
        """
        e = Event(event=event)
        if e.action in self._events[e.stream].keys():
            func = self._events[e.stream][e.action]
            logger.info(f"{datetime.now()} - Stream: {e.stream} - {e.event_id}: {e.action} {e.data}")
            return func(**e.data)
        else:
            return False


class Event():
    """
    Abstraction for an event
    """

    def __init__(self, stream="", action="", data={}, event=None):
        self.stream = stream
        self.action = action
        self.data = data
        self.event_id = None
        if event:
            self.parse_event(event)

    def parse_event(self, event):
        # event = [[b'bar', [(b'1594764770578-0', {b'action': b'update', b'test': b'True'})]]]
        self.stream = event[0][0].decode('utf-8')
        self.event_id = event[0][1][0][0].decode('utf-8')
        self.data = event[0][1][0][1]
        self.action = self.data.pop(b'action').decode('utf-8')
        params = {}
        for k, v in self.data.items():
            params[k.decode('utf-8')] = v.decode('utf-8')
        self.data = params

    def publish(self, r):
        body = {
            "action": self.action
        }
        for k, v in self.data.items():
            body[k] = v
        r.xadd(self.stream, body)


class Producer:
    """
    Abstraction for a service (module) that publishes events about itself
    Manages stream information and can publish events
    """

    # stream = None
    # _r = redis.Redis(host="localhost", port=6379, db=0)

    def __init__(self, stream_name='core_broker'):
        self.stream = stream_name
        self._r = RedisWrapper('core_broker').redis_client

    def send_event(self, action, data):
        e = Event(stream=self.stream, action=action, data=data)
        e.publish(self._r)

    def event(self, action, data: Dict[str, Any] = {}):
        def decorator(func):
            @functools.wraps(func)
            def wrapped(*args, **kwargs):
                result = func(*args, **kwargs)
                arg_keys = func.__code__.co_varnames[1:-1]
                for i in range(1, len(args)):
                    kwargs[arg_keys[i - 1]] = args[i]
                self.send_event(action, kwargs)
                return result

            return wrapped

        return decorator
