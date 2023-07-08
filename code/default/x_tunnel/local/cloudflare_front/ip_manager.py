import os
import json
import socket

import utils

from front_base.ip_manager import IpManagerBase


class IpManager(IpManagerBase):
    def __init__(self, config, default_domain_fn, domain_fn, logger):
        super(IpManager, self).__init__(config, None, logger)
        self.default_domain_fn = default_domain_fn
        self.domain_fn = domain_fn

        self.domain_map = self.load_domains()
        # top_domain -> {}

    def load_domains(self):
        domain_map = {}  # top_domain -> {}
        for fn in [self.domain_fn, self.default_domain_fn]:
            if not os.path.isfile(fn):
                continue

            try:
                with open(fn, "r") as fd:
                    ds = json.load(fd)
                    for top in ds:
                        domain_map[str(top)] = {
                            "links": 0,
                            "fail_times": 0
                        }
                self.logger.info("load %s success", fn)
                break
            except Exception as e:
                self.logger.warn("load %s for host failed:%r", fn, e)
        return domain_map

    def save_domains(self, domains):
        ns = []
        for top_domain, _ in self.domain_map.items():
            ns.append(top_domain)

        if ns == domains:
            self.logger.debug("save domains not changed, ignore")
            return
        else:
            self.logger.info("save domains:%s", domains)

        dat = {}
        for domain in domains:
            dat[domain] = ["www." + domain]

        with open(self.domain_fn, "w") as fd:
            json.dump(dat, fd)

        self.domain_map = self.load_domains()

    def get_ip_sni_host(self):
        for top_domain, info in self.domain_map.items():
            if info["links"] > self.config.max_connection_per_domain:
                continue

            sni = "www." + top_domain
            try:
                ip = socket.gethostbyname(sni)
            except Exception as e:
                self.logger.debug("get ip for sni:%s failed:%r", sni, e)
                continue

            info["links"] += 1

            self.logger.debug("get ip:%s sni:%s", ip, sni)
            return ip, sni, top_domain

        return None, None, None

    def report_connect_fail(self, ip_str, sni=None, reason=""):
        ip, _ = utils.get_ip_port(ip_str)
        ip = utils.to_str(ip)
        top_domain = ".".join(sni.split(".")[1:])

        self.domain_map[top_domain]["fail_times"] += 1
        self.domain_map[top_domain]["links"] -= 1
        self.logger.debug("ip %s sni:%s connect fail, reason:%s", ip, sni, reason)

    def update_ip(self, ip_str, sni, handshake_time):
        ip, _ = utils.get_ip_port(ip_str)
        ip = utils.to_str(ip)
        top_domain = ".".join(sni.split(".")[1:])

        self.domain_map[top_domain]["fail_times"] = 0
        # self.logger.debug("ip %s sni:%s connect success, rtt:%f", ip, sni, handshake_time)

    def ssl_closed(self, ip_str, sni=None, reason=""):
        ip, _ = utils.get_ip_port(ip_str)
        ip = utils.to_str(ip)
        top_domain = ".".join(sni.split(".")[1:])

        try:
            self.domain_map[top_domain]["links"] -= 1
            self.logger.debug("ip %s sni:%s connect closed reason %s", ip, sni, reason)
        except Exception as e:
            self.logger.warn("ssl_closed %s sni:%s reason:%s except:%r", ip_str, sni, reason, e)