# `MotionCommand.speed` 公共字段迁移说明

## 1. 当前状态

截至 2026-07-17，仓库内置运行链路已完成对
`motion_msgs/msg/MotionCommand.speed` 的逻辑脱钩：

- `execution_manager` 只从正值 `duration_ms` 构造内部执行时长。
- `websocket_bridge`、`parallel_3dof_controller` 和可选 BVH 扩展均只写
  `duration_ms`。
- `MotionCommand.speed` 仍保留在公共消息定义中，但已经标记为弃用；它只用
  于公共接口迁移窗口，不再承载仓库内运行时语义。
- `motion_msgs` 的源码合同测试禁止仓库内置 producer / consumer 重新读写该
  字段。

当前正式链路为：

```text
producer duration_ms
    → MotionCommand.duration_ms
    → execution_manager 内部 duration_ms
    → ServoCommand.speed
```

## 2. 不属于本次迁移的同名合同

以下字段位于不同协议层，不能随 `MotionCommand.speed` 删除：

- WebSocket payload 的 `speed` / `s` 与规范化 ack 的 `speed`
  - 属于外部协议兼容面，由 bridge 规范化为 `duration_ms`。
- BVH 请求的 `speed_ms`、动作资源的 `speed` 与播放器 timing
  - 属于动作播放请求和资源语义，最终由扩展写入 `duration_ms`。
- `servo_msgs/msg/ServoCommand.speed`
  - 属于驱动层执行时长合同，继续由 `execution_manager` 从内部
    `duration_ms` 映射得到。
- controller 的 `default_speed` 与求解器 `speed` 形参
  - 是包内仍待后续收敛的兼容词表，不是 ROS 公共消息字段。

## 3. 删除字段前的 Go / No-Go 门禁

删除 ROS `.msg` 字段会改变类型描述、类型哈希、生成代码和 CDR 序列化布
局。`speed` 位于消息结构中间，删除后其后的字段布局也会变化。因此在以下
条件全部得到项目所有者或部署环境确认前，不得删除字段：

1. 已盘点仓库外 publisher / subscriber，包括自定义 `command_topic`、
   `bvh_command_topic` 覆盖所连接的节点。
2. 已盘点外部 ROS 工作空间、生成代码客户端、容器镜像、CLI 与运维脚本。
3. 已决定旧 rosbag2 / MCAP 数据的处理方式：保留旧环境读取、离线转换，或
   明确接受不能直接回放给新 schema。
4. 已冻结下一版 `MotionCommand` 目标 schema，并决定本次只删除 `speed`，还
   是与 `servo_type`、`servo_id`、`position` 等字段统一安排一次破坏性变更。
5. 已决定切换策略：可停机系统采用原消息名原子切换；必须滚动部署或长期兼
   容外部节点时，采用版本化新消息 / 新 topic 并行迁移。
6. 已明确 `motion_msgs` 的 breaking-change 版本策略。
7. 已具备 ROS 2 / colcon 环境，可执行干净接口生成、依赖构建和新 schema
   pub/sub 冒烟验证。

任一条件未满足时，本次变更均为 **No-Go**；仓库内源码合同通过不能替代外部
兼容性确认。

## 4. 重建与切换范围

仓库内直接或运行时依赖 `motion_msgs` 的包包括：

- `execution_manager`
- `websocket_bridge`
- `parallel_3dof_controller`
- `record_load_action`

`robot_bringup` 是间接装配方，也必须纳入最终场景验证。

字段删除后的部署必须按同一切换窗口完成：

1. 停止所有使用旧 `MotionCommand` 的节点和容器。
2. 使用隔离或已清理的 build / install 目录重新生成 `motion_msgs`。
3. 重建全部直接和间接依赖包，并在所有终端 source 同一套新 install。
4. 验证生成消息包含 `duration_ms` 且不包含 `speed`。
5. 验证 `MotionCommand.duration_ms → ServoCommand.speed` 的真实 pub/sub 链路。
6. 同步重启全部 publisher / subscriber；禁止旧、新 schema 混跑。

建议在具备 ROS 环境时使用隔离输出目录：

```bash
colcon --log-base /tmp/rr-motion-log build \
  --base-paths src \
  --build-base /tmp/rr-motion-build \
  --install-base /tmp/rr-motion-install \
  --packages-up-to execution_manager websocket_bridge \
  parallel_3dof_controller record_load_action \
  --event-handlers console_direct+
```

随后 source 新 install，运行相关包测试，并用
`ros2 interface show motion_msgs/msg/MotionCommand` 与真实 pub/sub 冒烟测试
确认新接口。旧 overlay、旧节点和旧生成绑定不得参与该验证。

## 5. 本迁移阶段的完成边界

当前阶段只完成：弃用标记、仓内 no-read / no-write 门禁、失效示例清理、测
试 fixture 收紧和切换要求记录。它不代表仓库外依赖已经确认，也不授权删除
公共字段。

当第 3 节全部门禁有可追溯证据后，再以单独的 breaking-change 阶段删除
`MotionCommand.speed`，同步更新接口版本、事实文档并完成 ROS 环境验证。
