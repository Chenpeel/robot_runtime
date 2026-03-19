# 控制层到 execution_manager 的最小执行请求消息
# 当前仍保留 servo 风格字段作为过渡接口，避免一次性重写上层节点

# 执行器类型
string servo_type  # "bus" 或 "pca"

# 执行器 ID
uint16 servo_id

# 目标位置
uint16 position

# 执行速度
uint16 speed

# 时间戳
builtin_interfaces/Time stamp
