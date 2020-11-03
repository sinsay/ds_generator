import os


def mkdir_without_exception(target):
    try:
        # subprocess.call([
        #     "mkdir",
        #     "-p",
        #     target
        # ])
        os.makedirs(target, exist_ok=True)
    except FileExistsError:
        print("the directory %s already exists. continue the next gen phase." % target)
