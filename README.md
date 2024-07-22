# TmuxTop

## Overview
TmuxTop is an advanced Tmux process monitoring tool that provides a top-like interface for managing and monitoring processes within Tmux sessions. This tool leverages a terminal user interface (TUI) to display real-time data on CPU and memory usage of processes running in Tmux panes. Additionally, TmuxTop includes features for exporting session data, and backing up and restoring Tmux sessions.

## Features
- **Real-time Monitoring**: View real-time CPU and memory usage for processes within Tmux panes.
- **Session Management**: Easily navigate through Tmux sessions, windows, and panes.
- **Export Data**: Export session and process data to a JSON file for further analysis.
- **Backup Sessions**: Create backup scripts of your current Tmux sessions, preserving the state and commands.
- **Restore Sessions**: Restore Tmux sessions from previously created backup scripts.
- **Intuitive Interface**: User-friendly terminal interface with navigation and interaction using keyboard shortcuts.

## Installation
Ensure you have Python 3 and the required dependencies installed:

pip install psutil curses argparse
Usage
-----

Run the TmuxTop tool:

sh

Copy code

`python tmuxtop.py`

### Command Line Options

-   `--export`: Export session and process data to a JSON file.
-   `--backup`: Backup current Tmux sessions to a shell script.
-   `--restore`: Restore Tmux sessions from the latest backup script.

### Interactive Commands

While running TmuxTop, use the following keys to interact with the interface:

-   **q**: Quit the application.
-   **e**: Export session data to `tmuxtop_export.json`.
-   **b**: Backup current Tmux sessions.
-   **r**: Restore Tmux sessions from the latest backup script.
-   **Up/Down Arrow Keys**: Scroll through the list of processes and sessions.

Example
-------

Here's an example of how to use TmuxTop:

### Start TmuxTop

sh

Copy code

`python tmuxtop.py`

### Export Session Data

sh

Copy code

`python tmuxtop.py --export`

### Backup Sessions

sh

Copy code

`python tmuxtop.py --backup`

### Restore Sessions

sh

Copy code

`python tmuxtop.py --restore`

Screenshots
-----------

*Include screenshots of TmuxTop interface showing real-time monitoring, navigation through sessions and panes, and the export/backup/restore process.*

Advanced Usage
--------------

### Real-Time Process Monitoring

TmuxTop provides real-time monitoring of processes within Tmux panes. It displays crucial metrics such as CPU and memory usage, user, process IDs, and more, helping you keep track of system resource consumption and performance.

### Session and Window Navigation

TmuxTop organizes processes by Tmux sessions and windows, making it easy to navigate and view detailed information about each pane. This hierarchical view helps in managing complex setups with multiple sessions and windows efficiently.

### Exporting Data

The export feature allows you to save the current state of Tmux sessions and processes to a JSON file. This can be useful for later analysis or reporting. Simply press 'e' while running TmuxTop or use the `--export` option when starting the script.

### Backing Up and Restoring Sessions

TmuxTop's backup and restore functionalities enable you to save and reload your Tmux environment. This is particularly handy for preserving your workflow across reboots or system changes. Use 'b' to backup and 'r' to restore sessions directly within the interface.

Contributing
------------

Contributions are welcome! Please submit a pull request or open an issue to discuss any changes or enhancements. Your feedback and suggestions are valuable to make TmuxTop even better.

License
-------

This project is licensed under the MIT License. See the LICENSE file for more details.

* * * * *

By using TmuxTop, you can enhance your Tmux experience with powerful monitoring and session management capabilities. Whether you're managing complex development environments or simply want better insight into your Tmux processes, TmuxTop is the tool for you.
