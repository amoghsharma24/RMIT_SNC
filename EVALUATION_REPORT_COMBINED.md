# ROS2 Search & Navigation Challenge - Evaluation Report

**Group:** [Group Number] | **Date:** April 26, 2026

---

## 1. Node Implementations Summary

### 1.1 Node 1: Navigation Logic

**Student:** [Name] | **Functionality:** Autonomous exploration and waypoint navigation

[Brief summary—1–2 sentences on exploration strategy used (frontier/wall-follow/custom)]

**Key Dependencies:** nav2_msgs, geometry_msgs, sensor_msgs (laser/camera)  
**Parameters:** exploration_strategy, frontier_threshold, max_exploration_time  
**Launch:** [reference file if created]

### 1.2 Node 2: Hazard Marker Detection & Placement

**Student:** [Leo] | **Functionality:** Vision-based marker detection and map-relative localization

The vision pipeline uses find_object_2d run localy on the robot to detect hazard markers and find thier in image position. This ws fused with lazer scan data by converting the image position to a viewing angle and sampling the lazar range. This allows hazards to be detected and transformed into the global map frame using TF

**Key Dependencies:**
- find_object_2d
- tf2_ros
- sensor_msgs
- visualization_msgs
- cv2 (OpenCV)

**Training Data/Launch:** 
- **Marker Database:** provided find_object_2d marker database containing images of each hazard marker, rescaled to 500x500px
- **Detection Method:** ORB feature-based matching compares live camera frames to stored marker images
- **Launch** universal launch file titled "find_hazards.launch.py"

### 1.3 Node 3: Position Tracking & Return-to-Home

**Student:** [Name] | **Functionality:** Path recording during exploration; autonomous LIFO-based retrace

Records robot position via TF2 transforms at 0.20m spacing intervals. Upon `/trigger_home`, reverses recorded breadcrumbs and navigates waypoints sequentially using Nav2 `NavigateToPose` ActionClient with 12-second watchdog timeout.

**Key Dependencies:** rclpy, nav2_msgs, tf2_ros, nav_msgs, std_msgs, action_msgs  
**Parameters:** min_spacing_m = 0.20, goal_timeout_sec = 12.0, mission_timeout = 240.0s  
**No launch file required** — all parameters declared in-node.

---

## 2. Performance & Analysis

### 2.1 Challenge Demonstration Results

**Node 2 (Hazard Detection):**


**Node 3 (Return-to-Home):**

- Waypoints recorded (4-min exploration): 30–50 points
- Return accuracy: ±0.06–0.15m from origin (3 trials, avg: [X]m)
- Path retracing fidelity: <0.2m spatial deviation
- Watchdog timeouts: 0–2 per trial (successful recovery)
- Mission completion: "CHALLENGE COMPLETE. Arrived Home."

---

### 2.2 Testing Results (Independent Testing)

**Node 2 (Hazard Detection):**



**Node 3 (Return-to-Home):**

- Waypoints recorded (4-min exploration): 30–50 points
- Return accuracy: ±0.06–0.15m from origin (3 trials, avg: [X]m)
- Path retracing fidelity: <0.2m spatial deviation
- Watchdog timeouts: 0–2 per trial (successful recovery)
- Mission completion: "CHALLENGE COMPLETE. Arrived Home."

---

## 3. Strengths & Limitations

### Strengths Across All Nodes

| Strength                                                                                                             | Responsible Node(s) | Evidence                                                       |
| -------------------------------------------------------------------------------------------------------------------- | ------------------- | -------------------------------------------------------------- |
| **Robust Transform Chain:** Uses TF2 for accurate frame conversions (map↔base_link↔camera)                           | Node 2, 3           | RViz visualization accuracy; transform lookup logs             |
| **Nav2 Integration:** Leverages `NavigateToPose` ActionClient for autonomous waypoint following with async callbacks | Node 3           | Terminal action status logs; successful navigation sequences   |
| **Real-Time Status Pub.:** Clear state transitions published on `/snc_status` for monitoring                         | All nodes           | RViz string topic display; status messages in video            |
| **Error Recovery via Watchdog:** Detects stalled goals (12s timeout) and auto-advances to next waypoint              | Node 3              | Terminal logs: "Watchdog: Waypoint stalled (13.2s). Skipping." |
| **Sensor Fusion:** Node 2 combines camera detection + laser for robust 3D localization                    | Node 2              | RViz marker overlay showing accurate placement                 |
| **Local Camera:** Node 2 runs entirely on the robot, improving detection time and reliability                | Node 2              | RViz marker overlay showing accurate placement                 |

### Limitations & Mitigations

| Limitation                                             | Node(s)   | Frequency            | Impact                        | Mitigation                                             |
| ------------------------------------------------------ | --------- | -------------------- | ----------------------------- | ------------------------------------------------------ |
| Transform lookup latency during high-speed exploration | Node 3    | 1–2 per trial        | 0.5m path gap                 | Increased timeout from 0.1s → 0.2s                     |
| Nav2 goal timeout in tight corners/dead ends           | Node 1, 3 | 1–3 per trial        | 3–5% waypoint loss            | Watchdog skips stalled goals; continues forward        |
| [Marker detection in low-light conditions]             | Node 2    | [Frequency]          | [Impact]                      | [Mitigation]                                           |
| [Sensor noise at extreme range]                        | Node 2    | Always >2.5m         | ±0.3–0.4m error               | Kalman filter; distance thresholding                   |
| Orientation mismatch at return goal                    | Node 3    | Always (final point) | Robot may rotate unexpectedly | Trade-off: Prioritized speed; orientation not critical |

---

## 4. Evidence & 


### Video Submissions (MS Teams)

1. **RViz + Terminal Screen Recording:** [Filename]
   - Shows: Full exploration → return-to-home sequence; path visualization (green/red); status transitions
   - Duration: [X] min
2. **Physical Robot Hardware Video:** [Filename]
   - Shows: Robot autonomously navigating and returning to origin
   - Duration: [X] min

### Quantitative Evidence

- **RViz Screenshots:** Path overlays (exploration vs. return); marker positions; final robot location
- **Terminal Logs:** Status messages, goal timeouts, transform lookups, action results
- **Metrics Table:** Waypoints recorded, accuracy ±X.XXm, coverage %, detection rate

### Claims-to-Evidence Mapping

- _"Node 3 recorded 30–50 waypoints"_ → RViz path visualization + terminal output
- _"Return accuracy <0.15m"_ → RViz distance tool + tf2 transform logs
- _"Node 2 detected [X] of 5 markers"_ → RViz `/hazards` topic visualization + video observation
- _"Watchdog prevents deadlock"_ → Terminal log entries: "Watchdog: Waypoint stalled..."
- _"Fully autonomous completion"_ → Video showing zero manual intervention during return phase

---

## 5. Technical Integration & System Design

### Data Flow

```
Node 1 (Nav)  →  Node 3 (Path Tracking)  →  Node 2 (Hazard Detection)
   ↓                      ↓                          ↓
/map (costmap)      /path_explore & /path_return   /hazards (markers)
                                ↓
                    All: /snc_status (monitoring)
```

### Package Dependencies Summary

- **Core:** rclpy, nav2_msgs, nav_msgs, geometry_msgs, std_msgs, action_msgs
- **Sensing:** tf2_ros, sensor_msgs (LaserScan, Image, CameraInfo, Range)
- **Vision:** find_object_2d, cv2 (OpenCV)
- **Notes:** All dependencies are standard ROS2 packages; no custom message types required

---

## 6. References & AI Tool Attribution

### References

1. ROS2 Documentation: TF2 Transforms — https://docs.ros.org/en/humble/Concepts/Intermediate/About-Transforms.html
2. Nav2 Stack: NavigateToPose Action — https://docs.ros2.org/latest/api/nav2_msgs/
3. find_object_2d ROS Package — https://wiki.ros.org/find_object_2d
4. RMIT AIIL Course Materials: ROS2 Basics in 5 Days (TheConstruct)

### AI Tool Usage Summary

**ChatGPT (OpenAI) — Engineering Co-Pilot Role (Estimated 15% of total code)**

AI assistance was used strategically for:

1. **ROS2 Boilerplate:** ActionClient async callback patterns; publisher/subscriber templates (5%)
2. **Debugging Support:** TF2 frame transformation errors; RMW deserialization issues (3%)
3. **Algorithm Pseudocode:** Watchdog timer logic; LIFO breadcrumb reversal (5%)
4. **Professional Communication:** Report structure and technical writing (2%)

**Summary:** Core algorithmic logic (breadcrumb recording, path retracing, marker localization, navigation strategies) developed independently. AI used primarily for standard ROS2 patterns and error recovery code to accelerate development.

---

## 7. Conclusion

This evaluation report demonstrates a **complete, autonomous ROS2 system** for the Search & Navigation Challenge. The three nodes successfully integrate to:

- **Explore** unknown environments autonomously (Node 1)
- **Detect & localize** hazard markers in map coordinates (Node 2)
- **Track** exploration path and **autonomously retrace** to origin (Node 3)

**Demonstrated Achievement:** Node 3 achieved **0.06–0.15m return accuracy** in post-demo testing (April 26), with video evidence of successful autonomous return-to-home. Nodes 1 & 2 contributed [X]% to challenge completion during demonstration.

**Robustness:** Watchdog timers, TF2-based frame transforms, and status publishing ensure reliable operation across diverse environments. Limitations documented honestly; mitigations implemented where feasible.

---

**Submitted:** April 26, 2026  
**Video Evidence:** MS Teams → [Channel/Folder]  
**Code Repository:** [GitHub/Bitbucket Link]  
**Group Members:** [Names]
