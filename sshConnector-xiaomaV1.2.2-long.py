import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import paramiko
import threading
import time
import re
import openpyxl
from datetime import datetime


class SSHClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH 客户端 小马版v1.2-一小时版")
        self.root.geometry("800x700")

        # 连接状态变量
        self.count = 0
        self.connected = False
        self.ssh_client = None
        self.channel = None
        self.stop_event = threading.Event()
        self.microcom_active = False
        self.at_thread = None
        self.current_date = datetime.now().strftime("%Y%m%d")
        self.current_month = datetime.now().strftime("%Y%m")
        self.current_year = datetime.now().strftime("%Y")
        self.current_hour = datetime.now().strftime("%H")
        self.current_minute = datetime.now().strftime("%M")
        self.current_second = datetime.now().strftime("%S")



        # 数据收集变量
        self.log_data = ""
        self.batt_volt = None
        self.lithium_batt_volt = None
        self.signal_abnormal_count = 0
        self.video_storage_status = "正常"
        self.memory_usage = None
        self.signal_strengths = []
        self.ip_address = "未获取"
        self.total_memory = None
        self.used_memory = None
        self.device_id = "unknown"  # 设备ID默认值

        # 创建UI
        self.create_widgets()
        self.set_default_values()

    def create_widgets(self):
        # 连接参数框架
        param_frame = tk.LabelFrame(self.root, text="SSH 连接参数")
        param_frame.pack(fill="x", padx=10, pady=5)

        # 设备ID - 新增
        tk.Label(param_frame, text="设备ID:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.id_entry = tk.Entry(param_frame, width=15)
        self.id_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.id_entry.insert(0, "0001")  # 默认设备ID

        # 主机名
        tk.Label(param_frame, text="主机名:").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        self.host_entry = tk.Entry(param_frame, width=25)
        self.host_entry.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # 端口
        tk.Label(param_frame, text="端口:").grid(row=0, column=4, sticky="e", padx=5, pady=2)
        self.port_entry = tk.Entry(param_frame, width=10)
        self.port_entry.grid(row=0, column=5, sticky="w", padx=5, pady=2)

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

        self.export_btn = tk.Button(btn_frame, text="导出结果", command=self.export_results)
        self.export_btn.pack(side="left", padx=5)
        self.export_btn.config(state="disabled")

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
            "cd /mnt/sda2/video/" + self.current_year + "/" + self.current_month + "/" + self.current_date + " && ls -lr | grep total",
            "dbgCli McuComm setLog 0",
            "dbgCli SystemServ version",
            "tail /mnt/emmc1/log/McuComm.info | grep batt_volt",
            "free",
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
        self.device_id = self.id_entry.get().strip() or "unknown"  # 获取设备ID

        # 重置数据收集
        self.log_data = ""
        self.batt_volt = None
        self.lithium_batt_volt = None
        self.signal_abnormal_count = 0
        self.video_storage_status = "正常"
        self.memory_usage = None
        self.signal_strengths = []
        self.ip_address = "未获取"
        self.total_memory = None
        self.used_memory = None
        self.export_btn.config(state="disabled")

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
                    self.parse_output(cmd, output)
                if error:
                    self.output(f"错误: {error}")
                    # 保证无视频文件目录的错误被捕捉
                    if "ls" in cmd:
                        self.video_storage_status = "不正常"

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
                        data = self.channel.recv(1024).decode(errors="ignore")
                        self.output(data, end="")
                        self.parse_at_output(data)
                    time.sleep(0.1)

        except Exception as e:
            self.output(f"命令执行错误: {str(e)}")
        finally:
            self.microcom_active = False
            self.export_btn.config(state="normal")
            self.output("命令执行完成，可以导出结果")

    def parse_output(self, cmd, output):
        """解析命令输出并提取数据"""
        # 解析电池电压
        if "batt_volt" in output and "lithium_Batt_volt" in output:
            matches = re.findall(r'batt_volt:\s*(\d+)\s*lithium_Batt_volt:\s*(\d+)', output)
            if matches:
                self.batt_volt = matches[-1][0]  # 取最后一个值
                self.lithium_batt_volt = matches[-1][1]

        # 解析视频存储状态
        if cmd == "cd /mnt/sda2/video/" + self.current_year + "/" + self.current_month + "/" + self.current_date + " && ls -lr | grep total":
            lines = output.splitlines()
            if lines:
                total_line = lines[0]
                self.output(total_line)
                if "total" in total_line:
                    total_value = total_line.split()[1]
                    self.video_storage_status = "正常" if total_value != "0" else "不正常"

        # 解析内存使用情况
        if cmd == "free":
            # 示例输出:
            #              total       used       free     shared    buffers     cached
            # Mem:        499592     180112     319480          0      24636      74304
            # -/+ buffers/cache:      81172     418420
            # Swap:            0          0          0

            # 解析内存信息
            mem_lines = output.splitlines()
            if len(mem_lines) >= 2:
                try:
                    # 提取内存总量和已用量
                    mem_line = mem_lines[1]
                    if "Mem:" in mem_line:
                        parts = mem_line.split()
                        if len(parts) >= 4:
                            self.total_memory = int(parts[1])
                            self.used_memory = int(parts[2])

                            # 计算内存使用率
                            if self.total_memory > 0:
                                self.memory_usage = round(self.used_memory / self.total_memory * 100, 2)
                except (ValueError, IndexError):
                    pass

        # 解析IP地址
        if "inet addr:" in output:
            # 查找第一个inet addr:后的IP地址
            ip_matches = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', output)
            if ip_matches:
                # 优先选择192.168开头的地址
                for ip in ip_matches:
                    if ip.startswith("192.168"):
                        self.ip_address = ip
                        break
                else:
                    # 如果没有192.168开头的地址，则取第一个
                    self.ip_address = ip_matches[0]

    def parse_at_output(self, data):
        """解析AT命令输出并提取信号强度"""
        # 解析信号强度
        lines = data.splitlines()
        for line in lines:
            if '+QENG: "servingcell"' in line:
                parts = line.split(',')
                if len(parts) >= 15:
                    try:
                        # 倒数第五位是信号强度
                        signal_strength = int(parts[-5].strip())
                        self.signal_strengths.append(signal_strength)

                        # 统计异常数量（小于-95）
                        if signal_strength < -95:
                            self.signal_abnormal_count += 1
                    except (ValueError, IndexError):
                        pass

    def send_at_commands_periodically(self):
        """每10秒发送一次AT命令，持续60分钟（120次）"""
        count = 0
        # max_count = 120  # 10分钟 = 120 * 5秒
        max_count = 360  # 60分钟 = 360 * 10秒

        while count < max_count and not self.stop_event.is_set():
            try:
                if self.channel:
                    # 记录精确发送时间
                    send_time = time.strftime('%H:%M:%S')

                    # 发送AT命令（增加命令间间隔）
                    self.channel.send('ate1\r')  # 确保回显开启
                    time.sleep(0.2)
                    self.channel.send('at+qeng="servingcell"\r')
                    time.sleep(0.3)
                    self.channel.send('at+cpin?\r')

                    self.output(f"[{send_time}] 发送AT命令")
                    count += 1
                    self.status_var.set(f"状态: AT命令发送中 ({count}/{max_count})")

                    # 精确等待10秒（包含已用时间）
                    start_wait = time.time()
                    while (time.time() - start_wait) < 10.0:
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.5)
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
        self.log_data += text + end
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, text + end)
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")

    def clear_output(self):
        self.log_data = ""
        self.output_text.config(state="normal")
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state="disabled")

    def export_results(self):
        """导出结果到Excel和文本文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 在文件名中包含设备ID
        txt_filename = f"ssh_log_{self.device_id}_{timestamp}.txt"
        excel_filename = f"device_status_{self.device_id}_{timestamp}.xlsx"

        # 确保文件名有效
        txt_filename = self.sanitize_filename(txt_filename)
        excel_filename = self.sanitize_filename(excel_filename)

        # 保存文本日志
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(self.log_data)

        # 创建Excel文件
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "设备状态"

        # 添加表头
        headers = ["参数", "值", "说明"]
        ws.append(headers)

        # 添加数据行
        data_rows = [
            ["设备ID", self.device_id, "设备标识符"],
            ["IP地址", self.ip_address, "设备IP地址"],
            ["供电电压 (mV)", int(self.batt_volt) / 100 if self.batt_volt is not None else "N/A", "从日志中提取的batt_volt值"],
            ["电池电压 (mV)", int(self.lithium_batt_volt) / 100 if self.lithium_batt_volt is not None else "N/A", "从日志中提取的lithium_Batt_volt值"],
            ["信号强度异常数量", self.signal_abnormal_count, "信号强度小于-95的数量"],
            ["信号强度异常占比(%)", int(self.signal_abnormal_count) / len(self.signal_strengths) * 100, "信号强度小于-95的数据数量占总样本数的比例"],
            ["视频存储状态", self.video_storage_status, "total值不为0表示正常"],
            ["内存使用率 (%)", self.memory_usage if self.memory_usage is not None else "N/A", "已使用内存占比"],
            ["信号强度样本数", len(self.signal_strengths), "收集到的信号强度样本总数"]
        ]

        for row in data_rows:
            ws.append(row)

        # 添加信号强度详情
        if self.signal_strengths:
            ws.append([])
            ws.append(["信号强度详情", "", ""])
            ws.append(["时间", "信号强度", "是否异常"])
            self.current_hour = datetime.now().strftime("%H")
            self.current_minute = datetime.now().strftime("%M")
            self.current_second = datetime.now().strftime("%S")

            # 为每个信号强度添加一行
            for i, strength in enumerate(self.signal_strengths):
                # 模拟时间戳（每5秒一次）
                hours = int(self.current_hour)
                minutes = int(self.current_minute) + i // 6  # 每5秒一次，12次为一分钟
                seconds = int(self.current_second) + (i % 6) * 10
                if seconds >= 60:
                    seconds = seconds % 60
                    minutes += 1
                if minutes >= 60:
                    minutes = minutes % 60
                    hours += 1
                if hours >= 24:
                    hours = 0
                time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                ws.append([time_str, strength, "是" if strength < -95 else "否"])

        # 保存Excel文件
        wb.save(excel_filename)

        self.output(f"结果已导出到文件: {txt_filename} 和 {excel_filename}")
        self.output(f"设备ID: {self.device_id}")
        self.output(f"Excel文件包含{len(data_rows)}个主要参数和{len(self.signal_strengths)}个信号强度样本")
        self.output(f"IP地址: {self.ip_address}")
        self.output(f"信号强度异常数量: {self.signal_abnormal_count}")

    def sanitize_filename(self, filename):
        """确保文件名有效，移除非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def on_closing(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SSHClientApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()