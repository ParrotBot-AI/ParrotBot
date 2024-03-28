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
        return True, "答题卡已暂停。"

    @ep.event("grade_single_prob")
    def grade_single_prob(self, **kwargs):
        return True, "单题打分开始。"

    @ep.event("save_study_time")
    def save_study_time(self, **kwargs):
        return True, "学习时间已保存。"
