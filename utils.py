# Ref: https://github.com/kaito-kidd/douban-group-spider/blob/0bc44886dfdd742b176f77bb2d5e6476cf515642/utils.py

import random
import time


class ProxyManager(object):
    """代理管理器
    """

    def __init__(self, proxies_or_path, interval_per_ip=0, is_single=False):
        '''
        @proxies_or_path, str or list, 代理path或列表
        @interval_per_ip, int, 每个ip调用最小间隔
        @is_single, bool, 是否启用单点代理,例如使用squid
        '''
        self.proxies_or_path = proxies_or_path
        self.host_time_map = {}
        self.interval = interval_per_ip
        self.is_single = is_single
        self.init_proxies(self.proxies_or_path)

    def init_proxies(self, proxies_or_path):
        '''初始化代理列表
        @proxies_or_path, list or str
        '''
        if isinstance(proxies_or_path, str):
            if self.is_single:
                self.proxies = proxies_or_path
            else:
                with open(proxies_or_path) as f:
                    self.proxies = f.readlines()
        else:
            self.proxies = proxies_or_path

    def reload_proxies(self):
        '''重新加载代理，proxies_or_path必须是文件路径
        '''
        if not isinstance(self.proxies_or_path, str):
            raise TypeError("proxies_or_path type is invalid!")
        if self.is_single:
            raise TypeError("is_single must be False!")
        with open(self.proxies_or_path) as f:
            self.proxies = f.readlines()
        print("reload %s proxies ...", len(self.proxies))

    def get_proxy(self):
        '''获取一个可用代理
        如果代理使用过于频繁会阻塞，以防止服务器屏蔽
        '''
        # 如果使用单点代理,直接返回
        if self.is_single:
            return self.proxies
        proxy = self.proxies[random.randint(0, len(self.proxies) - 1)].strip()
        host, _ = proxy.split(':')
        latest_time = self.host_time_map.get(host, 0)
        interval = time.time() - latest_time
        if interval < self.interval:
            print("%s waiting", proxy)
            time.sleep(self.interval)
        self.host_time_map[host] = time.time()
        return proxy.strip()