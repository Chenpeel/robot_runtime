# 控制层到 execution_manager 的最小执行请求消息
# 当前仍保留 servo 风格字段作为过渡接口，避免一次性重写上层节点

# 执行器类型
string servo_type  # "bus" 或 "pca"

# 执行器 ID
uint16 servo_id

# 目标位置
uint16 position

# 兼容字段：执行时长（毫秒）
uint16 speed

# 目标值编码
# bus_pulse_us: 总线舵机脉宽微秒值
# pca_tick: PCA 舵机 tick 值
string value_encoding

# 显式执行时长（毫秒）
# 为 0 时，consumer 应回退读取 speed
uint16 duration_ms

# 请求方标识
# teleop 链路可透传当前连接 requester，用于执行层做更严格的控制权校验
# 为空时表示未提供身份，consumer 可按过渡兼容语义处理
string requester_id

# 当前已确认的 teleop lease 标识
# teleop 链路可透传当前 lease，用于执行层做更严格的控制权校验
# 为空时表示未提供 lease，consumer 可按过渡兼容语义处理
string lease_id

# 时间戳
builtin_interfaces/Time stamp
