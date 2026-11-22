"""Reproducible synthetic IQ dataset and experimental training (NOT RF validation)."""
from pathlib import Path
import json
import numpy as np
import torch
from torch import nn

CLASSES = ("CW", "AM", "NFM", "WFM", "USB", "LSB", "UNKNOWN")
SEED = 20261108
torch.manual_seed(SEED)
np.random.seed(SEED)

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.net=nn.Sequential(
            nn.Conv1d(2,24,9,stride=4,padding=4),nn.ReLU(),
            nn.Conv1d(24,48,7,stride=4,padding=3),nn.ReLU(),
            nn.Conv1d(48,64,5,stride=4,padding=2),nn.ReLU(),
            nn.Conv1d(64,64,5,stride=2,padding=2),nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),nn.Flatten(),nn.Linear(64,7))
    def forward(self,x):return self.net(x)

def sample(label,rng,n=2048):
    fs=48000
    t=np.arange(n)/fs
    freq=rng.uniform(300,2800)
    noise=rng.normal(size=n)+1j*rng.normal(size=n)
    phase=rng.uniform(0,2*np.pi)
    if label=="CW":
        z=np.exp(1j*(2*np.pi*freq*t+phase))*((np.sin(2*np.pi*rng.uniform(4,14)*t)>0).astype(float))
    elif label=="AM":
        mod=1+0.75*np.sin(2*np.pi*rng.uniform(100,1500)*t)
        z=mod*np.exp(1j*(2*np.pi*rng.uniform(-800,800)*t+phase))
    elif label in ("NFM","WFM"):
        deviation=rng.uniform(1500,4500) if label=="NFM" else rng.uniform(15000,35000)
        mod=np.sin(2*np.pi*rng.uniform(200,2200)*t)
        z=np.exp(1j*(2*np.pi*rng.uniform(-700,700)*t+2*np.pi*deviation*np.cumsum(mod)/fs+phase))
    elif label in ("USB","LSB"):
        side=1 if label=="USB" else -1
        z=np.zeros(n,dtype=complex)
        for _ in range(4):
            f=rng.uniform(300,2700)
            z+=rng.uniform(.2,1)*np.exp(1j*(side*2*np.pi*f*t+rng.uniform(0,2*np.pi)))
    else:
        z=noise
    snr=rng.uniform(-2,25)
    z=np.asarray(z,dtype=complex)
    z+=np.sqrt(np.mean(np.abs(z)**2)+1e-8)*10**(-snr/20)*noise/np.sqrt(2)
    z-=z.mean()
    z/=max(1e-8,np.sqrt(np.mean(np.abs(z)**2)))
    return np.stack([z.real,z.imag]).astype("float32")

def dataset(count,seed):
    rng=np.random.default_rng(seed)
    xs=[];ys=[]
    for i in range(count):
        label=i%len(CLASSES)
        xs.append(sample(CLASSES[label],rng));ys.append(label)
    return torch.from_numpy(np.stack(xs)),torch.tensor(ys)

def main():
    torch.set_num_threads(2)
    train_x,train_y=dataset(5600,42)
    test_x,test_y=dataset(1400,991)
    model=Net()
    optimizer=torch.optim.Adam(model.parameters(),lr=.003)
    for epoch in range(18):
        model.train()
        for indices in torch.randperm(len(train_y)).split(128):
            optimizer.zero_grad()
            loss=nn.functional.cross_entropy(model(train_x[indices]),train_y[indices])
            loss.backward()
            optimizer.step()
        print(f"epoch {epoch+1}/18",flush=True)
    model.eval()
    with torch.no_grad():
        predictions=model(test_x).argmax(1).numpy()
    truth=test_y.numpy()
    confusion=np.zeros((7,7),dtype=int)
    for actual,predicted in zip(truth,predictions):
        confusion[actual,predicted]+=1
    metrics={"labels":CLASSES,"train_samples":len(train_y),"validation_samples":len(test_y),
             "accuracy":float(np.mean(predictions==truth)),"confusion_matrix":confusion.tolist(),
             "limitations":"Synthetic-only validation; not tested on SDR hardware"}
    Path("models/iq").mkdir(parents=True,exist_ok=True)
    torch.save(model.state_dict(),"models/iq/synthetic_v2.pt")
    Path("models/iq/synthetic_v2_metrics.json").write_text(json.dumps(metrics,indent=2))
    print(json.dumps(metrics,indent=2))

if __name__=="__main__":main()
