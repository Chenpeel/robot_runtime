# execution_manager 向上层发布的执行器状态反馈
# 驱动层 ServoState 必须先经过 execution_manager 适配，不能直接进入上层桥接

# 执行器类型，例如 "bus" 或 "pca"
string actuator_type

# 执行器 ID
uint16 actuator_id

# 未解释的原始位置值；具体编码由 value_encoding 明确
uint16 position_raw

# 位置值编码，例如 bus_pulse_us 或 pca_tick
string value_encoding

# 驱动反馈；不支持时沿用驱动层的 -1 约定
int16 load
int16 temperature

# 结构化执行反馈状态
string status       # "ok" 或 "error"
string reason       # 稳定错误原因；正常时为空
bool recoverable    # 当前错误是否允许在状态恢复后重试

# 原始驱动错误码，0 表示正常
uint8 driver_error_code

# 原始驱动状态时间戳
builtin_interfaces/Time stamp
