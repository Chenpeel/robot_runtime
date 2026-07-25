# execution_manager 对外发布的执行层状态消息

# 当前模式
string mode

# 当前持有控制权的来源，空字符串表示无
string active_source

# 当前 teleop 控制权持有者，空字符串表示无
string teleop_holder_id

# 当前活跃的 teleop lease 标识，空字符串表示无
string teleop_lease_id

# 急停状态
bool estop_active

# 各来源是否仍处于活跃窗口
bool teleop_active
bool motion_active

# 各来源超时配置
float32 teleop_timeout_sec
float32 motion_timeout_sec

# teleop 控制权反馈
float32 teleop_control_remaining_sec
string last_teleop_control_action
bool last_teleop_control_accepted
string last_teleop_control_reason
uint32 teleop_control_accepted_count
uint32 teleop_control_rejected_count

# 计数器
uint32 teleop_accepted_count
uint32 motion_accepted_count
uint32 teleop_rejected_count
uint32 motion_rejected_count

# 最近一次拒绝原因
string last_rejection_reason

# 时间戳
builtin_interfaces/Time stamp
