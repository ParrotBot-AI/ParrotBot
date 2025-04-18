import redis
from datetime import datetime
import functools
from utils.redis_tools import RedisWrapper
from typing import Dict, Any


class Worker:
    # streams = {
    #   "bar": {
    #       "update": Foo.foo_action
    #   },
    # }

    def __init__(self):
        self._events = {}

    def consume_past_messages(self, listen_name="broker"):
        self._r = RedisWrapper(listen_name).redis_client
        streams = " ".join(self._events.keys())
        # 消费掉之前的属于自己的message
        messages = self._r.xread({streams: '0-0'}, block=None)
        for stream, msgs in messages:
            for msg_id, msg in msgs:
                # Process the message
                event = [[stream, [(msg_id, msg)]]]
                if self._dispatch(event):
                    self._r.xdel(stream, msg_id)

    def on(self, stream, action, **options):
        """
        Wrapper to register a function to an event
        """
        def decorator(func):
            self.register_event(stream, action, func, **options)
            return func

        return decorator

    def register_event(self, stream, action, func, **options):
        """
        Map an event to a function
        """
        if stream in self._events.keys():
            self._events[stream][action] = func
        else:
            self._events[stream] = {action: func}

    def listen(self, listen_name="broker"):
        """
        Main event loop
        Establish redis connection from passed parameters
        Wait for events from the specified streams
        Dispatch to appropriate event handler
        """
        self._r = RedisWrapper(listen_name).redis_client
        streams = " ".join(self._events.keys())
        print(streams)
        while True:
            event = self._r.xread({streams: "$"}, None, 0)
            # Call function that is mapped to this event
            if self._dispatch(event):
                stream = event[0][0].decode('utf-8')
                msg_id = event[0][1][0][0].decode('utf-8')
                self._r.xdel(stream, msg_id)

    def _dispatch(self, event):
        """
        Call a function given an event
        If the event has been registered, the registered function will be called with the passed params.
        """
        e = Event(event=event)
        if e.action in self._events[e.stream].keys():
            func = self._events[e.stream][e.action]
            print(f"{datetime.now()} - Stream: {e.stream} - {e.event_id}: {e.action} {e.data}")
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
