import os
import subprocess


class Git(object):
    """
    封装了对 git 的常用操作
    """
    def __init__(self, working_dir: str):
        """
        working_dir 是用来工作的目录，可以是相对路径也可以是绝对路径
        :param working_dir:
        """
        self.dir_hist = []
        self.working_dir = os.path.abspath(working_dir)
        if not os.path.exists(self.working_dir):
            subprocess.call([
                "mkdir",
                "-p",
                self.working_dir
            ])
            self.ch_to(self.working_dir)
            self.init()
            self.ch_back()

        self.repo_name = ""
        self.dir_hist = []

    @staticmethod
    def init():
        call_git("init")

    def ch_to(self, d: str = ""):
        """
        将工作目录切换到 d 指定的路径，d 是指 working_dir 中的子目录,
        如果不传递，则说明切换到 working_dir
        :param d:
        :return:
        """
        self.dir_hist.append(os.path.abspath(os.path.curdir))
        os.chdir(os.path.join(self.working_dir, d))

    def next_dir(self, n: str):
        """
        获取位于当前 working_dir 的子目录，但不进入具体目录
        :param n:
        :return:
        """
        return os.path.join(self.working_dir, n)

    def ch_back(self):
        if len(self.dir_hist) == 0:
            return

        back_to = self.dir_hist.pop()
        os.chdir(back_to)

    def clone(self, from_repo: str, rename: str = ""):
        """
        从 from_repo 所在的地址，clone 一份代码到 working_dir 中
        :param from_repo:
        :param rename:
        :return:
        """
        self.repo_name = rename
        call_git(
            "clone",
            from_repo,
            rename
        )

    @staticmethod
    def checkout(branch: str):
        call_git(
            "checkout",
            branch
         )

    @staticmethod
    def pull():
        call_git(
            "pull"
        )

    @staticmethod
    def push():
        call_git(
            "push"
        )

    @staticmethod
    def commit(msg: str):
        call_git(
            "commit",
            "-am",
            msg
        )

    @staticmethod
    def submodule_add(module_path: str, name: str = "", branch: str = "") -> str:
        """
        创建子模块，如果没传递名称，则会尝试从 path 中解析出名称，然后返回给使用者
        """
        # 已存在该模块，则不再 add, 而是等待下一步 update
        if os.path.exists(name):
            return name

        git_args = ["submodule", "add"]
        if branch:
            git_args.append("-b")
            git_args.append(branch)
        git_args.append(module_path)
        if name:
            git_args.append(name)
        call_git(*git_args)
        return name

    @staticmethod
    def submodule_update(recur: bool = False, remote: bool = False, path: str = ""):
        """
        更新子模块，recur 对应 recursive,
        path 用于指定要更新的库
        """
        git_args = ["submodule", "update", "--init"]
        if remote:
            git_args.append("--remote")
        if recur:
            git_args.append("--recursive")
        if path:
            git_args.append("--")
            git_args.append(path)
        call_git(*git_args)


def call_git(*args: str):
    """
    对 git 命令函调用的简单封装
    :param args:
    :return:
    """
    try:
        subprocess.call(["git"] + list(args))
    except FileNotFoundError as fe:
        print("调用 git 命令出错")
        raise fe
