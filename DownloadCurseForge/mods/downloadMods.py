import json
import requests
import re
import sys
import os
sys.path.append("../");

from tools.delete import del_file
from tools.Downloader import Downloader
from multiprocessing import Process, Manager, Queue

def decoderJson():
    #os.system("title Now is 3 stage of 6 decoderJson");
    f = open("temp/manifest.json");
    text = f.read();
    f.close();
    fileArray = json.loads(text)["files"];
    outputArray = [];
    for file in fileArray:
        projectID = file['projectID'];
        fileID = file['fileID'];
        required = file['required'];
        if required == True:
            getUrl = "https://minecraft.curseforge.com/projects/%s/files/%s/download" % (projectID, fileID);
            outputArray.append(getUrl);
    return outputArray;

def redirectUrl(conf):
    #os.system("title Now is 5 stage of 6 redirectUrl");
    headers = {
        'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
        };
    url = conf['url'];
    s = requests.Session();
    res = s.get(url, allow_redirects = False, headers = headers);
    while res.status_code == 302 or res.status_code == 307:
        url = res.headers['Location'];
        if url.find("media.forgecdn.net") == -1:
            res = s.get(url, allow_redirects = False, headers = headers);
        else:
            break;
    return {'url' : url, 'name' : conf['name']};

def translateUrl(urlArray, index):
    #os.system("title Now is 4 stage of 6 translateUrl");
    url = urlArray[index];
    r = requests.get(url);
    text = r.text;
    searchObj = re.search(r'<a class="overflow-tip truncate" href="(.*?)" data-action=', text);
    finalUrl = "https://www.curseforge.com" + searchObj.group(1);
    finalUrl = finalUrl.replace("files", "download");
    finalUrl += "/file";

    searchObj = re.search(r'data-name="(.*?)">', text);
    finalFileName = searchObj.group(1);

    print("Now is downloading: %s" % (finalFileName));
    urlObj = redirectUrl({'url' : finalUrl, 'name' : finalFileName});
    return urlObj;
  

def startDownload(urlArray, index, length, q):
    for i in range(len(urlArray)):
        url = translateUrl(urlArray, i);
        url.update(path = str(index));
        url.update(src = os.path.dirname(os.getcwd()) + "\\src\\mods");
        down = Downloader(url);
        down.start();
        q.put(1);
        os.system("title Now is 6 stage of 6 downloadingMods... %d / %dmods percent: %.2f..." % (q.qsize(), length, q.qsize() / length * 100));
    os.popen("taskkill /pid %d /f" % (os.getpid()));


def downloadMods(num):
    urlArray = decoderJson();
    os.system("title Now is 6 stage of 6 downloadingMods... total: %dmods" % len(urlArray));
    part = len(urlArray) // num;
    q = Manager().Queue();
     
    ps = [];
    for i in range(num + 1):
        if (i != num):
            p = Process(target = startDownload, args = (urlArray[i * part : (i + 1) * part], i, len(urlArray), q, ));
            ps.append(p);
        else:
            p = Process(target = startDownload, args = (urlArray[i * part : len(urlArray)], i, len(urlArray), q, ));
            ps.append(p);
    
    for i in range(num + 1):
        ps[i].start();

    for i in range(num + 1):
        ps[i].join();