def upper_first_character(s: str) -> str:
    """
    将第一个字符转为大写
    :param s:
    :return:
    """
    if len(s) == 0:
        return s
    if len(s) == 1:
        return s.upper()

    return s[0].upper() + s[1:]


def split_by_upper_character(s: str, splitter: str = '') -> str:
    if len(s) == 0:
        return s

    segment = []
    sub_seg = []
    prev_i = 0
    for (i, c) in enumerate(s):
        if not c.isupper():
            continue

        sub_seg.append(s[prev_i: i])
        prev_i = i + 1
        segment.append("".join(sub_seg))
        sub_seg = [s[i]]

    # if prev_i != len(s):
    if len(sub_seg) == 1:
        segment.append(sub_seg[0] + s[prev_i:])

    # 合并大写单字
    i = 0
    new_segment = []
    seg_len = len(segment)
    while i < seg_len:
        j = i
        while j < seg_len and segment[j].isupper() and (
                ((j + 1) < seg_len and len(segment[j+1]) == 1 and segment[j + 1].isupper()) or
                (j + 1 == seg_len and len(segment[j]) == 1)
        ):
            j += 1
        if j != i:
            new_segment.append("".join(segment[i:j + 1]))
            i = j + 1
        else:
            new_segment.append(segment[i])
            i += 1

    return splitter.join([s for s in new_segment if s])


def upper_first_by_splitter(s: str, splitter: str) -> str:
    """
    按照 splitter 分割，然后首字母大写
    :param s:
    :param splitter:
    :return:
    """
    if not s:
        return s

    return "".join(map(upper_first_character, s.split(splitter)))


def pretty_name(s: str) -> str:
    """
    将用 _ 分隔的名称转换为驼峰式
    """
    msg = "".join(
        map(
            split_by_upper_character,
            map(upper_first_character, s.split("_"))
        )
    )

    return msg
