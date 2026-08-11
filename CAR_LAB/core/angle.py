def wrap_deg(angle):
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def angle_error_deg(target, actual):
    return wrap_deg(float(target) - float(actual))
