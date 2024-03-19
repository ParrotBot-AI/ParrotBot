from dvadmin.system.streaming.revents import Producer
import redis

ep = Producer('broker')


class AdminStream:
    @ep.event("account_register")
    def core_register(self, **kwargs):
        # ep.send_event("account_register", {"core": str(True), "test": str(True)})
        return True, "broker account_register"

    @ep.event("pause_sheet")
    def pause_sheet(self, **kwargs):
        # ep.send_event("account_register", {"core": str(True), "test": str(True)})
        return True, "broker pause_sheet"

    @ep.event("grade_single_prob")
    def grade_single_prob(self, **kwargs):
        return True, "broker grade_single_prob"
