# 语音入口只发布结构化意图，不承载原始 JSON 或驱动级字段。
builtin_interfaces/Time stamp
string intent_id
string task_id
string trace_id
string session_id
string task_type
string target_group
float64 roll
float64 pitch
float64 yaw
uint16 duration_ms
uint16 position_tolerance
float32 execution_timeout_sec
float32 confidence
# status 稳定取值：accepted / executing / succeeded / cancelled /
# timed_out / failed / rejected。
string status
string reason
bool recoverable
