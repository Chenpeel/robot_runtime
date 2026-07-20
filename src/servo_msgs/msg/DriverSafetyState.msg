# execution_manager 发布的驱动安全权威状态。
# 驱动只接受时间戳晚于本地 stop fence 的非 active 状态作为 release。
bool estop_active
string reason
builtin_interfaces/Time stamp
