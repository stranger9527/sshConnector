import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import paramiko
import threading
import time
import re


class SSHClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH 客户端 小马版v1.0")
        self.root.geometry("800x600")

        # 连接状态变量
        self.connected = False
        self.ssh_client = None
        self.channel = None
        self.stop_event = threading.Event()
        self.microcom_active = False

        # 创建UI
        self.create_widgets()
        self.set_default_values()

    def create_widgets(self):
        # 连接参数框架
        param_frame = tk.LabelFrame(self.root, text="SSH 连接参数")
        param_frame.pack(fill="x", padx=10, pady=5)

        # 主机名
        tk.Label(param_frame, text="主机名:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.host_entry = tk.Entry(param_frame, width=25)
        self.host_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # 端口
        tk.Label(param_frame, text="端口:").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        self.port_entry = tk.Entry(param_frame, width=10)
        self.port_entry.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # 用户名
        tk.Label(param_frame, text="用户名:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.user_entry = tk.Entry(param_frame, width=25)
        self.user_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # 密码
        tk.Label(param_frame, text="密码:").grid(row=1, column=2, sticky="e", padx=5, pady=2)
        self.pass_entry = tk.Entry(param_frame, width=25, show="*")
        self.pass_entry.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        # 命令框架
        cmd_frame = tk.LabelFrame(self.root, text="执行命令")
        cmd_frame.pack(fill="x", padx=10, pady=5)

        self.cmd_text = ScrolledText(cmd_frame, height=8)
        self.cmd_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 按钮框架
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)

        self.connect_btn = tk.Button(btn_frame, text="连接并执行", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=5)

        self.clear_btn = tk.Button(btn_frame, text="清空输出", command=self.clear_output)
        self.clear_btn.pack(side="left", padx=5)

        # AT命令按钮
        at_btn_frame = tk.Frame(btn_frame)
        at_btn_frame.pack(side="left", padx=20)

        tk.Label(at_btn_frame, text="AT命令:").pack(side="left")
        self.at1_btn = tk.Button(at_btn_frame, text="servingcell",
                                 command=lambda: self.send_at_command("at+qeng=\"servingcell\""))
        self.at1_btn.pack(side="left", padx=2)
        self.at1_btn.config(state="disabled")

        self.at2_btn = tk.Button(at_btn_frame, text="cpin?", command=lambda: self.send_at_command("at+cpin?"))
        self.at2_btn.pack(side="left", padx=2)
        self.at2_btn.config(state="disabled")

        self.exit_btn = tk.Button(at_btn_frame, text="退出会话", command=self.exit_microcom)
        self.exit_btn.pack(side="left", padx=5)
        self.exit_btn.config(state="disabled")

        # 输出框架
        output_frame = tk.LabelFrame(self.root, text="命令输出")
        output_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.output_text = ScrolledText(output_frame, state="normal")
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("状态: 未连接")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_default_values(self):
        self.host_entry.insert(0, "192.168.1.17")
        self.port_entry.insert(0, "9011")
        self.user_entry.insert(0, "root")
        self.pass_entry.insert(0, "HIK@root1988F~")

        default_cmds = [
            "cd /mnt/emmc1/log",
            "dbgCli McuComm setLog 0",
            "dbgCli SystemServ version",
            "tail /mnt/emmc1/log/McuComm.info | grep batt_volt",
            "microcom /dev/ttyUSB13"

        ]
        self.cmd_text.insert("1.0", "\n".join(default_cmds))

    def toggle_connection(self):
        if self.connected:
            self.disconnect()
        else:
            self.connect_and_execute()

    def connect_and_execute(self):
        host = self.host_entry.get()
        port = int(self.port_entry.get())
        user = self.user_entry.get()
        password = self.pass_entry.get()

        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(host, port, user, password, timeout=10)

            self.connected = True
            self.connect_btn.config(text="断开连接")
            self.status_var.set(f"状态: 已连接 ({host}:{port})")

            # 获取并执行命令
            commands = self.cmd_text.get("1.0", tk.END).strip().split('\n')

            # 创建线程执行命令
            self.stop_event.clear()
            thread = threading.Thread(
                target=self.execute_commands,
                args=(commands,),
                daemon=True
            )
            thread.start()

        except Exception as e:
            self.output(f"连接错误: {str(e)}")
            self.status_var.set(f"状态: 连接失败 - {str(e)}")
            if self.ssh_client:
                self.ssh_client.close()

    def execute_commands(self, commands):
        try:
            # 执行所有非交互式命令
            for cmd in commands:
                if self.stop_event.is_set():
                    break

                # 跳过microcom命令，后面单独处理
                if "microcom" in cmd:
                    continue

                self.output(f"$ {cmd}")
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()

                if output:
                    self.output(output)
                if error:
                    self.output(f"错误: {error}")

            # 处理microcom交互式会话
            microcom_cmd = next((cmd for cmd in commands if "microcom" in cmd), None)
            if microcom_cmd and not self.stop_event.is_set():
                self.output(f"$ {microcom_cmd}")
                self.output("进入microcom交互模式，请使用上方按钮发送AT命令")

                # 创建交互式shell通道
                transport = self.ssh_client.get_transport()
                self.channel = transport.open_session()
                self.channel.get_pty()
                self.channel.exec_command(microcom_cmd)

                # 启用AT命令按钮
                self.at1_btn.config(state="normal")
                self.at2_btn.config(state="normal")
                self.exit_btn.config(state="normal")
                self.microcom_active = True

                # 实时读取输出
                while not self.stop_event.is_set() and self.microcom_active:
                    if self.channel.recv_ready():
                        data = self.channel.recv(1024).decode()
                        self.output(data, end="")
                    time.sleep(0.1)

                self.at1_btn.config(state="disabled")
                self.at2_btn.config(state="disabled")
                self.exit_btn.config(state="disabled")

            # 执行最后的命令
            # if not self.stop_event.is_set():
            #     self.output("$ dbgCli SystemServ version")
            #     stdin, stdout, stderr = self.ssh_client.exec_command("dbgCli SystemServ version", timeout=10)
            #     output = stdout.read().decode().strip()
            #     self.output(output)

        except Exception as e:
            self.output(f"命令执行错误: {str(e)}")

    def send_at_command(self, command):
        if self.channel and self.microcom_active:
            # 发送AT命令并添加回车
            self.channel.send(command + "\r\n")
            self.output(f"发送: {command}")

    def exit_microcom(self):
        if self.channel and self.microcom_active:
            # 发送Ctrl+C (ASCII 3)
            self.channel.send("\x03")
            self.output("已发送Ctrl+C退出microcom会话")
            self.microcom_active = False

    def disconnect(self):
        self.stop_event.set()
        self.connected = False
        self.connect_btn.config(text="连接并执行")
        self.status_var.set("状态: 已断开")

        if self.microcom_active:
            self.exit_microcom()

        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

    def output(self, text, end="\n"):
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, text + end)
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")

    def clear_output(self):
        self.output_text.config(state="normal")
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state="disabled")

    def on_closing(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SSHClientApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()