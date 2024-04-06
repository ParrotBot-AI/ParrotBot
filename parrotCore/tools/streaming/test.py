import time

import aioredis
from configs.redis_config import REDIS_SETTINGS

data_entries = [
    {"action": "grade_single_prob", "sheet_id": "1741", "question_id": "1517"},
    {"action": "grade_single_prob", "sheet_id": "1781", "question_id": "1537"},
    {"action": "grade_single_prob", "sheet_id": "1783", "question_id": "1540"},
    {"action": "grade_single_prob", "sheet_id": "1789", "question_id": "1542"},
    {"action": "grade_single_prob", "sheet_id": "1791", "question_id": "1543"},
    {"action": "grade_single_prob", "sheet_id": "1792", "question_id": "1544"},
    {"action": "grade_single_prob", "sheet_id": "1795", "question_id": "1544"},
    {"action": "grade_single_prob", "sheet_id": "1797", "question_id": "1545"},
    {"action": "grade_single_prob", "sheet_id": "1803", "question_id": "1622"},
    {"action": "grade_single_prob", "sheet_id": "1805", "question_id": "1622"},
] * 10

async def insert_to_stream():
    DEFAULT_SETTING = REDIS_SETTINGS['broker']
    redis_url = f"redis://:{DEFAULT_SETTING['password']}@{DEFAULT_SETTING['host']}:{DEFAULT_SETTING['port']}/{DEFAULT_SETTING['db']}"
    redis = await aioredis.create_redis_pool(redis_url)
    import random
    for entry in data_entries:
        # Using '*' as the ID to let Redis generate a unique ID for each entry
        stream_id = await redis.xadd('broker', entry)
        print(f"Inserted entry with Stream ID: {stream_id}, sheet_id: {entry['sheet_id']}, question_id: {entry['question_id']}")
        await asyncio.sleep(random.randint(0, 10))

    redis.close()
    await redis.wait_closed()


import asyncio
asyncio.run(insert_to_stream())