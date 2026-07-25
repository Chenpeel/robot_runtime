# 外部任务服务可消费的结构化上下文事件
builtin_interfaces/Time stamp

# 上下文来源：speech 或 perception
string source

# 来源域内的稳定事件标识
string event_id

# 可为空的会话标识；存在时用于跨模块关联
string session_id

# ready / rejected / failed 等稳定状态
string status
string reason
bool recoverable

# 面向外部任务服务的简短摘要，不承载内部协议原文
string summary

# 感知对象标签或语音意图标签；保持结构化数组语义
string[] labels
