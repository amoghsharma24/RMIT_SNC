import rclpy
from rclpy.node import Node
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

class MyTracker(Node):
    def __init__(self):
        super().__init__('path_recorder_node')

        # This part sets up the "Listener" - it listens to the robot's position
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Create a timer that runs every 1 second
        self.timer = self.create_timer(1.0, self.record_positiSon)

    def record_position(self):
        try:
            # We ask: "Where is the robot (base_link) relative to the map?"
            now = rclpy.time.Time()
            t = self.tf_buffer.lookup_transform('map', 'base_link', now)

            # Get the X and Y coordinates
            x = t.transform.translation.x
            y = t.transform.translation.y
            
            self.get_logger().info(f'I am at: X={x:.2f}, Y={y:.2f}')

        except TransformException as ex:
            # If the robot hasn't started mapping yet, it will show this error
            self.get_logger().info(f'Still waiting for map... {ex}')

def main(args=None):
    rclpy.init(args=args)
    node = MyTracker()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()