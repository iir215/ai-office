import redis
from rq import Queue

from app.core.config import settings

redis_conn = redis.from_url(settings.REDIS_URL)

task_queue = Queue("agent_tasks", connection=redis_conn)
