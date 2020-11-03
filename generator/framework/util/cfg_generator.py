class HasIdent(object):
    """
    避免 CfgGenerator 交叉引用所使用的基类
    """
    def __init__(self, ident: int = 0):
        self.ident = ident

    def increase_ident(self):
        self.ident += 1

    def decrease_ident(self):
        self.ident -= 1


class CfgGeneratorIdent(object):
    def __init__(self, gen: HasIdent):
        self.gen = gen

    def __enter__(self):
        self.gen.increase_ident()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.gen.decrease_ident()


class CfgGenerator(HasIdent):

    def __init__(self, step: int = 4):
        super(CfgGenerator, self).__init__()
        self.step = step
        self.conf = []

    def to_cfg_string(self):
        """
        获取生成好的配置信息
        :return:
        """
        return "".join(self.conf)

    def with_ident(self):
        """
        返回一个保存了递进状态的资源对象, 用于 with 语句
        :return:
        """
        return CfgGeneratorIdent(self)

    def increase_ident(self, ident: int = 1):
        """
        手动增加或减少递进状态
        :param ident:
        :return:
        """
        self.ident += ident

    def append_with(self, conf: str = "", new_line: bool = True, with_ident: bool = True):
        """
        添加配置信息，传递了 new_line 或 ident 参数时可为其添加 ident 及新行
        :param conf:
        :param new_line:
        :param with_ident:
        :return:
        """
        ident = "" if not with_ident else self.ident_str()
        if str:
            self.conf.append("%s%s" % (ident, conf))

        if new_line:
            self.conf.append("\n")

    def ident_str(self):
        return self.ident * self.step * " "

    def str_with_ident(self, s) -> str:
        """
        使用当前的缩进来创建字符串
        """
        return "%s%s" % (self.ident_str(), s)
