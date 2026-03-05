from gpiozero import MotionSensor
from signal import pause

# Define the sensor on GPIO 17
pir = MotionSensor(17)

def motion_detected():
    print("✨ Motion detected! Someone is there.")

def motion_stopped():
    print("... Clear. All quiet now.")

# Link the events to the functions
pir.when_motion = motion_detected
pir.when_no_motion = motion_stopped

print("PIR Sensor Initializing... (Wait about 10-60 seconds for it to settle)")

# Keep the program running to listen for events
pause()