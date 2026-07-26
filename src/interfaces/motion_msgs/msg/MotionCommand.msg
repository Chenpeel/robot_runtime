# 控制层到 execution_manager 的最小执行请求消息
# 当前仍保留 servo 风格字段作为过渡接口，避免一次性重写上层节点

# 执行器类型
string servo_type  # "bus" 或 "pca"

# 执行器 ID
uint16 servo_id

# 目标位置
uint16 position

# DEPRECATED：仅在公共消息迁移窗口内保留，仓库内置 producer/consumer
# 已禁止读写该字段。新调用方必须使用 duration_ms。
# 后续删除属于破坏性 ROS 接口变更，必须统一重建并同步重启全部依赖节点。
uint16 speed

# 目标值编码
# bus_pulse_us: 总线舵机脉宽微秒值
# pca_tick: PCA 舵机 tick 值
string value_encoding

# 显式执行时长（毫秒）
# execution_manager 仅从该字段读取内部执行时长；0 表示未显式指定
uint16 duration_ms

# 请求方标识
# teleop 链路透传连接 requester；正式 task 命令使用当前 task_id
# 普通 motion/demo 可为空，但活跃 task/teleop 租约内必须匹配当前身份
string requester_id

# 当前已确认的 execution lease 标识
# teleop 或 task 链路必须透传各自 lease；普通 motion/demo 可为空
string lease_id

# 时间戳
builtin_interfaces/Time stamp
