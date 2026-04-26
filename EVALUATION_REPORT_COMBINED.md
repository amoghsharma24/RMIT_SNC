# ROS2 Search & Navigation Challenge - Evaluation Report

**Group:** A2-SNC 6

---

## 1. Node Implementations Summary

### 1.1 Node 1: Navigation Logic

**Student:** student assigned to node 1 stopped collaborating early in the project, and no implementation of node 1 was attempted

### 1.2 Node 2: Hazard Marker Detection & Placement

**Student:** Leo Barnes | **Functionality:**

The vision pipeline uses find_object_2d, running locally on the robot, to detect hazard markers and determine their position in the camera image. The detector outputs the marker ID and its position in the image.

This image position is combined with laser scan data by converting the horizontal pixel location into a viewing angle using the camera’s field of view. The laser scan is then sampled at this angle to get the distance to the object, allowing the system to estimate the marker’s position relative to the robot.

The position is first calculated in the robot’s base_link frame, and then transformed into the global map frame using TF2. This allows all hazards to be placed correctly on the map and visualised in RViz.

To improve reliability, detections must be consistent over multiple frames before being accepted, and duplicate hazards are ignored based on their position. This helps reduce noise and improves accuracy.

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

**Student:** Amogh Sharma | **Functionality:** tracks and publishes the path of the robot taken while exploring, returns to the robot’s home (starting) position by following this path in reverse order. tracks and publishes the path of the robot taken when returning to home.

This node records the robot’s position continuously using TF2 transforms between the map and base_link frames. Positions are stored at fixed spatial intervals (0.20 m) to avoid redundant data while maintaining path accuracy.

When a return command is triggered, the recorded path is reversed using a Last-In-First-Out (LIFO) approach. The robot then navigates through each recorded waypoint sequentially using the Nav2 NavigateToPose ActionClient. This ensures that the robot follows the exact path it previously travelled, rather than generating a new path.

To maintain the responsiveness, the node uses asynchronous callbacks which allows navigation feedback and transform lookups to run without blocking execution. I also added a watchdog timer (12 seconds) to detect stalled navigation goals. If a waypoint is not reached within this time, it is skipped to prevent deadlock. A positional tolerance is also added to account for small odometry errors during movement.

**Key Dependencies:** rclpy, nav2_msgs, tf2_ros, nav_msgs, std_msgs, action_msgs  
**Parameters:** min_spacing_m = 0.20, goal_timeout_sec = 12.0, mission_timeout = 240.0s  
**Launch Notes:** No external launch file required. All parameters are declared and initialised within the node.

---

## 2. Performance & Analysis

### 2.1 Challenge Demonstration Results

**Node 2 (Hazard Detection):**

- Demo: 2 hazards where detected and thier locations where off significantly, and the return was not triggered

**Node 3 (Return-to-Home):**

- Demo: During the Week 6 demo, Node 3 did not fully complete the return-to-home task, but it published \path_explore. After refinement and additional testing, the node successfully completed full return-to-home sequences autonomously.

---

### 2.2 Independent Testing Results

**Node 2:**

**Node 3:**

- Key Metric: The system consistently returned the robot to its starting position with an average positional error between 0.06 m and 0.15 m this was measured using TF2 transforms and RViz visualisation tools.

- Video evidence: shows the robot completing exploration and return phases without manual input (except /trigger_home) and with clear status updates published throughout execution.

### 2.3 Quantified Results (Independent Testing)

**Node 2 (Hazard Detection):**

- **Node 3 (Return-to-Home):**

- Waypoints recorded: 25-40 points during exploration
- Return accuracy: ±0.06–0.15 m (3 trials)
- Path fidelity: <0.20 m deviation from original path
- Mission completion: 100% success rate after refinement

---

## 3. Strengths & Limitations

### Strengths

**Node 2:**

- Uses sensor fusion: It does not rely only on the camera. It combines marker detection with laser distance data, which gives a better estimate of where the hazard is.
- Runs vision locally on the robot: This reduces network delay and avoids problems from the unreliable shared robot network.
- Start and return triggers are automatic: The system can detect the start marker, begin exploration, and trigger return-home after finding hazards or after the timeout.
- Duplicate filtering: It avoids repeatedly publishing the same hazard when the robot sees the same marker multiple times.
- Stable detection filtering: It waits for consistent detections before accepting a marker, reducing false positives from brief or noisy detections.

**Node 3:**

- Consistent Return-to-Home Accuracy: The robot was able to return to its starting position within ±0.06–0.15 m across multiple trials.
- Reliable Path Tracking: The system successfully recorded and published the exploration path and used it for return navigation.

- Sequential Waypoints (LIFO): The robot retraced its path using a Last-In-First-Out structure, So it only explored the known safe path.

- Failure Handling (Watchdog Timer): Stalled navigation goals were detected and skipped, allowing the robot to continue instead of getting stuck.

**Evidence:** RViz visualisation, TF2-based distance measurement, terminal logs, video recording of the robot, and screen recording of the terminal and RViz.

### Limitations & Mitigations

**Node 2:**

- Approximate Angle Estimation: The pixel-to-angle conversion assumes a fixed camera field of view, which may not be perfectly accurate.
  - Impact: Left/right errors in hazard positioning, leading to noticeable map misalignment.
  - Mitigation: Tune the field of view parameter experimentally and apply proper camera calibration.

- Camera-Laser Misalignment: The camera and lidar are mounted in slightly different positions on the robot.
  - Impact: Small positional offsets between detected hazards and their true location.
  - Possible Causes: Physical separation between camera and laser sensors, lack of precise calibration between sensors.
  - Mitigation: Apply a fixed offset correction between camera and lidar frames and use calibrated sensor transforms for improved alignment.

- Reduced Accuracy at Long Distances: Laser readings become less reliable at greater distances.
  - Impact: Increased localisation error, approximately ±0.3–0.5 m, for distant hazards.
  - Possible Causes: Sensor noise increases with range, lower resolution of laser scan at distance, and wider spread of laser beams over longer distances.
  - Mitigation: Ignore detections beyond a distance threshold, average or filter nearby laser readings, and prioritise closer detections for more accurate placement.

- No Depth from Vision Alone: Distance is taken entirely from the laser scan rather than the camera.
  - Impact: Hazards cannot be localised if laser data is missing or incorrect.
  - Mitigation: Add validation checks for laser readings and use multiple laser samples instead of a single point.

- No Camera Calibration: The system uses assumed camera parameters instead of calibrated values.
  - Impact: Reduced overall accuracy in hazard localisation.
  - Mitigation: Perform camera calibration to obtain accurate intrinsic parameters and apply distortion correction before processing detections.

- Processing Pauses During Detection: The robot briefly stops while processing hazards.
  - Impact: Slower exploration and increased total task time.
  - Mitigation: Minimise pause duration during processing, allow detection to continue during movement where possible, and optimise the processing pipeline to reduce delay.

**Node 3:**

- Path misalignment b/w exploration and return: The return path does not perfectly overlap with the exploration path, added in the evidence folder (green & purple lines. Green being \path_explore and purple being \path_return).
  - Possible Causes:
    - TF2 transform timing delays
    - Slam drift during movement: During exploration, slam_toolbox updated the map as new features were discovered this made it jump the coordinate origin. Since breadcrumbs are saved as fixed coordinates, they appeared out of bounds after the map shift).
    - Evidence: Added as a separate screenshot in evidence labelled "path misalignment".
- Final orientation not controlled: The robot returns to the correct position but may not match the original orientation.

### General Limitations

During development, a key limitation was limited access to ROSbot 3.0s, as multiple teams were sharing a small number of units. This meant our team had a period of about a week without direct access to them, which slowed down real-world testing. To work around this, most development and testing was done using simulation and the ROSbot 2.0s and this introduced a real gap. The behaviour in simulation did not always match the physical robot.

---

## 4. Evidence & Validation

### Video Submissions (MS Teams)

**Node 2:**

**Node 3:**

- Node3_screen_recording.mkv: A screen recording of RViz and the terminal running at the same time. This shows the LIFO retracing logic in action, including the robot navigating through all 25 recorded waypoints.

- Node3_iphone_rosbot3_recording.MOV: A video of the physical ROSbot 3.0 (Underdark) completing the return-to-home task. This confirms that the robot successfully returned to its starting position.

- Node3_path_misalignment.png: A RViz screenshot showing the difference between the exploration path and the return path. This image supports the analysis in Section 3 and highlights that while the robot followed the correct waypoints, the actual path taken during return was different which was likely due to the slam drift.

---

## 5. References & AI Tool Attribution

### References

1. ROS2 Documentation: TF2 Transforms: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Transforms.html
2. Nav2 Stack: NavigateToPose Action: https://docs.ros2.org/latest/api/nav2_msgs/
3. RMIT AIIL Course Materials: ROS2 Basics in 5 Days.
4. The AIIL wiki.

### AI Tool Usage Summary

**Node 2:**
**Node 3:** Added a .txt file with the AI logs.
