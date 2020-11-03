# config: utf8

import importlib
import os
import sys

from ... import config
from .module_scanner import ModuleScanner


class DirScanner(object):
    """
    扫描指定的目录，得到所有的服务元数据, 该目录一般是对应项目的根目录
    """

    def __init__(self, target_dir):
        self.cur_dir = os.path.abspath(os.curdir)
        self.target_dir = target_dir
        sys.path.append(target_dir)
        os.chdir(target_dir)

    def gather(self):
        """
        获取目标目录下的复合条件的所有类型
        :return:
        """
        target_dir = self.target_dir
        if config.outside_server:
            # 如果是生成独立项目，则需要在扫描时进入该子目录，扫描完成后退出来
            target_dir = os.path.join(config.outside_server_path, config.source_project_name)
        self.scan_file(target_dir, "")
        if config.outside_server:
            os.chdir(self.target_dir)
        return ModuleScanner().gather()

    def scan_file(self, target_dir, rel_path):
        """
        :param target_dir:
        :param rel_path
        :return:
        """

        # if os.path.exists(os.path.join(target_dir, "__init__.py")):
        #     self.import_file(rel_path, "")

        for entry in os.scandir(target_dir):
            if entry.is_file() and entry.name.endswith(".py"):
                self.import_file(rel_path, entry.name[:-3])
            elif entry.is_dir():
                # only python package dir
                next_dir = os.path.join(target_dir, entry.name)
                if not os.path.exists(os.path.join(next_dir, "__init__.py")):
                    continue

                # import the package first
                self.import_file(rel_path, entry.name)
                # then get into deeper
                self.scan_file(
                    next_dir,
                    ".".join(rel_path and [rel_path, entry.name] or [entry.name]))

    @staticmethod
    def import_file(target_dir: str, target_file: str):
        path_elem = target_dir and [target_dir, target_file] or [target_file]
        path = ".".join(path_elem)
        try:
            importlib.import_module(path)
        except Exception as e:
            if "_tkinter" not in str(e):
                print(("导入文件 %s 出错，错误信息为: %s" % (path, str(e))))

    def __del__(self):
        # sys.path.remove(self.cur_dir)
        # os.chdir(self.cur_dir)
        pass
