# teleop 到 execution_manager 的最小控制权消息

# 控制动作
# claim: 显式申请 teleop 控制权
# keepalive: 续租当前 teleop 控制权
# release: 主动释放 teleop 控制权
string action

# 请求方标识
# WebSocket 链路默认使用连接级 session id
# 为空时表示匿名请求方，用于兼容过渡期旧入口
string requester_id

# 当前已确认的 teleop lease 标识
# claim 时可为空；keepalive / release 应优先携带最近一次确认的 lease
# 为空时允许执行层按 requester_id 走过渡兼容
string lease_id

# 时间戳
builtin_interfaces/Time stamp
