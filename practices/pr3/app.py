import json
import os
import threading
import time
from collections import deque

import psycopg2
import psycopg2.pool
import redis


postgresConfig = {
    "host": os.environ.get("PG_HOST", "postgres"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "user": os.environ.get("PG_USER", "app"),
    "password": os.environ.get("PG_PASSWORD", "app"),
    "dbname": os.environ.get("PG_DB", "app"),
}

redisHost = os.environ.get("REDIS_HOST", "redis")
redisPort = int(os.environ.get("REDIS_PORT", "6379"))

cacheTtl = 300


def connectPostgres(retries=60, delay=0.5):
    lastError = None
    for _ in range(retries):
        try:
            return psycopg2.pool.ThreadedConnectionPool(2, 16, **postgresConfig)
        except Exception as e:
            lastError = e
            time.sleep(delay)
    raise lastError


def connectRedis(retries=60, delay=0.5):
    lastError = None
    for _ in range(retries):
        try:
            r = redis.Redis(host=redisHost, port=redisPort, decode_responses=True)
            r.ping()
            return r
        except Exception as e:
            lastError = e
            time.sleep(delay)
    raise lastError


def profileKey(profileId):
    return f"profile:{profileId}"


class Metrics:
    def __init__(self):
        self.db_reads = 0
        self.db_writes = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.lock = threading.Lock()

    def increment(self, attr, n=1):
        with self.lock:
            setattr(self, attr, getattr(self, attr) + n)

    def snapshot(self):
        with self.lock:
            return {
                "db_reads": self.db_reads,
                "db_writes": self.db_writes,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
            }


class Base:
    def __init__(self):
        self.pool = connectPostgres()
        self.redis = connectRedis()
        self.metrics = Metrics()

    def dbGet(self, profileId):
        self.metrics.increment("db_reads")
        connection = self.pool.getconn()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, name, age, bio FROM profiles WHERE id=%s", (profileId,))
                row = cursor.fetchone()
                if not row:
                    return None
                return {"id": row[0], "name": row[1], "age": row[2], "bio": row[3]}
        finally:
            self.pool.putconn(connection)

    def dbUpsert(self, profileId, value):
        self.metrics.increment("db_writes")
        connection = self.pool.getconn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO profiles (id, name, age, bio, updated_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET name=EXCLUDED.name, age=EXCLUDED.age, bio=EXCLUDED.bio, updated_at=NOW()
                    """,
                    (profileId, value["name"], value["age"], value["bio"]),
                )
            connection.commit()
        finally:
            self.pool.putconn(connection)

    def flushCache(self):
        self.redis.flushdb()

    def shutdown(self):
        pass


class CacheAside(Base):
    name = "cache_aside"

    def get(self, profileId):
        cached = self.redis.get(profileKey(profileId))
        if cached is not None:
            self.metrics.increment("cache_hits")
            return json.loads(cached)
        self.metrics.increment("cache_misses")
        value = self.dbGet(profileId)
        if value is not None:
            self.redis.setex(profileKey(profileId), cacheTtl, json.dumps(value))
        return value

    def set(self, profileId, value):
        self.dbUpsert(profileId, value)
        self.redis.delete(profileKey(profileId))


class WriteThrough(Base):
    name = "write_through"

    def get(self, profileId):
        cached = self.redis.get(profileKey(profileId))
        if cached is not None:
            self.metrics.increment("cache_hits")
            return json.loads(cached)
        self.metrics.increment("cache_misses")
        value = self.dbGet(profileId)
        if value is not None:
            self.redis.setex(profileKey(profileId), cacheTtl, json.dumps(value))
        return value

    def set(self, profileId, value):
        self.dbUpsert(profileId, value)
        self.redis.setex(profileKey(profileId), cacheTtl, json.dumps({"id": profileId, **value}))


class WriteBack(Base):
    name = "write_back"

    def __init__(self, flushInterval=0.5, batchSize=200):
        super().__init__()
        self.flushInterval = flushInterval
        self.batchSize = batchSize
        self.dirtyQueue = deque()
        self.queueLock = threading.Lock()
        self.stopEvent = threading.Event()
        self.flushThread = threading.Thread(target=self.flusher, daemon=True)
        self.flushThread.start()

    def get(self, profileId):
        cached = self.redis.get(profileKey(profileId))
        if cached is not None:
            self.metrics.increment("cache_hits")
            return json.loads(cached)
        self.metrics.increment("cache_misses")
        value = self.dbGet(profileId)
        if value is not None:
            self.redis.setex(profileKey(profileId), cacheTtl, json.dumps(value))
        return value

    def set(self, profileId, value):
        record = {"id": profileId, **value}
        self.redis.setex(profileKey(profileId), cacheTtl, json.dumps(record))
        with self.queueLock:
            self.dirtyQueue.append((profileId, value))

    def dirtyCount(self):
        with self.queueLock:
            return len(self.dirtyQueue)

    def drainBatch(self):
        with self.queueLock:
            batch = []
            while self.dirtyQueue and len(batch) < self.batchSize:
                batch.append(self.dirtyQueue.popleft())
        if not batch:
            return 0
        coalesced = {}
        for profileId, value in batch:
            coalesced[profileId] = value
        connection = self.pool.getconn()
        try:
            with connection.cursor() as cursor:
                upsertRows = [(pid, v["name"], v["age"], v["bio"]) for pid, v in sorted(coalesced.items())]
                cursor.executemany(
                    """
                    INSERT INTO profiles (id, name, age, bio, updated_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET name=EXCLUDED.name, age=EXCLUDED.age, bio=EXCLUDED.bio, updated_at=NOW()
                    """,
                    upsertRows,
                )
            connection.commit()
        finally:
            self.pool.putconn(connection)
        self.metrics.increment("db_writes", len(coalesced))
        return len(batch)

    def flusher(self):
        while not self.stopEvent.is_set():
            try:
                self.drainBatch()
            except Exception:
                pass
            self.stopEvent.wait(self.flushInterval)

    def flushSync(self):
        self.stopEvent.set()
        if self.flushThread.is_alive():
            self.flushThread.join(timeout=10)
        while True:
            n = self.drainBatch()
            if n == 0:
                return

    def shutdown(self):
        self.flushSync()


strategies = {
    "cache_aside": CacheAside,
    "write_through": WriteThrough,
    "write_back": WriteBack,
}
