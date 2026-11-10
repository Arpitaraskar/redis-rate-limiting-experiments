local key = KEYS[1]

local limit = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])

local count = redis.call("INCR", key)

if count == 1 then
    redis.call("EXPIRE", key, expiry)
end

if count <= limit then
    return {count, 1}
else
    return {count, 0}
end