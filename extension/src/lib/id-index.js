const MAGIC = "FOWIDX01";
const HEADER_BYTES = 64;
const CARD_BYTES = 40;

const readCString = (bytes, offset) => {
  let end = offset;
  while (end < bytes.length && bytes[end] !== 0) end += 1;
  return new TextDecoder().decode(bytes.subarray(offset, end));
};

export const parseIdIndex = (buffer) => {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  const magic = new TextDecoder().decode(bytes.subarray(0, 8));
  if (magic !== MAGIC) throw new Error("ID index magic mismatch");
  const version = view.getUint32(8, true);
  if (version !== 1) throw new Error(`ID index version ${version} unsupported`);

  const nCards = view.getUint32(12, true);
  const nDesc = view.getUint32(16, true);
  const descBytes = view.getUint32(20, true);
  const nEmb = view.getUint32(24, true);
  const embDim = view.getUint32(28, true);
  const queryWidth = view.getUint32(32, true);
  const minScore = view.getFloat32(56, true);
  const wEmb = view.getFloat32(60, true);

  const heapStart = HEADER_BYTES + nCards * CARD_BYTES;
  const tailBytes = nDesc * 8 + nDesc * descBytes + nEmb * embDim * 4;
  const heapLen = buffer.byteLength - heapStart - tailBytes;
  if (heapLen < 0) throw new Error("ID index is truncated");
  const embStart = heapStart + heapLen + nDesc * 8 + nDesc * descBytes;

  const cards = [];
  for (let i = 0; i < nCards; i += 1) {
    const at = HEADER_BYTES + i * CARD_BYTES;
    cards.push({
      id: readCString(bytes, heapStart + view.getUint32(at, true)),
      name: readCString(bytes, heapStart + view.getUint32(at + 4, true)),
      imageUrl: readCString(bytes, heapStart + view.getUint32(at + 8, true)),
      group: readCString(bytes, heapStart + view.getUint32(at + 12, true)),
      nKp: view.getUint32(at + 16, true),
      kpIndex: view.getUint32(at + 20, true),
      nDes: view.getUint32(at + 24, true),
      desIndex: view.getUint32(at + 28, true),
      nEmb: view.getUint32(at + 32, true),
      embIndex: view.getUint32(at + 36, true),
    });
  }

  const embeddings = new Float32Array(
    buffer.slice(embStart, embStart + nEmb * embDim * 4)
  );
  const E = [];
  const EOwner = [];
  for (let i = 0; i < cards.length; i += 1) {
    const card = cards[i];
    for (let j = 0; j < card.nEmb; j += 1) {
      const off = (card.embIndex + j) * embDim;
      E.push(embeddings.subarray(off, off + embDim));
      EOwner.push(i);
    }
  }

  return {
    version,
    queryWidth,
    minScore,
    wEmb,
    descBytes,
    embDim,
    cards,
    E,
    EOwner,
    nDesc,
    nEmb,
  };
};

export const loadIdIndex = async (url) => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`ID index fetch failed (${response.status})`);
  return parseIdIndex(await response.arrayBuffer());
};
