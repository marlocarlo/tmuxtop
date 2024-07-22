#!/usr/bin/env python3

import curses
import psutil
import subprocess
import time
import json
import os
from collections import defaultdict, deque
import argparse

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
        children = process.children(recursive=True)
        return [process] + children
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []

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
            return " " * 20
        max_value = max(data)
        if max_value == 0:
            return " " * 20
        graph = ""
        for value in data:
            height = int((value / max_value) * 8)
            graph += "█"[8-height:]
        return graph.ljust(20)

class TmuxTop:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.timeout(1000)
        self.scroll_position = 0
        self.sessions = {}
        self.process_cache = {}
        self.last_update = 0
        self.update_interval = 2  # Update every 2 seconds

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
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()

        # Draw header
        header = "TmuxTop - Press 'q' to quit, 'e' to export, 'b' to backup, 'r' to restore, Up/Down to scroll"
        self.stdscr.addstr(0, 0, header.center(width), curses.A_REVERSE)

        # Draw column headers
        headers = ["PID", "PPID", "USER", "CPU%", "MEM%", "CPU Graph", "MEM Graph", "TIME", "COMMAND"]
        header_str = "{:<7} {:<7} {:<8} {:>5} {:>5} {:<20} {:<20} {:<8} {:<}".format(*headers)
        self.stdscr.addstr(2, 0, header_str, curses.A_BOLD)

        line = 3
        for session_name, windows in self.sessions.items():
            if line - self.scroll_position >= height:
                break
            if line >= self.scroll_position:
                self.stdscr.addstr(line - self.scroll_position, 0, f"Session: {session_name}", curses.A_BOLD | curses.A_UNDERLINE)
            line += 1

            for window_name, panes in windows.items():
                if line - self.scroll_position >= height:
                    break
                if line >= self.scroll_position:
                    self.stdscr.addstr(line - self.scroll_position, 2, f"Window: {window_name}", curses.A_BOLD)
                line += 1

                for pane_index, pid in panes:
                    if line - self.scroll_position >= height:
                        break
                    if line >= self.scroll_position:
                        self.stdscr.addstr(line - self.scroll_position, 4, f"Pane {pane_index}:", curses.A_BOLD)
                    line += 1

                    processes = get_process_tree(pid)
                    for process in processes:
                        info = self.process_cache.get(process.pid)
                        if info:
                            cpu_percent = info.cpu_history[-1] if info.cpu_history else 0
                            mem_percent = info.mem_history[-1] if info.mem_history else 0
                            cmd_str = ' '.join(info.cmdline)
                            process_str = f"{info.pid:<7} {info.ppid:<7} {info.username:<8} {cpu_percent:5.1f} {mem_percent:5.1f} {info.get_cpu_graph()} {info.get_mem_graph()} {info.create_time:>8} {cmd_str}"
                            if line - self.scroll_position >= height:
                                break
                            if line >= self.scroll_position:
                                self.stdscr.addnstr(line - self.scroll_position, 4, process_str, width - 5)
                            line += 1

                line += 1

        self.stdscr.refresh()

    def export_data(self):
        data = {
            "timestamp": time.time(),
            "sessions": {}
        }
        for session_name, windows in self.sessions.items():
            data["sessions"][session_name] = {}
            for window_name, panes in windows.items():
                data["sessions"][session_name][window_name] = []
                for pane_index, pid in panes:
                    pane_data = {
                        "pane_index": pane_index,
                        "processes": []
                    }
                    processes = get_process_tree(pid)
                    for process in processes:
                        info = self.process_cache.get(process.pid)
                        if info:
                            pane_data["processes"].append({
                                "pid": info.pid,
                                "ppid": info.ppid,
                                "username": info.username,
                                "cpu_percent": info.cpu_history[-1] if info.cpu_history else 0,
                                "mem_percent": info.mem_history[-1] if info.mem_history else 0,
                                "create_time": info.create_time,
                                "cmdline": info.cmdline
                            })
                    data["sessions"][session_name][window_name].append(pane_data)
        
        with open("tmuxtop_export.json", "w") as f:
            json.dump(data, f, indent=2)
        
        self.stdscr.addstr(0, 0, "Data exported to tmuxtop_export.json", curses.A_REVERSE)
        self.stdscr.refresh()
        time.sleep(2)

    def backup_sessions(self):
        try:
            subprocess.run(["tmux", "list-sessions"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            self.stdscr.addstr(0, 0, "No tmux sessions to backup", curses.A_REVERSE)
            self.stdscr.refresh()
            time.sleep(2)
            return

        backup_file = f"tmux_backup_{int(time.time())}.sh"
        with open(backup_file, "w") as f:
            f.write("#!/bin/bash\n\n")
            f.write("# Tmux session backup created by TmuxTop\n\n")
            
            for session_name in self.sessions:
                f.write(f"tmux new-session -d -s {session_name}\n")
                
                for window_name, panes in self.sessions[session_name].items():
                    window_index, window_name = window_name.split(':', 1)
                    f.write(f"tmux rename-window -t {session_name}:{window_index} '{window_name}'\n")
                    
                    for i, (pane_index, pid) in enumerate(panes):
                        if i > 0:
                            f.write(f"tmux split-window -t {session_name}:{window_index}\n")
                        f.write(f"tmux send-keys -t {session_name}:{window_index}.{pane_index} 'cd {os.getcwd()}' C-m\n")
                        
                        processes = get_process_tree(pid)
                        if processes:
                            cmd = ' '.join(processes[0].cmdline())
                            f.write(f"tmux send-keys -t {session_name}:{window_index}.{pane_index} '{cmd}' C-m\n")
        
        os.chmod(backup_file, 0o755)
        self.stdscr.addstr(0, 0, f"Sessions backed up to {backup_file}", curses.A_REVERSE)
        self.stdscr.refresh()
        time.sleep(2)

    def restore_sessions(self):
        backup_files = [f for f in os.listdir() if f.startswith("tmux_backup_") and f.endswith(".sh")]
        if not backup_files:
            self.stdscr.addstr(0, 0, "No backup files found", curses.A_REVERSE)
            self.stdscr.refresh()
            time.sleep(2)
            return

        latest_backup = max(backup_files, key=os.path.getctime)
        try:
            subprocess.run(["bash", latest_backup], check=True)
            self.stdscr.addstr(0, 0, f"Sessions restored from {latest_backup}", curses.A_REVERSE)
        except subprocess.CalledProcessError:
            self.stdscr.addstr(0, 0, f"Failed to restore sessions from {latest_backup}", curses.A_REVERSE)
        
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
            elif key == ord('e'):
                self.export_data()
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
    parser.add_argument("--export", action="store_true", help="Export data to JSON file")
    parser.add_argument("--backup", action="store_true", help="Backup tmux sessions")
    parser.add_argument("--restore", action="store_true", help="Restore tmux sessions")
    args = parser.parse_args()

    if args.export:
        tmux_top = TmuxTop(None)
        tmux_top.update_data()
        tmux_top.export_data()
        print("Data exported to tmuxtop_export.json")
    elif args.backup:
        tmux_top = TmuxTop(None)
        tmux_top.update_data()
        tmux_top.backup_sessions()
        print("Sessions backed up")
    elif args.restore:
        TmuxTop(None).restore_sessions()
        print("Sessions restored")
    else:
        curses.wrapper(main)
