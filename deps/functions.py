
def get_empty_votes():
    """ Returns an empty votes dictionary.
    Used to initialize the votes cache for a single day.
    Each array contains SimpleUser
    """
    return {
        '4pm': [],
        '5pm': [],
        '6pm': [],
        '7pm': [],
        '8pm': [],
        '9pm': [],
        '10pm': [],
        '11pm': [],
        '12pm': [],
        '1am': [],
        '2am': [],
        '3am': [],
    }
