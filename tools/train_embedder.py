r"""Train a Force of Will card embedder that survives stream conditions, and export it to ONNX
with the same interface as the Riftbound model (input [n,3,128,128] ImageNet-normalised,
output [n,256] unit vectors) so src/lib/embed-id.js needs no change.

Each card image is one class. Views are generated on the fly with augmentation that mimics what
the extension sees: loose or tight YOLO boxes, downscaling to 30-110 px, blur, JPEG, colour cast,
glare, rotation (rested cards), background around the box, and crops that drop the text box
(full-art prints). Loss is normalised-softmax with an additive cosine margin (ArcFace style).

usage: .venv/Scripts/python tools/train_embedder.py [--epochs 30] [--batch 256] [--out runs/embedder]
       .venv/Scripts/python tools/train_embedder.py --export-only runs/embedder/best.pt
"""
import argparse, json, math, os, random, time
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torchvision
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from card_aug import SIZE, augment, imread_u, load_backgrounds  # noqa: E402


def to_tensor(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return torch.from_numpy(((rgb - MEAN) / STD).transpose(2, 0, 1).copy())


def clean_view(card):
    return cv2.resize(card, (SIZE, SIZE), interpolation=cv2.INTER_AREA)


# ----------------------------------------------------------------------------- data
CACHE_W, CACHE_H = 208, 290


def build_cache(images, path):
    """Decode every card once into a uint8 memmap (N, H, W, 3) shared by all worker processes."""
    if os.path.exists(path) and os.path.exists(path + '.n') and open(path + '.n').read().strip() == str(len(images)):
        return
    mm = np.lib.format.open_memmap(path, mode='w+', dtype=np.uint8, shape=(len(images), CACHE_H, CACHE_W, 3))
    for i, p in enumerate(images):
        mm[i] = cv2.resize(imread_u(p), (CACHE_W, CACHE_H), interpolation=cv2.INTER_AREA)
    mm.flush()
    del mm
    open(path + '.n', 'w').write(str(len(images)))


def hard_for_epoch(epoch, epochs, floor=0.5):
    """Curriculum: start at `floor` augmentation strength, reach full strength at 40% of training."""
    return min(1.0, floor + epoch / max(1, epochs * 0.4))


class CardViews(Dataset):
    """All epochs in one dataset so a single persistent DataLoader serves the whole run."""

    def __init__(self, cache_path, n_images, bgs, views_per_epoch, epochs, seed=0, hard_floor=0.5):
        self.hard_floor = hard_floor
        self.cache_path = cache_path
        self.n_images = n_images
        self.bgs = bgs
        self.views = views_per_epoch
        self.epochs = epochs
        self.seed = seed
        self.mm = None

    def __len__(self):
        return self.views * self.epochs

    def _img(self, idx):
        if self.mm is None:
            self.mm = np.load(self.cache_path, mmap_mode='r')
        return np.ascontiguousarray(self.mm[idx])

    def __getitem__(self, i):
        rng = random.Random(self.seed * 1_000_003 + i)
        idx = rng.randrange(self.n_images)
        hard = hard_for_epoch(i // self.views, self.epochs, self.hard_floor)
        return to_tensor(augment(self._img(idx), self.bgs, rng, hard)), idx


# ----------------------------------------------------------------------------- model
class Embedder(nn.Module):
    def __init__(self, dim=256):
        super().__init__()
        m = torchvision.models.mobilenet_v3_small(weights=torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        self.features = m.features
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Sequential(nn.Linear(576, 512), nn.Hardswish(), nn.Dropout(0.1), nn.Linear(512, dim))

    def forward(self, x):
        x = self.pool(self.features(x)).flatten(1)
        return F.normalize(self.head(x), dim=1)


class CosMargin(nn.Module):
    """Normalised-softmax classifier with additive cosine margin (CosFace)."""

    def __init__(self, dim, n_classes, s=30.0, m=0.25):
        super().__init__()
        self.w = nn.Parameter(torch.randn(n_classes, dim) * 0.01)
        self.s, self.m = s, m

    def forward(self, emb, labels):
        cos = emb @ F.normalize(self.w, dim=1).t()
        onehot = F.one_hot(labels, cos.shape[1]).float()
        return F.cross_entropy(self.s * (cos - self.m * onehot), labels)


# ----------------------------------------------------------------------------- eval
@torch.no_grad()
def evaluate(model, cache_path, bgs, device, n_query=1200, seed=123):
    model.eval()
    mm = np.load(cache_path, mmap_mode='r')
    images = list(range(mm.shape[0]))
    gallery = []
    for i in range(0, len(images), 256):
        batch = torch.stack([to_tensor(clean_view(np.ascontiguousarray(mm[j]))) for j in images[i:i + 256]]).to(device)
        gallery.append(model(batch))
    gallery = torch.cat(gallery)
    rng = random.Random(seed)
    idxs = [rng.randrange(len(images)) for _ in range(n_query)]
    qs = []
    for k, idx in enumerate(idxs):
        r = random.Random(seed * 7 + k)
        qs.append(to_tensor(augment(np.ascontiguousarray(mm[idx]), bgs, r, 1.0)))
    q = model(torch.stack(qs).to(device))
    sims = q @ gallery.t()
    top = sims.topk(2, dim=1)
    labels = torch.tensor(idxs, device=device)
    correct = top.indices[:, 0] == labels
    acc = correct.float().mean().item()
    true_score = sims[torch.arange(len(idxs)), labels]
    # best wrong score per query
    sims_wrong = sims.clone()
    sims_wrong[torch.arange(len(idxs)), labels] = -1
    best_wrong = sims_wrong.max(dim=1).values
    model.train()
    return {
        'top1': acc,
        'true_score_median': true_score.median().item(),
        'true_score_p10': true_score.quantile(0.1).item(),
        'best_wrong_median': best_wrong.median().item(),
        'best_wrong_p90': best_wrong.quantile(0.9).item(),
    }


# ----------------------------------------------------------------------------- export
def export_onnx(model, path):
    model.eval().cpu()
    dummy = torch.zeros(1, 3, SIZE, SIZE)
    torch.onnx.export(model, dummy, path, input_names=['image'], output_names=['embedding'],
                      dynamic_axes={'image': {0: 'n'}, 'embedding': {0: 'n'}}, opset_version=17, dynamo=False)
    import onnxruntime as ort
    sess = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
    x = torch.randn(3, 3, SIZE, SIZE)
    ref = model(x).detach().numpy()
    out = sess.run(None, {'image': x.numpy()})[0]
    print(f"exported {path}: onnx vs torch max abs diff {np.abs(ref - out).max():.2e}, size {os.path.getsize(path) / 1e6:.1f} MB")


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='extension/data/cards.json')
    ap.add_argument('--media', default='media/cards')
    ap.add_argument('--bg', default='samples/frames')
    ap.add_argument('--out', default='runs/embedder')
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--views', type=int, default=64000, help='augmented views per epoch')
    ap.add_argument('--batch', type=int, default=256)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--workers', type=int, default=10)
    ap.add_argument('--export-only', default=None)
    ap.add_argument('--init', default=None, help='checkpoint to continue from')
    ap.add_argument('--hard-from-start', action='store_true', help='skip the curriculum (for fine-tuning)')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    cards = json.load(open(a.cards, encoding='utf-8'))
    files = sorted({c['image'] for c in cards if c.get('image')})
    images, files_ok = [], []
    for f in files:
        p = os.path.join(a.media, f)
        if os.path.exists(p) and imread_u(p) is not None:
            images.append(p)
            files_ok.append(f)
    print(f"{len(images)} readable card images (classes), {len(files) - len(images)} skipped")
    json.dump(files_ok, open(os.path.join(a.out, 'classes.json'), 'w'))

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = Embedder().to(device)
    if a.init:
        model.load_state_dict(torch.load(a.init, map_location=device)['model'])
        print('initialised from', a.init)
    if a.export_only:
        model.load_state_dict(torch.load(a.export_only, map_location=device)['model'])
        export_onnx(model, os.path.join(a.out, 'embedder.onnx'))
        return

    cache_path = os.path.join('runs', f'cards_{CACHE_W}x{CACHE_H}.npy')
    os.makedirs('runs', exist_ok=True)
    t0 = time.time()
    build_cache(images, cache_path)
    print(f"image cache {cache_path} ready in {time.time() - t0:.0f}s")
    bgs = load_backgrounds(a.bg)
    print(f"{len(bgs)} background frames, device {device}")
    head = CosMargin(256, len(images)).to(device)
    params = [{'params': model.features.parameters(), 'lr': a.lr * 0.4},
              {'params': list(model.head.parameters()) + list(head.parameters()), 'lr': a.lr}]
    opt = torch.optim.AdamW(params, weight_decay=1e-4)
    steps = a.epochs * (a.views // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[a.lr * 0.4, a.lr], total_steps=steps, pct_start=0.08)
    scaler = torch.amp.GradScaler('cuda', enabled=device == 'cuda')
    best = 0.0
    log = open(os.path.join(a.out, 'log.jsonl'), 'a')

    ds = CardViews(cache_path, len(images), bgs, a.views, a.epochs, seed=2 if a.init else 1, hard_floor=1.0 if a.hard_from_start else 0.5)
    dl = DataLoader(ds, batch_size=a.batch, shuffle=False, num_workers=a.workers, pin_memory=True,
                    persistent_workers=True, drop_last=True, prefetch_factor=2)
    steps_per_epoch = a.views // a.batch
    epoch, t0, tot, n = 0, time.time(), 0.0, 0
    model.train()
    for x, y in dl:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        with torch.autocast('cuda', enabled=device == 'cuda'):
            loss = head(model(x), y)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        sched.step()
        tot += loss.item()
        n += 1
        if n < steps_per_epoch:
            continue
        ev = evaluate(model, cache_path, bgs, device)
        rec = {'epoch': epoch + 1, 'loss': tot / max(1, n), 'hard': hard_for_epoch(epoch, a.epochs, ds.hard_floor),
               'sec': round(time.time() - t0), **ev}
        print(json.dumps(rec), flush=True)
        log.write(json.dumps(rec) + "\n")
        log.flush()
        torch.save({'model': model.state_dict(), 'epoch': epoch + 1, 'eval': ev}, os.path.join(a.out, 'last.pt'))
        if ev['top1'] >= best:
            best = ev['top1']
            torch.save({'model': model.state_dict(), 'epoch': epoch + 1, 'eval': ev}, os.path.join(a.out, 'best.pt'))
        epoch, t0, tot, n = epoch + 1, time.time(), 0.0, 0
        if epoch >= a.epochs:
            break

    model.load_state_dict(torch.load(os.path.join(a.out, 'best.pt'), map_location=device)['model'])
    export_onnx(model, os.path.join(a.out, 'embedder.onnx'))


if __name__ == '__main__':
    main()
