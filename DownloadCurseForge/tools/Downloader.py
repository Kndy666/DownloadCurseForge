import time
from os.path import basename, exists, getsize
from queue import Queue
from threading import Lock, Thread, current_thread

import requests as req
import random as rand
import sys
sys.path.append("../");

from tools import conf
from tools import log


class Downloader:
  KB=1024
  MB=KB*KB
  GB=KB*MB
  range_size=MB
  max_workers=50
  spd_refresh_interval=1
  user_agents=[
    'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1',
    'Mozilla/5.0 (Windows NT 6.4; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2225.0 Safari/537.36'
    'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0'
  ]
  chunk_size=KB
  max_error=0.35 #单线程允许最大出错率
  max_error_one_worker=0.75 #仅剩一个线程时允许的最大出错率
  home='' #下载目录
  def __init__(self,c):
    self.__locks={i:Lock() for i in ('file','worker_info','itr_job','download_info')}
    self.__config=c
    self.__alive=False
    self.__fails=Queue()
    self.__conf=c
    self.home = c['src']
    conf.setPath(c['path'])
    c=conf.load(c['url'])
    if c:
      self.__conf=c
      self.__init_from_conf()
    else: self.__init_task()

  def __init_from_conf(self):
    self.__download_offset=self.__conf['offset']
    for i in self.__conf['fails']: self.__fails.put(i)

  def __get_agent(self):
    return self.user_agents[rand.randint(0,len(self.user_agents)-1)]

  def __init_task(self):
    headers={'Range':'bytes=0-0'}
    headers['User-Agent']=self.__get_agent()
    #print(headers)
    try:
      r=req.get(self.__conf['url'],headers=headers,stream=True)
      self.__conf['name'] = basename(self.__conf['url']) or str(int(round(time.time()*1000)))
      self.__conf['206'] = r.status_code == 206 or r.headers.get('Accept-Ranges')=='bytes'
      if self.__conf['206']:
        self.__conf['len']=int(r.headers['Content-Range'].split('/')[-1])
      elif r.status_code!=200:
        log.out('init task err')
        return
      else:
        self.__conf['len']=int(r.headers['Content-Length'])
      r.close()
      self.__download_offset=0
      self.__conf['init']=True
    except Exception as e:
      log.out(e)

  def __itr_job(self):
    if self.__locks['itr_job'].acquire():
      if not self.__fails.empty():
        ans=self.__fails.get()
      elif self.__download_offset<self.__conf['len']:
        o=self.__download_offset
        ans=(o,min(self.__conf['len']-1,o+self.range_size-1))
        self.__download_offset+=self.range_size
      else:
        ans=(-1,-1)
      self.__locks['itr_job'].release()
    return ans

  def __has_job(self):
    if self.__locks['itr_job'].acquire():
      ans=self.__download_offset<self.__conf['len'] or  not self.__fails.empty()
      self.__locks['itr_job'].release()
    return ans

  def __download_no_206(self):
    headers={'User-Agent':self.__get_agent()}
    r=req.get(self.__conf['url'],headers=headers,stream=True)
    self.__download_offset=0
    if r.status_code != 200:
      r.close()
      self.__stopped()
      return
    try:
      for con in r.iter_content(chunk_size=self.chunk_size):
        if self.__kill_signal: break
        self.__file.write(con)
        l=len(con)
        self.__down_bytes+=l
        self.__download_offset+=l
        t0=time.time()
        t=t0-self.__last_time
        if t>=self.spd_refresh_interval:
          self.__down_spd=self.__down_bytes/t
          log.out('downloadSpend: %d KB/s'%(self.__down_spd/self.KB))
          self.__last_time=t0
          self.__down_bytes=0
    except:
      pass
    r.close()
    self.__stopped()

  def __download_206(self):
    file_len=self.__conf['len']
    total=0
    error=0
    kill=False
    with req.session() as sess:
      while True:
        s,e=self.__itr_job()
        if s==-1:
          log.out('no job stop')
          break
        headers={'Range':'bytes=%d-%d'%(s,e)}
        headers['User-Agent']=self.__get_agent()
        try:
          r=sess.get(self.__conf['url'],headers=headers,stream=True)
          total+=1
          if r.status_code!=206:
            self.__fails.put((s,e))
            error+=1
            if error>self.max_error*total:
              if self.__locks['worker_info'].acquire():
                num=self.__current_workers
                self.__locks['worker_info'].release() 
                if error>self.max_error_one_worker*total or num>1:
                  break           
            continue
          for con in r.iter_content(chunk_size=self.chunk_size):
            if self.__locks['worker_info'].acquire():
              if self.__kill_signal:
                self.__locks['worker_info'].release()
                kill=True
                break
              self.__locks['worker_info'].release()

            if self.__locks['file'].acquire():
              self.__file.seek(s)
              self.__file.write(con)
              l=len(con)
              s+=l
              self.__locks['file'].release()

              if self.__locks['download_info'].acquire():
                self.__down_bytes+=l
                t0=time.time()
                t=t0-self.__last_time
                if t>=self.spd_refresh_interval:
                  log.out('downloadSpend: %d KB/s'%(self.__down_spd/self.KB))
                  self.__down_spd=self.__down_bytes/t
                  self.__down_bytes=0
                  self.__last_time=t0
                self.__locks['download_info'].release()

          if s<=e and s<file_len:
            self.__fails.put((s,e))
          if kill:
            break
        except  :
          self.__fails.put((s,e))
          error+=1
          if error>self.max_error*total:
            if self.__locks['worker_info'].acquire():
              num=self.__current_workers
              self.__locks['worker_info'].release() 
              if error>self.max_error_one_worker*total or num>1:
                break 

      self.__stopped()

  def __start_worker(self,target):
    if self.__locks['worker_info'].acquire():
      if self.__kill_signal: 
        self.__locks['worker_info'].release()
        return False
      if self.__current_workers<self.max_workers:
        Thread(target=target).start()
        self.__current_workers+=1
        #log.out('new worker started, current workers %d'%self.__current_workers)
      self.__locks['worker_info'].release()
    return True

  def __start_workers(self):
    for _ in range(self.max_workers):
      if not self.__start_worker(self.__download_206): break
      time.sleep(0.8)

  def start(self):
    if self.__alive:
      #log.out('already started!')
      return
    if self.__conf.get('status')=='done':
      #log.out('already done')
      return
    self.__alive=True
    self.__kill_signal=False
    self.__conf['status']='working'
    self.__down_bytes=0
    self.__down_spd=0
    self.__last_time=0
    self.__current_workers=0
    self.__start_time=time.time()

    try:
      path=self.home+ '/' + self.__conf['name']
      self.__file=open(path,(exists(path) and 'rb+') or 'wb' )
      if not self.__conf['206']:
        Thread(target=self.__start_workers).start()
      else: self.__start_worker(self.__download_no_206)
      #log.out('starting done!')
    except: log.out('starting failed')

  def stop(self):
    if self.__kill_signal:
      return
    log.out('stopping')
    if self.__locks['worker_info'].acquire():
      self.__kill_signal=True
      if self.__conf['status']=='working':
        self.__conf['status']='stopped'
      self.__locks['worker_info'].release()

  def __after_stopped(self):
    if not self.__kill_signal:
      self.__kill_signal=True
    __alive=False
    self.__file.close()
    #log.out('total time: %.2f'%(time.time()-self.__start_time))
    self.__conf['offset']=self.__download_offset
    if not self.__has_job():
      self.__conf['status']='done'
    elif self.__conf.get('status')!='stopped': self.__conf['status']='error'
    leak=0
    ls=[]
    while not self.__fails.empty():
      i=self.__fails.get()
      leak+=i[1]-i[0]+1
      ls.append(i)
    self.__conf['fails']=ls
    leak+=max(self.__conf['len']-self.__download_offset,0)
    #log.out('total leak:  %d'%leak)
    conf.append(self.__conf)

  def __stopped(self):
    if self.__locks['worker_info'].acquire():
      self.__current_workers-=1
      #log.out('%s stopped'%current_thread().name)
      if self.__current_workers==0:
        self.__after_stopped()
      self.__locks['worker_info'].release()
