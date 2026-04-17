#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 汕头大学校园网自动认证守护进程
# 专门解决午夜清除cookie导致的断网问题

import re
import sys
import time
import math
import subprocess
import requests
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class StuNetworkDaemon:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
        # 汕头大学配置
        self.test_url = "http://1.1.1.2"
        self.stu_dns = "202.192.240.87"
        self.other_dns = "223.5.5.5"
        
        # 认证信息
        self.auth_url = None
        self.referer = None
        self.origin = None
        
        # 认证过程中不要走系统代理
        self.proxies = {'http': None, 'https': None}
        
        # 检测间隔（秒）
        self.check_interval = 60
        
    def _ping(self, host):
        """利用 ping 判断网络状态"""
        if sys.platform.lower() == "win32":
            cmd = f"ping -n 2 -w 1000 {host}"
            creation_flags = subprocess.CREATE_NO_WINDOW
        else:
            cmd = f"ping -c 2 -W 1 {host}"
            creation_flags = 0
        
        args = cmd.split(' ')
        th = subprocess.Popen(args, stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL, creationflags=creation_flags)
        return (th.wait() == 0)

    def _check_status(self):
        """检测网络状态"""
        return self._ping(self.stu_dns) or self._ping(self.other_dns)

    def _get_auth_info(self):
        """获取认证信息"""
        try:
            response = requests.get(self.test_url, proxies=self.proxies, verify=False)
            response.encoding = 'utf8'
            
            # 获取跳转链接
            href = re.findall(r"href='(.+)'", response.text)
            if href:
                self.referer = href[0]
                self.origin = self.referer.split("/ac_portal/")[0]
                self.auth_url = self.origin + "/ac_portal/login.php"
            else:
                # 使用已知的认证页面
                self.referer = "https://a.stu.edu.cn/ac_portal/20170602150308/pc.html"
                self.origin = "https://a.stu.edu.cn"
                self.auth_url = self.origin + "/ac_portal/login.php"
                
            return True
        except Exception as e:
            self._log(f"获取认证信息失败: {e}")
            return False

    def _authenticate(self):
        """执行认证"""
        if self.auth_url is None:
            if not self._get_auth_info():
                return False

        # 汕头大学锐捷系统认证数据
        data = {
            "opr": "pwdLogin",
            "userName": self.username,
            "pwd": self.password,
            "ipv4or6": "",
            "rememberPwd": "1"
        }

        # 请求头 - 基于实际抓包信息
        headers = {
            "Host": "a.stu.edu.cn",
            "Origin": "https://a.stu.edu.cn",
            "Referer": "https://a.stu.edu.cn/ac_portal/20170602150308/pc.html?template=20170602150308&tabs=pwd&vlanid=0&_ID_=0&switch_url=&url=",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Priority": "u=1, i",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }

        try:
            response = requests.post(self.auth_url, data=data, headers=headers, proxies=self.proxies, verify=False)
            response.encoding = response.apparent_encoding
            
            # 调试：打印响应状态和内容
            self._log(f"响应状态码: {response.status_code}")
            self._log(f"响应内容类型: {response.headers.get('content-type', 'unknown')}")
            
            # 尝试解析JSON，如果失败则手动处理JSON字符串
            response_text = response.text.strip()
            
            # 检查响应内容是否包含JSON格式
            if response_text.startswith('{') and response_text.endswith('}'):
                try:
                    # 手动解析JSON（处理单引号问题）
                    import json
                    # 将单引号替换为双引号
                    json_text = response_text.replace("'", '"')
                    result = json.loads(json_text)
                    
                    if result.get("success"):
                        self._log(f"认证成功: {result.get('msg', '')}")
                        return True
                    else:
                        self._log(f"认证失败: {result.get('msg', '')}")
                        return False
                except Exception as json_error:
                    self._log(f"JSON解析失败: {json_error}")
                    self._log(f"原始响应: {response_text}")
                    return False
            else:
                # 如果不是JSON格式
                self._log(f"响应内容不是JSON: {response_text[:200]}...")
                return False
                
        except Exception as e:
            self._log(f"认证请求失败: {e}")
            return False

    def _log(self, message):
        """日志记录"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{timestamp}] {message}")

    def run(self):
        """主循环"""
        self._log("汕头大学校园网自动认证守护进程启动")
        self._log(f"用户名: {self.username}")
        self._log(f"检测间隔: {self.check_interval}秒")
        
        while True:
            try:
                # 检测网络状态
                network_status = self._check_status()
                
                if not network_status:
                    self._log("网络断开，尝试重新认证")
                    if self._authenticate():
                        self._log("认证成功，网络已恢复")
                    else:
                        self._log("认证失败，等待下次检测")
                else:
                    self._log("网络正常")
                
                # 等待下次检测
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self._log("用户中断，程序退出")
                break
            except Exception as e:
                self._log(f"运行异常: {e}")
                time.sleep(self.check_interval)


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python StuNetworkDaemon.py 配置文件")
        print("配置文件格式:")
        print("第一行: 校园网账号")
        print("第二行: 校园网密码")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            username = f.readline().strip()
            password = f.readline().strip()
            
        if not username or not password:
            print("错误: 配置文件中账号或密码为空")
            sys.exit(1)
            
        daemon = StuNetworkDaemon(username, password)
        daemon.run()
        
    except FileNotFoundError:
        print(f"错误: 配置文件 {config_file} 不存在")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()