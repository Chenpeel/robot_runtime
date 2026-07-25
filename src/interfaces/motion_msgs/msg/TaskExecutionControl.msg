# execution_manager 的正式任务执行租约控制
# 这不是外部任务 API；外部请求后续必须由 task_service_bridge 转换后进入

# 支持 start / keepalive / finish / cancel
# cancel 只撤销后续命令准入；驱动级在途停止需由未来正式任务动作接口承接
string action

# 任务追踪身份
string task_id
string trace_id
string session_id

# start 成功后由 execution_manager 生成
# 活跃 task 的重复 start / keepalive / finish / cancel 必须原样携带
string lease_id

# 调用方产生该控制请求的时间，仅用于观测追踪
# 准入超时使用 execution_manager 的单调时钟；终态身份 tombstone 负责阻断近期 start 重放
builtin_interfaces/Time stamp
