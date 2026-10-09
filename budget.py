import redis.asyncio as redis

class BudgetEnforcer:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        # Atomic check-and-decrement to prevent concurrent race conditions
        self.lua_script = """
        local current_spend = tonumber(redis.call('GET', KEYS[1]) or "0")
        local request_cost = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        
        if current_spend + request_cost > limit then
            return -1 -- Budget exceeded
        else
            redis.call('INCRBYFLOAT', KEYS[1], request_cost)
            redis.call('EXPIRE', KEYS[1], 86400) -- Reset daily
            return current_spend + request_cost
        end
        """
        self.script_sha = None

    async def authorize_spend(self, organization_id: str, estimated_cost: float, daily_limit: float) -> bool:
        if not self.script_sha:
            self.script_sha = await self.redis.script_load(self.lua_script)
            
        key = f"budget:org:{organization_id}:daily"
        result = await self.redis.evalsha(self.script_sha, 1, key, estimated_cost, daily_limit)
        
        if result == -1:
            return False
        return True
