import datetime
import os


class FileInfo():
    """
    For displaying lists of files in project pages
    All attributes are human readable strings
    """
    def __init__(self, name, size, last_modified, description):
        self.name = name
        self.size = size
        self.last_modified= last_modified
        self.description = description


class DirectoryInfo():
     def __init__(self, name, size, last_modified, description):
        self.name = name
        self.size = size
        self.last_modified = last_modified
        self.description = description 


def get_file_info(file_path):
    "Given a file path, get the information used to display it"
    name = os.path.split(file_path)[-1]
    size = readable_size(os.path.getsize(file_path))
    last_modified = datetime.date.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d")
    description = ''
    return FileInfo(name, size, last_modified, description)

def get_directory_info(dir_path):
    "Given a directory path, get the information used to display it"
    name = os.path.split(dir_path)[-1]
    size = ''
    last_modified = datetime.date.fromtimestamp(os.path.getmtime(dir_path)).strftime("%Y-%m-%d")
    description = ''
    return DirectoryInfo(name, size, last_modified, description)

def get_tree_size(path):
    """Return total size of files in given path and subdirs."""
    total = 0
    for entry in os.scandir(path):
        if entry.is_dir(follow_symlinks=False):
            total += get_tree_size(entry.path)
        else:
            total += entry.stat(follow_symlinks=False).st_size
    return total

def readable_size(num, suffix='B'):
    "Display human readable size of byte number"
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024:
            readsize = '{0:g}'.format(num)

            if '.' not in readsize:
                return readsize+' '+unit+suffix
            else: 
                return "%3.1f %s%s" % (num, unit, suffix)

        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

