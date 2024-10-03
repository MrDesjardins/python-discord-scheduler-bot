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
)

SERVICE_NAME = "gametimescheduler.service"


def main():
    options = ["Raspberri PI", "Local", "Exit"]
    terminal_menu = TerminalMenu(options)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        raspberri_pi_menu()
    elif menu_entry_index == 1:
        local_menu()
    elif menu_entry_index == 2:
        sys.exit(0)


def raspberri_pi_menu():
    options = ["Service Status", "Restart Service", "Upgrade Code", "Back"]
    terminal_menu = TerminalMenu(options)
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
    options = [
        "Save Dependencies in requirements.txt",
        "Get Latest DB",
        "Lint",
        "Run Scripts",
        "Run Unit Tests",
        "Back",
    ]
    terminal_menu = TerminalMenu(options)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        save_dependencies()
    elif menu_entry_index == 1:
        get_latest_db()
    elif menu_entry_index == 2:
        lint_code()
    elif menu_entry_index == 3:
        run_scripts_menu()
    elif menu_entry_index == 4:
        run_unit_tests()
    elif menu_entry_index == 5:
        return

    main()


def run_scripts_menu():
    options = ["Community 2D", "Community 3D", "Relationship Time", "Back"]
    terminal_menu = TerminalMenu(options)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index == 0:
        show_community_2d()
    elif menu_entry_index == 1:
        show_community_3d()
    elif menu_entry_index == 2:
        show_relationship()
    elif menu_entry_index == 3:
        local_menu()
        return

    main()


def print_service_status(service_name: str) -> None:
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


def get_latest_db() -> None:
    try:
        # Execute the bash script
        result = subprocess.run(
            [
                "/bin/bash",
                "./analytics/transfer.sh",
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
    lint_black()
    # Run the linting in a separate thread to avoid the PyLint to close the script
    thread = threading.Thread(target=lint_pylint)
    thread.start()
    thread.join()  # Wait for the thread to finish


def lint_black() -> None:
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


def show_community_2d() -> None:
    display_graph_cluster_people()


def show_community_3d() -> None:
    display_graph_cluster_people_3d_animated()


def show_relationship() -> None:
    display_time_relationship()


if __name__ == "__main__":
    main()
