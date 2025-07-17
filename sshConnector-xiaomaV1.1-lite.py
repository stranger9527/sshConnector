import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import paramiko
import threading
import time
import re


class SSHClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH 客户端 小马版v1.1-lite")
        self.root.geometry("800x800")

        # 连接状态变量
        self.count = 0
        self.connected = False
        self.ssh_client = None
        self.channel = None
        self.stop_event = threading.Event()
        self.microcom_active = False
        self.at_thread = None  # 用于控制AT命令发送的线程

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
            "cd /mnt/sda2/video/2025/202507/20250703 && ls -lr | grep total",
            "dbgCli McuComm setLog 0",
            "dbgCli SystemServ version",
            "tail /mnt/emmc1/log/McuComm.info | grep batt_volt",
            "printf '已使用内存占比:'",
            "free | awk 'NR==2{printf $3*100/$2}'",
            "ifconfig | grep 192",
            "rm -f /var/lock/LCK..ttyUSB13",
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
                # 创建交互式shell通道
                transport = self.ssh_client.get_transport()
                self.channel = transport.open_session()
                self.channel.get_pty()
                self.channel.exec_command(microcom_cmd)
                self.microcom_active = True

                # 启动单独的线程发送AT命令
                self.at_thread = threading.Thread(
                    target=self.send_at_commands_periodically,
                    daemon=True
                )
                self.at_thread.start()

                # 实时读取输出
                while not self.stop_event.is_set() and self.microcom_active:
                    if self.channel.recv_ready():
                        data = self.channel.recv(1024).decode()
                        self.output(data, end="")
                    time.sleep(0.1)

        except Exception as e:
            self.output(f"命令执行错误: {str(e)}")
        finally:
            self.microcom_active = False

    def send_at_commands_periodically(self):
        """每5秒发送一次AT命令，持续10分钟（120次）"""
        count = 0
        max_count = 120  # 10分钟 = 120 * 5秒

        while count < max_count and not self.stop_event.is_set():
            try:
                if self.channel:
                    # 发送AT命令
                    self.channel.send('at+qeng="servingcell"' + "\r\n")
                    self.channel.send('at+cpin?' + "\r\n")
                    self.output(f"[{time.strftime('%H:%M:%S')}] 发送AT命令")

                    count += 1
                    self.status_var.set(f"状态: AT命令发送中 ({count}/{max_count})")

                    # 等待5秒
                    for _ in range(50):  # 50 * 0.1秒 = 5秒
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.1)
            except Exception as e:
                self.output(f"发送AT命令错误: {str(e)}")
                break

        # 循环结束后设置状态
        if count >= max_count:
            self.status_var.set("状态: AT命令发送完成")
            self.output("AT命令发送完成，等待最后响应...")

            # 等待最后响应
            end_time = time.time() + 10  # 额外等待10秒
            while time.time() < end_time and not self.stop_event.is_set():
                time.sleep(0.1)

        # 退出microcom
        self.exit_microcom()

    def exit_microcom(self):
        if self.channel and self.microcom_active:
            try:
                # 发送Ctrl+C (ASCII 3)
                self.channel.send("\x03")
                self.output("已发送Ctrl+C退出microcom")
            except Exception as e:
                self.output(f"退出microcom错误: {str(e)}")
            finally:
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