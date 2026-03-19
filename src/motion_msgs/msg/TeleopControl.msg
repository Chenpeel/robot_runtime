# teleop 到 execution_manager 的最小控制权消息

# 控制动作
# claim: 显式申请 teleop 控制权
# keepalive: 续租当前 teleop 控制权
# release: 主动释放 teleop 控制权
string action

# 时间戳
builtin_interfaces/Time stamp
