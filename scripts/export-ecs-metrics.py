"""Export service-level CloudWatch data without requiring Container Insights."""
import datetime
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
start = json.loads((root/'results/locust/http-1_metadata.json').read_text())['started_utc']
end = datetime.datetime.now(datetime.timezone.utc).isoformat()
folder = root/'results/cloudwatch'
folder.mkdir(parents=True,exist_ok=True)
for metric in ['CPUUtilization','MemoryUtilization']:
    cmd=['aws','cloudwatch','get-metric-statistics','--region','us-west-2',
         '--namespace','AWS/ECS','--metric-name',metric,'--dimensions',
         'Name=ClusterName,Value=cs6650-hw5-product-cluster',
         'Name=ServiceName,Value=cs6650-hw5-product','--start-time',start,
         '--end-time',end,'--period','60','--statistics','Average','Maximum','--output','json']
    data=json.loads(subprocess.check_output(cmd,text=True))
    data['Datapoints'].sort(key=lambda x:x['Timestamp'])
    (folder/f'{metric}.json').write_text(json.dumps(data,indent=2)+'\n')
    print(metric,len(data['Datapoints']),'minute samples')
(folder/'window.json').write_text(json.dumps({'start':start,'end':end},indent=2)+'\n')
