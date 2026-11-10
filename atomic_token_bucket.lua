local key = KEYS[1]

local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local redis_time = redis.call("TIME")

local now = tonumber(redis_time[1]) +
            tonumber(redis_time[2]) / 1000000

-- Read current bucket state
local bucket = redis.call("HMGET", key, "tokens", "last_refill")

local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- Initialize bucket if it does not exist
if not tokens then
    tokens = capacity
    last_refill = now
end

-- Calculate refill
local elapsed = now - last_refill
local refilled_tokens = elapsed * refill_rate

local new_tokens = math.min(
    capacity,
    tokens + refilled_tokens
)

-- Check and consume token
local allowed = 0

if new_tokens >= 1 then
    new_tokens = new_tokens - 1
    allowed = 1
end

-- Save updated state
redis.call(
    "HSET",
    key,
    "tokens", new_tokens,
    "last_refill", now
)

return {allowed, new_tokens}