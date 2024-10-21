#!/usr/bin/env python3
""" Entry file for the Discord bot admin command """
import subprocess
import glob
import io
import os
import sys
import threading
import unittest
import black
from simple_term_menu import TerminalMenu
from pylint import lint
from deps.analytic_visualizer import (
    display_graph_cluster_people,
    display_graph_cluster_people_3d_animated,
    display_time_relationship,
    display_time_voice_channel,
    display_inactive_user,
    display_user_day_week,
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
        "[6] Run Unit Tests",
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
        run_unit_tests()
    elif menu_entry_index == 6:
        run_test_coverage()
    elif menu_entry_index == 7:
        return

    main()


def show_visualization_menu():
    """Menu to choose the visualization"""
    options = [
        "[1] Community 2D",
        "[2] Community 3D",
        "[3] Relationship Time",
        "[4] Total Voices Time",
        "[5] Inactive Users",
        "[6] User per weekday",
        "[q] Back",
    ]
    terminal_menu = TerminalMenu(options, title="Visualizations", show_shortcut_hints=True)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        display_graph_cluster_people()
    elif menu_entry_index == 1:
        display_graph_cluster_people_3d_animated()
    elif menu_entry_index == 2:
        display_time_relationship()
    elif menu_entry_index == 3:
        display_time_voice_channel()
    elif menu_entry_index == 4:
        display_inactive_user()
    elif menu_entry_index == 5:
        display_user_day_week()
    elif menu_entry_index == 6:
        local_menu()
        return

    main()


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


def run_unit_tests() -> None:
    """
    Run the unit tests using the unittest
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
