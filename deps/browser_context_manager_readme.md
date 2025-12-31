1. The Core Issue: The "X11 Display" Gap

The Problem: Initially, you were trying to run a browser-based bot as a systemd service. Services in Linux are "non-interactive" and have no access to a monitor (Display). When the bot tried to launch Chrome, Chrome would search for a screen to draw on, find none, and crash with the error: Missing X server or $DISPLAY.

The Struggle: We tried manually starting Xvfb (a virtual monitor) inside the Python code. However, because of how Ubuntu 24.04 (Noble) handles security and permissions, the Chrome process often couldn't "see" the virtual display created by the Python script, or it would time out before the display was ready.
2. The Solution: "System-Level Virtualization"

Instead of forcing Python to manage the hardware/display logic, we moved that responsibility to the Linux System itself.

The Fix (The "xvfb-run" Wrapper): We modified your .service file to use the xvfb-run utility.

    How it works: xvfb-run acts like a "bubble." It creates a virtual 1920x1080 monitor, sets up all the complicated environment variables (DISPLAY, XAUTHORITY), and then launches your bot inside that bubble.

    The Result: From the bot's perspective, it feels like it is running on a real computer with a real monitor. It no longer has to "set up" a display; it just inherits one that is already working.

3. The "Undetected-Chromedriver" Handshake

The Problem: Once the display was fixed, we hit a second error: unable to discover open pages. This happened because we were manually starting Chrome via subprocess, and the timing was off—the bot was trying to talk to Chrome before Chrome was fully awake.

The Fix: We simplified the Python code to let the undetected-chromedriver library handle the launch of the browser executable directly. Since the service provided the "Display," we didn't need the manual subprocess logic anymore. This allowed the library to use its built-in "waiting" logic to ensure Chrome was fully ready before starting the automation.