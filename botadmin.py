#!/usr/bin/env python3
""" Entry file for the Discord bot admin command """
from datetime import datetime, timedelta
import subprocess
import glob
import io
import os
import sys
import threading
from typing import Optional
import unittest
import black
from simple_term_menu import TerminalMenu
from pylint import lint
from deps.analytic_data_access import fetch_user_info
from deps.analytic_visualizer import (
    display_graph_cluster_people,
    display_graph_cluster_people_3d_animated,
    display_time_relationship,
    display_time_voice_channel,
    display_inactive_user,
    display_user_day_week,
    display_user_line_graph_time,
    display_user_timeline_voice_by_months,
    display_user_timeline_voice_time_by_week,
    display_user_voice_per_month,
)

SERVICE_NAME = "gametimescheduler.service"


def main():
    """First menu"""
    options = ["[1] Raspberry PI", "[2] Local", "[q] Exit"]
    terminal_menu = TerminalMenu(options, title="Environment", show_shortcut_hints=True)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        raspberry_pi_menu()
    elif menu_entry_index == 1:
        local_menu()
    elif menu_entry_index == 2:
        sys.exit(0)
    main()


def raspberry_pi_menu():
    """Menu for actions on the Raspberry PI"""
    options = ["[1] Service Status", "[2] Restart Service", "[3] Upgrade Code", "[q] Back"]
    terminal_menu = TerminalMenu(options, title="Raspberry Actions", show_shortcut_hints=True)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        print_service_status(SERVICE_NAME)
    elif menu_entry_index == 1:
        restart_service(SERVICE_NAME)
    elif menu_entry_index == 2:
        update_code()
    elif menu_entry_index == 3:
        return
    main()


def local_menu():
    """Menu for actions on the local development"""
    options = [
        "[1] Save Dependencies in requirements.txt",
        "[2] Get Latest DB",
        "[3] Get Latest Logs",
        "[4] Lint",
        "[5] Visualizations",
        "[6] Run Tests",
        "[7] Run Coverage Tests",
        "[q] Back",
    ]
    terminal_menu = TerminalMenu(options, title="Local Dev Actions", show_shortcut_hints=True)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        save_dependencies()
    elif menu_entry_index == 1:
        get_latest_db()
    elif menu_entry_index == 2:
        get_latest_logs()
    elif menu_entry_index == 3:
        lint_code()
    elif menu_entry_index == 4:
        show_visualization_menu()
    elif menu_entry_index == 5:
        run_tests()
    elif menu_entry_index == 6:
        run_test_coverage()
    elif menu_entry_index == 7:
        return

    main()


def get_from_to_days(menu_entry_index2: int) -> tuple[int, int]:
    """Get the day from and to"""
    if menu_entry_index2 == 0:
        # From the last 30 days
        from_day = 30
        to_day = 0
        return (from_day, to_day)
    elif menu_entry_index2 == 1:
        # Current Month
        from_day = datetime.now().day
        to_day = 0
        return (from_day, to_day)
    elif menu_entry_index2 == 2:
        # Get the current date
        current_date = datetime.now()

        # Determine the first day of the last month
        first_day_of_this_month = datetime(current_date.year, current_date.month, 1)
        last_month_last_day = first_day_of_this_month - timedelta(days=1)
        last_month_first_day = datetime(last_month_last_day.year, last_month_last_day.month, 1)

        # Calculate the number of days since the first and last day of the last month
        from_day = (current_date - last_month_first_day).days
        to_day = (current_date - last_month_last_day).days
        return (from_day, to_day)
    elif menu_entry_index2 == 3:
        # Since September 21th, 2024
        from_day = (datetime.now() - datetime(2024, 9, 21)).days
        to_day = 0
        return (from_day, to_day)


def show_visualization_menu(time_choice: Optional[int] = None):
    """Menu to choose the visualization"""
    if time_choice is None:
        options = [
            "[1] Community 2D",
            "[2] Community 3D",
            "[3] Duo Relationship Time",
            "[4] Users Total Voices Time Bar",
            "[5] Inactive Users",
            "[6] User per weekday Matrix",
            "[7] Voice time per Month Color Gradient",
            "[8] Time Line Users Activity Line Chart",
            "[9] Monthly Voice Time",
            "[a] Time Line for Specific User",
            "[q] Back",
        ]

        terminal_menu2 = TerminalMenu(
            ["[1] Last 30 days", "[2] Current month", "[3] Last Month", "[4] Since September 21th, 2024"],
            title="Days",
            show_shortcut_hints=True,
        )
        time_choice = terminal_menu2.show()
    if time_choice is None:
        local_menu()
        return
    (from_day, to_day) = get_from_to_days(time_choice)
    terminal_menu = TerminalMenu(
        options, title=f"Visualizations of {from_day} days ago to {to_day} days ago", show_shortcut_hints=True
    )
    menu_entry_index = terminal_menu.show()

    if menu_entry_index == 0:
        display_graph_cluster_people(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 1:
        display_graph_cluster_people_3d_animated(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 2:
        display_time_relationship(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 3:
        display_time_voice_channel(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 4:
        display_inactive_user(from_day=from_day)
    elif menu_entry_index == 5:
        display_user_day_week(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 6:
        display_user_voice_per_month(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 7:
        display_user_timeline_voice_time_by_week(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 8:
        display_user_timeline_voice_by_months(from_day=from_day, to_day=to_day)
    elif menu_entry_index == 9:
        display_user_line_graph_time_ask_user(from_day=from_day, to_day=to_day, time_choice=time_choice)
    elif menu_entry_index == 10:
        local_menu()
        return

    show_visualization_menu()


def display_user_line_graph_time_ask_user(from_day: int, to_day: int, time_choice: int):
    """Ask the user for the user id"""
    # Get the list of users
    user_info_dict = fetch_user_info()
    user_info_list = list(user_info_dict.values())
    # Order alphabetically
    user_info_list.sort(key=lambda x: x.display_name.lower())
    terminal_menu = TerminalMenu(
        [f"{user.display_name} - {user.id}" for user in user_info_list] + ["[q] Back"],
        title="Days",
        show_shortcut_hints=False,
    )
    user_choice = terminal_menu.show()
    if user_choice == len(user_info_list) - 1:
        show_visualization_menu(time_choice)
        return
    display_user_line_graph_time(user_info_list[user_choice].id, True, from_day, to_day)
    display_user_line_graph_time_ask_user(from_day, to_day, time_choice)


def print_service_status(service_name: str) -> None:
    """
    Print the status of the specified service using systemctl
    """
    try:
        # Execute the systemctl status command
        result = subprocess.run(
            ["sudo", "systemctl", "status", service_name],
            text=True,  # ensures the output is a string instead of bytes
            capture_output=True,  # captures stdout and stderr
            check=True,  # raises an exception if the command fails
        )

        # Check if the command was successful
        if result.returncode == 0:
            print(result.stdout)  # prints the output of the command
        else:
            print(f"Error: {result.stderr}")  # prints the error message

    except Exception as e:
        print(f"An exception occurred: {e}")


def restart_service(service_name: str) -> None:
    """
    Restart the specified service using systemctl
    """
    try:
        # Execute the systemctl restart command
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            text=True,  # ensures the output is a string instead of bytes
            capture_output=True,  # captures stdout and stderr
            check=True,  # raises an exception if the command fails
        )

        # Check if the command was successful
        if result.returncode == 0:
            print(result.stdout)  # prints the output of the command
        else:
            print(f"Error: {result.stderr}")  # prints the error message

    except Exception as e:
        print(f"An exception occurred: {e}")


def update_code() -> None:
    """
    1) Use git to pull the latest changes
    2) Install dependencies using the virtual environment
    3) Restart the service
    4) Check the status of the service
    """
    try:
        # Get the current directory and the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Pull the latest changes
        result = subprocess.run(
            ["git", "-C", script_dir, "pull", "origin", "main"], text=True, capture_output=True, check=False
        )
        print("Git output:\n", result.stdout)
        if result.returncode != 0:
            print(f"Failed to pull changes from git: {result.stderr}")
            return

        # Install dependencies using the virtual environment
        result = subprocess.run(
            [f"{script_dir}/.venv/bin/python3", "-m", "pip", "install", "-r", f"{script_dir}/requirements.txt"],
            text=True,
            capture_output=True,
            check=False,
        )
        print("Pip output:\n", result.stdout)
        if result.returncode != 0:
            print(f"Failed to install dependencies: {result.stderr}")
            return

        # Restart the service
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "gametimescheduler.service"], text=True, capture_output=True, check=False
        )
        if result.returncode != 0:
            print(f"Failed to restart the service: {result.stderr}")
            return

        # Check the status of the service
        result = subprocess.run(
            ["sudo", "systemctl", "status", "gametimescheduler.service"], text=True, capture_output=True, check=False
        )
        print("Service status output:\n", result.stdout)
        if result.returncode != 0:
            print(f"Service is not running properly: {result.stderr}")
            return

        print("Script executed successfully.")

    except Exception as e:
        print(f"An exception occurred: {e}")


def save_dependencies() -> None:
    """
    Save the current dependencies to a requirements.txt file
    """
    try:
        # Execute the bash script
        result = subprocess.run(
            ["python3", "-m", "pip", "freeze"],  # Specify the shell and script path
            text=True,  # Return the output as a string
            capture_output=True,  # Capture stdout and stderr
            check=True,  # Raise an exception if the script fails
        )

        # Write the output to the requirements.txt file
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write(result.stdout)

        print("Dependencies saved to requirements.txt")

    except subprocess.CalledProcessError as e:
        print(f"Script failed with error:\n{e.stderr}")
    except Exception as e:
        print(f"An exception occurred: {e}")


def run_tests() -> None:
    """
    Run the unit tests and integration tests using the unittest library
    """
    # Create a stream to capture test runner output
    test_output = io.StringIO()

    # Create a test loader and discover tests from the 'tests' directory
    loader = unittest.TestLoader()
    tests = loader.discover("tests", pattern="*_test.py")

    # Create a test runner that outputs to the test_output stream
    runner = unittest.TextTestRunner(stream=test_output, verbosity=2)

    # Run the tests
    result = runner.run(tests)
    # Print captured output
    print("Test output:")
    print(test_output.getvalue())

    # Print the overall result
    if result.wasSuccessful():
        print("All tests passed.")
    else:
        print(f"Tests failed. Failures: {len(result.failures)}. Errors: {len(result.errors)}.")


def run_test_coverage() -> None:
    """Unit Test Code Coverage"""
    print("Running coverage tests...")
    try:
        # Execute the bash script
        result = subprocess.run(
            ["coverage", "run", "-m", "pytest", "-v", "-s", "./tests"],  # Specify the shell and script path
            text=True,  # Return the output as a string
            capture_output=True,  # Capture stdout and stderr
            check=True,  # Raise an exception if the script fails
        )
        # Check if the script executed successfully
        if result.returncode != 0:
            print(f"Script failed with error:\n{result.stderr}")

        # Execute the bash script
        result = subprocess.run(
            ["coverage", "report", "-m"],  # Specify the shell and script path
            text=True,  # Return the output as a string
            capture_output=True,  # Capture stdout and stderr
            check=True,  # Raise an exception if the script fails
        )
        # Check if the script executed successfully
        if result.returncode == 0:
            print("Script output:\n", result.stdout)
        else:
            print(f"Script failed with error:\n{result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Script failed with error:\n{e.stderr}")
    except Exception as e:
        print(f"An exception occurred: {e}")


def get_latest_db() -> None:
    """Transfer the latest database from the server"""
    try:
        # Execute the bash script
        result = subprocess.run(
            [
                "/bin/bash",
                "./analytics/transfer_db.sh",
            ],  # Specify the shell and script path
            text=True,  # Return the output as a string
            capture_output=True,  # Capture stdout and stderr
            check=True,  # Raise an exception if the script fails
        )

        # Check if the script executed successfully
        if result.returncode == 0:
            print("Script output:\n", result.stdout)
        else:
            print(f"Script failed with error:\n{result.stderr}")

    except Exception as e:
        print(f"An exception occurred: {e}")


def get_latest_logs() -> None:
    """Transfer the latest database from the server"""
    try:
        # Execute the bash script
        result = subprocess.run(
            [
                "/bin/bash",
                "./analytics/transfer_logs.sh",
            ],  # Specify the shell and script path
            text=True,  # Return the output as a string
            capture_output=True,  # Capture stdout and stderr
            check=True,  # Raise an exception if the script fails
        )

        # Check if the script executed successfully
        if result.returncode == 0:
            print("Script output:\n", result.stdout)
        else:
            print(f"Script failed with error:\n{result.stderr}")

    except Exception as e:
        print(f"An exception occurred: {e}")


def lint_code() -> None:
    """
    1) Run lint black to format the code
    2) Run PyLint to check for code quality
    """
    lint_black()
    # Run the linting in a separate thread to avoid the PyLint to close the script
    thread = threading.Thread(target=lint_pylint)
    thread.start()
    thread.join()  # Wait for the thread to finish


def lint_black() -> None:
    """Run Black to format the code"""
    try:
        print("Running Black...")
        # Use glob to find all Python files to format
        python_files = glob.glob("**/*.py", recursive=True)

        if not python_files:
            print("No Python files found.")
            return

        # Iterate over each file and format it using black
        for file_path in python_files:
            print(f"Formatting {file_path}...")
            with open(file_path, "r", encoding="utf-8") as f:
                original_code = f.read()

            # Format the code
            file_mode = black.FileMode(line_length=120)
            formatted_code = black.format_str(original_code, mode=file_mode)

            # Write the formatted code back to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(formatted_code)

        print("Code formatting complete.")

    except Exception as e:
        print(f"An exception occurred: {e}")


def lint_pylint():
    """Run PyLint to check for code quality"""
    try:
        # Use glob to find all Python files
        python_files = glob.glob("**/*.py", recursive=True)

        if not python_files:
            print("No Python files found.")
            return

        # Run pylint
        lint.Run(python_files)

    except SystemExit as e:
        # Handle the SystemExit exception raised by pylint
        print(f"Pylint exited with status: {e.code}")
    except Exception as e:
        print(f"An exception occurred: {e}")


if __name__ == "__main__":
    main()
