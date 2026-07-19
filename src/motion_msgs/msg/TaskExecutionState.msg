# execution_manager 发布的正式任务执行租约状态

bool active
# 最近一次成功准入的完整任务身份；终态会保留，下一次成功 start 时替换
string task_id
string trace_id
string session_id
# 仅 active=true 时非空，所有终态都会立即撤销
string lease_id

float32 lease_timeout_sec
float32 lease_remaining_sec

string last_action
# 最近一次控制请求的 task_id；timeout / estop 等系统终态使用被撤销的 task_id
string last_task_id
bool last_action_accepted
string status
string reason
bool recoverable

uint32 control_accepted_count
uint32 control_rejected_count

# 最近一次 task MotionCommand 的独立准入结果，不与控制租约事件混用
string last_command_requester_id
bool last_command_accepted
string last_command_reason
uint32 command_accepted_count
uint32 command_rejected_count

builtin_interfaces/Time stamp
