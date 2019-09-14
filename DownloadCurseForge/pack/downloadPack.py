import re
import sys
import zipfile
import requests
import os
import time
from tools.rename import renameTitle
from tools.delete import del_file
sys.path.append("../");

def redirectUrl(conf):
    url = conf['url'];
    headers = {
        'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
        };
    s = requests.Session();
    res = s.get(url, allow_redirects = False, headers = headers);
    while res.status_code == 302 or res.status_code == 307:
        url = res.headers['Location'];
        if url.find("media.forgecdn.net") == -1:
            res = s.get(url, allow_redirects = False, headers = headers);
        else:
            break;
    return {'url' : url, 'name' : conf['name']};

def getDownloadUrl(originalUrl):
    text = requests.get(originalUrl).text;

    searchObj = re.search(r'<a class="overflow-tip truncate" href="(.*?)" data-action=', text);
    finalUrl = "https://www.curseforge.com" + searchObj.group(1);
    finalUrl = finalUrl.replace("files", "download");
    finalUrl += "/file";

    searchObj = re.search(r'data-name="(.*?)">', text);
    finalFileName = searchObj.group(1);
    
    finalFileName = renameTitle(finalFileName);

    urlObj = redirectUrl({'url' : finalUrl, 'name' : finalFileName});
    return urlObj;

def startDownload(beginUrl):
    os.system("title Now is 1 stage of 6 downloadingPack...");
    downloadUrl = getDownloadUrl(beginUrl);
    url = downloadUrl['url'];
    file_name = "temp/%s" % downloadUrl['name'] + ".zip";
    count = 0;
    res = requests.get(url, stream=True);
    chunk_size = 10240;
    content_size = int(res.headers['content-length']);
    lastTime = time.time();
    with open(file_name, "wb") as file:
        for data in res.iter_content(chunk_size=chunk_size):
            count += 1;
            current = len(data) * count / 1024;
            total = content_size / 1024;
            interval = time.time() - lastTime;
            file.write(data);
            try:
                print("total: %.2f MB  current:%.2f MB  downloadSpeed:%.2f MB / s" % (total / 1024, current / 1024, (chunk_size / 1024 / interval) / 1024));
                os.system("title Now is 1 stage of 6 downloadingPack downloadSpeed: %.2f MB / s..." % ((chunk_size / 1024 / interval) / 1024));
            except ZeroDivisionError:
                pass;
            lastTime = time.time();
    return "temp/" + downloadUrl['name'] + ".zip";

def unZip(name):
    os.system("title Now is 2 stage of 6 unZipPack...");
    frzip = zipfile.ZipFile(name);
    frzip.extractall(os.getcwd() + "\\temp");
    frzip.close();

def exportZip(url):
    del_file(os.path.abspath("temp"));
    src = startDownload(url);
    unZip(src);
    path1 = os.getcwd() + "\\temp\\overrides";
    path2 = os.path.dirname(os.getcwd()) + "\\src";
    os.popen("xcopy %s %s /S /E /Y" % (path1, path2));
    