from dvadmin.system.streaming.revents import Producer
import redis

ep = Producer('broker')


class AdminStream:
    @ep.event("account_register")
    def core_register(self, **kwargs):
        # ep.send_event("account_register", {"core": str(True), "test": str(True)})
        return True, "broker account_register"
