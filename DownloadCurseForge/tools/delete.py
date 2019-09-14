import os
import time
def  del_file(path):
    os.popen("rmdir /s /q %s" % path);
    time.sleep(2);
    os.popen("md %s" % path);




