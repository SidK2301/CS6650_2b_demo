"""Establish an idle baseline, then start the measured local-only workload."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error

root = Path(__file__).resolve().parents[1]
# Initialize each business endpoint and its error series before the idle period.
body = {"product_id":1,"sku":"LOCAL","manufacturer":"HW5","category_id":1,"weight":0,"some_other_id":1}
requests = [urllib.request.Request('http://localhost:8080/products/1'),
            urllib.request.Request('http://localhost:8080/products/1001'),
            urllib.request.Request('http://localhost:8080/products/1/details',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),
            urllib.request.Request('http://localhost:8080/products/1/details',data=b'{}',headers={'Content-Type':'application/json'})]
for req in requests:
    try: urllib.request.urlopen(req).read()
    except urllib.error.HTTPError as exc: exc.read()
meta={'environment':'local native-architecture Compose app','idle_start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'idle_seconds':90,'users':50,'spawn_rate':10,'warmup_seconds':20,'measurement_seconds':180,
      'workload':{'valid_GET':.88,'valid_POST':.10,'intentional_404':.01,'intentional_400':.01},'fault_injection':False}
path=root/'results/locust/local-red_metadata.json'
path.write_text(json.dumps(meta,indent=2)+'\n')
print('Local idle baseline started (90 seconds).',flush=True)
time.sleep(90)
meta['load_start_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
path.write_text(json.dumps(meta,indent=2)+'\n')
env=dict(os.environ,WORKLOAD='errors',LOCUST_NETWORK='cs6650_2b_demo_default')
subprocess.run([str(root/'scripts/start-locust.sh'),'ProductFastHttpUser','local-red','http://app:8080','50'],env=env,check=True)
print('Local load started: 20-second warm-up plus 180-second measurement.',flush=True)
