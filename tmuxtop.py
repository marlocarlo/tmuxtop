#!/usr/bin/env python3

import curses
import psutil
import subprocess
import time
import os
from collections import defaultdict, deque
import argparse
import shlex

def get_tmux_info():
    sessions = defaultdict(lambda: defaultdict(list))
    try:
        tmux_output = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}:#{window_name}:#{pane_index}:#{pane_pid}"],
            capture_output=True, text=True, check=True
        ).stdout.strip().split('\n')

        for line in tmux_output:
            session, window_index, window_name, pane_index, pane_pid = line.split(':')
            sessions[session][f"{window_index}:{window_name}"].append((pane_index, pane_pid))

    except subprocess.CalledProcessError:
        pass

    return sessions

def get_process_tree(pid):
    try:
        process = psutil.Process(int(pid))
        return process.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []

def get_actual_command(pid):
    try:
        process = psutil.Process(int(pid))
        children = process.children(recursive=True)

        if children:
            actual_process = children[-1]
        else:
            actual_process = process

        cmd = actual_process.cmdline()

        if cmd and cmd[0] not in ['bash', 'sh', 'zsh', 'fish']:
            return cmd

        try:
            with open(f"/proc/{pid}/cmdline", 'rb') as f:
                content = f.read().decode('utf-8').strip('\x00')
                if content and not content.startswith(('bash', 'sh', 'zsh', 'fish')):
                    return content.split('\x00')
        except:
            pass

        return None
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

class ProcessInfo:
    def __init__(self, process):
        self.process = process
        self.cpu_history = deque(maxlen=20)
        self.mem_history = deque(maxlen=20)
        self.update()

    def update(self):
        try:
            with self.process.oneshot():
                self.pid = self.process.pid
                self.ppid = self.process.ppid()
                self.username = self.process.username()[:8]
                cpu_percent = self.process.cpu_percent()
                mem_percent = self.process.memory_percent()
                self.cpu_history.append(cpu_percent)
                self.mem_history.append(mem_percent)
                self.create_time = time.strftime("%H:%M:%S", time.localtime(self.process.create_time()))
                self.cmdline = self.process.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def get_cpu_graph(self):
        return self._get_graph(self.cpu_history)

    def get_mem_graph(self):
        return self._get_graph(self.mem_history)

    def _get_graph(self, data):
        if not data:
            return " " * 10
        max_value = max(max(data), 0.1)  # Avoid division by zero
        graph_chars = "▁▂▃▄▅▆▇"
        graph = ""
        for value in data:
            height = min(int((value / max_value) * (len(graph_chars) - 1)), len(graph_chars) - 1)
            graph += graph_chars[height]
        return graph.ljust(10)


class TmuxTop:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        if stdscr:
            curses.curs_set(0)
            self.stdscr.timeout(1000)
            self.setup_colors()
        self.scroll_position = 0
        self.sessions = {}
        self.process_cache = {}
        self.last_update = 0
        self.update_interval = 2  # Update every 2 seconds

    def setup_colors(self):
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Default
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Header
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Good status
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK) # Warning status
        curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)    # Critical status
        curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_BLACK)   # Info

    def update_data(self):
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self.sessions = get_tmux_info()
            new_cache = {}
            for session in self.sessions.values():
                for window in session.values():
                    for _, pid in window:
                        processes = get_process_tree(pid)
                        for process in processes:
                            if process.pid in self.process_cache:
                                self.process_cache[process.pid].update()
                                new_cache[process.pid] = self.process_cache[process.pid]
                            else:
                                new_cache[process.pid] = ProcessInfo(process)
            self.process_cache = new_cache
            self.last_update = current_time

    def draw_screen(self):
        if not self.stdscr:
            return

        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()

        # Draw header
        header = " TmuxTop | Press 'q' to quit | 'b' to backup | 'r' to restore | Up/Down to scroll "
        self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
        self.stdscr.addstr(0, 0, header.center(width))
        self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        # Draw column headers
        headers = ["PID", "PPID", "USER", "CPU%", "MEM%", "CPU", "MEM", "TIME", "COMMAND"]
        header_str = "{:<7} {:<7} {:<8} {:>5} {:>5} {:<10} {:<10} {:<8} {:<}".format(*headers)
        self.stdscr.attron(curses.color_pair(6) | curses.A_BOLD)
        self.stdscr.addstr(2, 0, header_str)
        self.stdscr.attroff(curses.color_pair(6) | curses.A_BOLD)

        line = 3
        for session_name, windows in self.sessions.items():
            if line - self.scroll_position >= height:
                break
            if line >= self.scroll_position:
                self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                self.stdscr.addstr(line - self.scroll_position, 0, f"Session: {session_name}")
                self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            line += 1

            for window_name, panes in windows.items():
                if line - self.scroll_position >= height:
                    break
                if line >= self.scroll_position:
                    self.stdscr.attron(curses.color_pair(6))
                    self.stdscr.addstr(line - self.scroll_position, 2, f"Window: {window_name}")
                    self.stdscr.attroff(curses.color_pair(6))
                line += 1

                for pane_index, pid in panes:
                    if line - self.scroll_position >= height:
                        break
                    if line >= self.scroll_position:
                        self.stdscr.addstr(line - self.scroll_position, 4, f"Pane {pane_index}:")
                    line += 1

                    actual_cmd = get_actual_command(pid)
                    if actual_cmd:
                        cmd_str = ' '.join(actual_cmd)
                        if line - self.scroll_position >= height:
                            break
                        if line >= self.scroll_position:
                            self.stdscr.addnstr(line - self.scroll_position, 6, cmd_str, width - 7)
                        line += 1

                    processes = get_process_tree(pid)
                    for process in processes:
                        info = self.process_cache.get(process.pid)
                        if info:
                            cpu_percent = info.cpu_history[-1] if info.cpu_history else 0
                            mem_percent = info.mem_history[-1] if info.mem_history else 0
                            process_str = f"{info.pid:<7} {info.ppid:<7} {info.username:<8} {cpu_percent:5.1f} {mem_percent:5.1f}"
                            if line - self.scroll_position >= height:
                                break
                            if line >= self.scroll_position:
                                self.stdscr.addnstr(line - self.scroll_position, 6, process_str, width - 7)
                                cpu_graph = info.get_cpu_graph()
                                mem_graph = info.get_mem_graph()
                                cpu_color = 3 if cpu_percent < 50 else (4 if cpu_percent < 80 else 5)
                                mem_color = 3 if mem_percent < 50 else (4 if mem_percent < 80 else 5)
                                self.stdscr.addnstr(line - self.scroll_position, len(process_str) + 6, cpu_graph, 10, curses.color_pair(cpu_color))
                                self.stdscr.addnstr(line - self.scroll_position, len(process_str) + 17, mem_graph, 10, curses.color_pair(mem_color))
                                self.stdscr.addnstr(line - self.scroll_position, len(process_str) + 28, f"{info.create_time:>8} {' '.join(info.cmdline)}", width - len(process_str) - 33)
                            line += 1

                line += 1

        self.stdscr.refresh()

    def backup_sessions(self):
        try:
            subprocess.run(["tmux", "list-sessions"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            if self.stdscr:
                self.stdscr.addstr(0, 0, "No tmux sessions to backup", curses.A_REVERSE)
                self.stdscr.refresh()
                time.sleep(2)
            else:
                print("No tmux sessions to backup")
            return

        backup_file = f"tmux_backup_{int(time.time())}.sh"
        with open(backup_file, "w") as f:
            f.write("#!/bin/bash\n\n")
            f.write("# Tmux session backup created by TmuxTop\n\n")

            for session_name in self.sessions:
                f.write(f"tmux new-session -d -s {shlex.quote(session_name)}\n")

                for window_name, panes in self.sessions[session_name].items():
                    window_index, window_name = window_name.split(':', 1)
                    f.write(f"tmux rename-window -t {shlex.quote(session_name)}:{window_index} {shlex.quote(window_name)}\n")

                    for i, (pane_index, pid) in enumerate(panes):
                        if i > 0:
                            f.write(f"tmux split-window -t {shlex.quote(session_name)}:{window_index}\n")

                        # Get the current working directory of the pane
                        pane_pwd = subprocess.run(
                            ["tmux", "display-message", "-p", "-t", f"{session_name}:{window_index}.{pane_index}", "#{pane_current_path}"],
                            capture_output=True, text=True
                        ).stdout.strip()

                        f.write(f"tmux send-keys -t {shlex.quote(session_name)}:{window_index}.{pane_index} 'cd {shlex.quote(pane_pwd)}' C-m\n")

                        actual_cmd = get_actual_command(pid)
                        if actual_cmd:
                            cmd = ' '.join(shlex.quote(arg) for arg in actual_cmd)
                            f.write(f"tmux send-keys -t {shlex.quote(session_name)}:{window_index}.{pane_index} {cmd} C-m\n")

        os.chmod(backup_file, 0o755)
        if self.stdscr:
            self.stdscr.addstr(0, 0, f"Sessions backed up to {backup_file}", curses.A_REVERSE)
            self.stdscr.refresh()
            time.sleep(2)
        else:
            print(f"Sessions backed up to {backup_file}")

    def restore_sessions(self):
        backup_files = [f for f in os.listdir() if f.startswith("tmux_backup_") and f.endswith(".sh")]
        if not backup_files:
            if self.stdscr:
                self.stdscr.addstr(0, 0, "No backup files found", curses.A_REVERSE)
                self.stdscr.refresh()
                time.sleep(2)
            else:
                print("No backup files found")
            return

        latest_backup = max(backup_files, key=os.path.getctime)
        try:
            subprocess.run(["bash", latest_backup], check=True)
            if self.stdscr:
                self.stdscr.addstr(0, 0, f"Sessions restored from {latest_backup}", curses.A_REVERSE)
            else:
                print(f"Sessions restored from {latest_backup}")
        except subprocess.CalledProcessError:
            if self.stdscr:
                self.stdscr.addstr(0, 0, f"Failed to restore sessions from {latest_backup}", curses.A_REVERSE)
            else:
                print(f"Failed to restore sessions from {latest_backup}")

        if self.stdscr:
            self.stdscr.refresh()
            time.sleep(2)

    def run(self):
        while True:
            self.update_data()
            self.draw_screen()

            # Handle key presses
            key = self.stdscr.getch()
            if key == ord('q'):
                break
            elif key == ord('b'):
                self.backup_sessions()
            elif key == ord('r'):
                self.restore_sessions()
            elif key == curses.KEY_UP and self.scroll_position > 0:
                self.scroll_position -= 1
            elif key == curses.KEY_DOWN:
                self.scroll_position += 1

def main(stdscr):
    TmuxTop(stdscr).run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TmuxTop - Tmux Process Monitor")
    parser.add_argument("--backup", action="store_true", help="Backup tmux sessions")
    parser.add_argument("--restore", action="store_true", help="Restore tmux sessions")
    args = parser.parse_args()

    if args.backup:
        TmuxTop(None).backup_sessions()
    elif args.restore:
        TmuxTop(None).restore_sessions()
    else:
        curses.wrapper(main)
