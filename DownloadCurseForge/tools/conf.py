import pickle
from os.path import exists
import sys
sys.path.append("../");

db = ""

def setPath(index):
    global db
    db='temp/download%s.data' % (index)

def append(obj):
  try:
    if exists(db):
      with open(db,'rb') as f:
        data=pickle.load(f)
    else: data={}
  except:
    data={}
  data[obj['url']]=obj
  with open(db,'wb') as f:
    pickle.dump(data,f)

def load(url):
  if not exists(db): return None
  try:
    with open(db,'rb') as f:
      data=pickle.load(f)
    return data.get(url)
  except:
    return None