# 运行时 Profiling 基线

## 1. 目的与边界

本文记录 `docs/plan.md` Phase 6 的第一版可复现运行时基线，用于决定是否存在
值得迁移到 C++ 的真实热点。

它不是硬件性能承诺，不比较 Python/C++ 后端，也不替代目标 ROS 2 Jazzy、真实
设备或饱和负载验收。


## 2. 工作负载

脚本：`scripts/profile_runtime_hotpaths.py`

运行方式：

```bash
python3 scripts/profile_runtime_hotpaths.py \
  --samples 200 \
  --warmup 20 \
  --timeout-sec 2 \
  --output /tmp/runtime-profile.json
```

脚本在同一进程创建真实 `rclpy` 节点和 `MultiThreadedExecutor`，使用 DDS 顺序
闭环一次只发送一条请求。所有 endpoint 都按进程 PID remap 到独立 namespace，
不接入默认控制图。motion owner 的 `l0` / `l1` / `l2` 通过显式命令行参数
覆盖，并写入 JSON，默认值与正式 `parallel_3dof_params.yaml` 一致。

测量路径：

1. `MotionCommand -> ExecutionManagerNode -> ServoCommand`
2. `Vector3 -> Parallel3DOFControllerNode -> 3 x MotionCommand`
3. `ServoCommand -> SimServoBridge -> ServoCommand`

每条路径记录 20 个 warmup 和 200 个计量样本。延迟为发布调用到最后一个预期
输出到达 probe callback 的单向端到端 wall-clock 时间；吞吐是顺序闭环样本数除以
计量 wall-clock 时间；CPU 比例是同一进程 `process_time / wall_time * 100`；
jitter 是所有计量样本 latency ms 的总体标准差。motion owner 还会在 warmup 后
记录 solver 调用的分段 wall-clock 时间，用于区分求解成本和 ROS/DDS/发布成本；
该分段计时不改变节点业务逻辑。p50/p95/p99 使用线性插值排名 `(n - 1) * q`。


## 3. 基线结果

评估日期：2026-07-21。

环境：禁网、源码只读的临时 ARM64 容器；ROS 2 Humble、Python 3.10.12、
`rmw_fastrtps_cpp`、4 个可见 CPU。16 包依赖闭包 clean build 通过。

| 路径 | 完成/超时 | p50 ms | p95 ms | p99 ms | max ms | jitter ms | 吞吐 Hz | CPU % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| execution_manager | 200 / 0 | 16.55 | 43.75 | 57.16 | 594.27 | 43.18 | 43.95 | 98.09 |
| current motion owner | 200 / 0 | 24.06 | 50.12 | 70.13 | 103.89 | 12.84 | 36.54 | 103.77 |
| simulation_bridge | 200 / 0 | 13.99 | 33.03 | 45.51 | 107.57 | 10.82 | 58.14 | 101.02 |

三条路径均无发现或请求超时。该容器内 `servo_msgs` 的 CMake 构建日志出现时钟
偏移 warning，但 build 以退出码 0 完成；不能把该 warning 当作性能结论。

### 3.1 2026-07-23 本机校准复测

环境：macOS ARM64、ROS 2 Humble、Python 3.12.13、Cyclone DDS；使用
`/private/tmp/robot-runtime-all19-20260723` 安装空间，显式加载正式几何参数
`l0=0.02`、`l1=0.01`、`l2=0.03`。共完成 5 轮，每轮每条路径 200 个计量样本、
20 个 warmup，三条路径合计 3000 个样本，零超时。下表为五轮算术平均；`max`
为五轮中的全局最大值：

| 路径 | p50 ms | p95 ms | p99 ms | max ms | jitter ms | 吞吐 Hz | CPU % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| execution_manager | 0.99 | 1.77 | 2.44 | 7.60 | 0.37 | 849.93 | 103.00 |
| current motion owner | 1.51 | 2.56 | 3.93 | 7.81 | 0.55 | 547.92 | 101.42 |
| simulation_bridge | 0.49 | 1.01 | 1.68 | 6.48 | 0.29 | 1570.19 | 98.37 |

motion owner solver 分段五轮平均为 p50/p95/p99 `0.260/0.564/0.896ms`，
solver p50 约占 motion 端到端 p50 的 `17.2%`。这证明 solver 是可测成本，
但仍不能单凭端到端热点排序宣称 C++ 迁移收益；还需要目标 Jazzy、Python/C++
差分、launch 单值切换以及硬件和仿真回归。


## 4. 结论

1. `execution_manager` 的尾部延迟和 jitter 最高，594.27ms 单一最大值需要先
   用重复运行和 tracing 判断是否属于调度异常、状态发布或 DDS 行为，不能仅凭
   一次基线迁移安全仲裁器。
2. 当前 motion owner 的 p50/p99 均高于仿真桥，后续应优先区分并联机构
   kinematics、NumPy 原生计算和 Python/DDS 调度成本。
3. 仿真桥的纯转发路径目前未显示足以证明必须迁移的独立证据；现有
   `sim_joint_bridge_cpp` 也不是 Python servo bridge 的等价后端，不能作为
   Phase 6 迁移完成。
4. 三条 CPU 比例接近或略高于 100%，反映单进程、多线程、短轮询的闭环测试
   负载，不表示单个节点稳定占用一个完整 CPU，也不能外推到硬件或并发饱和吞
   吐。

因此 Phase 6 仍为 `25%`：三个目标责任域已有实际、可重复的 ROS/DDS 基线，
本机复测还补充了显式几何参数和 solver 分段成本，但尚未完成基于证据的 C++
后端、launch 单值切换、Python/C++ 差分合同，或硬件/仿真双环境回归。


## 5. 后续门禁

下一步先在目标 Jazzy 与目标硬件或等价仿真环境中重复至少五轮，并增加
`ros2_tracing` 或等价 callback/DDS tracing，拆分 publish、callback、求解、
状态发布与序列化时间。只有确认稳定热点后，才允许迁移一个保持相同
Topic/Service/Action、消息与参数合同的后端；Python/C++ 同负载对比、launch
单值选择和仿真/硬件回归均为 Phase 6 `50%` 的前置条件。
