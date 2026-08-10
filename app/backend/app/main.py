from pathlib import Path
from typing import Optional
import asyncio
import os
import shutil
import subprocess
import sys
import threading
import uuid

import cv2
import numpy as np
import pydicom
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT=Path(__file__).resolve().parents[3]; WORK=ROOT/'.pyrestus-jobs'; WORK.mkdir(exist_ok=True); DEFAULT=Path.home()/'Documents'/'Pyrestus Results'; JOBS={}
app=FastAPI(title='Pyrestus Local API'); app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:8080','http://localhost:8080'],allow_methods=['*'],allow_headers=['*'])
class Options(BaseModel):
    output_directory: Optional[str] = None
    output_format: str = 'png'
def get(j):
 if j not in JOBS: raise HTTPException(404,'Job not found')
 return JOBS[j]
@app.get('/api/health')
def health(): return {'status':'healthy','mode':'local'}
@app.post('/api/jobs')
def create(o:Options):
 j=uuid.uuid4().hex; (WORK/j/'inputs').mkdir(parents=True); JOBS[j]={'id':j,'status':'created','files':[],'total_files':0,'files_completed':0,'frames_created':0,'output_format':o.output_format,'output_directory':None,'message':'Ready for files','error':None}; return JOBS[j]
@app.post('/api/jobs/{j}/files')
async def upload(j:str,files:list[UploadFile]=File(...)):
 s=get(j); dest=WORK/j/'inputs'
 for f in files:
  name=Path(f.filename or 'input').name
  with (dest/name).open('wb') as out: shutil.copyfileobj(f.file,out)
  s['files'].append(name)
 s['total_files']=len(s['files']); s['status']='ready'; s['message']='Files ready'; return s
def _open_folder_dialog() -> Optional[str]:
 try:
  import tkinter as tk
  from tkinter import filedialog
  root=tk.Tk(); root.withdraw(); root.attributes('-topmost',True); folder=filedialog.askdirectory(title='Choose Pyrestus output folder',initialdir=str(DEFAULT)); root.destroy()
  return folder or None
 except Exception:
  return None
@app.post('/api/output-directory/select')
async def choose():
 loop=asyncio.get_event_loop()
 folder=await loop.run_in_executor(None,_open_folder_dialog)
 if folder: return {'selected':True,'path':folder,'path_display':folder}
 DEFAULT.mkdir(parents=True,exist_ok=True); return {'selected':True,'path':str(DEFAULT),'path_display':str(DEFAULT),'used_default':True}
@app.post('/api/jobs/{j}/process')
def process(j:str,o:Options):
 s=get(j)
 if not s['files']: raise HTTPException(400,'Add at least one file first')
 out=Path(o.output_directory or DEFAULT).expanduser(); out.mkdir(parents=True,exist_ok=True); s.update(status='processing',output_directory=str(out),output_format=o.output_format,message='Starting processing',error=None); threading.Thread(target=run,args=(j,),daemon=True).start(); return s
@app.get('/api/jobs/{j}')
def status(j:str): return get(j)
@app.post('/api/jobs/{j}/open-output-directory')
def open_folder(j:str):
 p=Path(get(j)['output_directory']);
 if sys.platform=='darwin': subprocess.Popen(['open',str(p)])
 elif os.name=='nt': os.startfile(str(p))
 else: subprocess.Popen(['xdg-open',str(p)])
 return {'opened':True}
def write(frame,out,i,fmt):
 out.mkdir(parents=True,exist_ok=True)
 if frame.ndim==3: frame=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
 if not cv2.imwrite(str(out/f'{i:04d}.{fmt}'),frame): raise RuntimeError('Could not write output frame')
def video(src,out,fmt):
 cap=cv2.VideoCapture(str(src));
 if not cap.isOpened(): raise ValueError('This video could not be opened')
 i=0
 while True:
  ok,frame=cap.read()
  if not ok: break
  write(frame,out,i,fmt);i+=1
 cap.release()
 if not i: raise ValueError('No frames found in video')
 return i
def dicom(src,out,fmt):
 pixels=pydicom.dcmread(str(src)).pixel_array
 frames=pixels if pixels.ndim>=3 else pixels[np.newaxis,...]
 for i,f in enumerate(frames): write(np.asarray(f),out,i,fmt)
 return len(frames)
def run(j):
 s=get(j)
 try:
  for n,name in enumerate(s['files'],1):
   s['message']=f'Processing {name} ({n} of {s["total_files"]})'; src=WORK/j/'inputs'/name; out=Path(s['output_directory'])/src.stem
   count=dicom(src,out,s['output_format']) if src.suffix.lower() in {'.dcm','.dicom'} else video(src,out,s['output_format'])
   s['frames_created']+=count;s['files_completed']=n
  s['status']='completed';s['message']='Processing complete'
 except Exception as e: s['status']='failed';s['message']='Processing could not be completed';s['error']=str(e)
WEB=ROOT/'app'/'build'/'web'
if WEB.exists(): app.mount('/',StaticFiles(directory=WEB,html=True),name='web')