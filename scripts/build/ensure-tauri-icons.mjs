import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

const outDir = process.argv[2]
const wantsIco = process.argv.includes('--ico')

if (!outDir) {
  console.error('Usage: node scripts/build/ensure-tauri-icons.mjs <icons-dir> [--ico]')
  process.exit(2)
}

fs.mkdirSync(outDir, { recursive: true })

const crcTable = new Uint32Array(256)
for (let n = 0; n < 256; n += 1) {
  let c = n
  for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1)
  crcTable[n] = c >>> 0
}

function crc32(buf) {
  let c = 0xffffffff
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const t = Buffer.from(type)
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(Buffer.concat([t, data])))
  return Buffer.concat([len, t, data, crc])
}

function mix(a, b, t) { return Math.round(a + (b - a) * t) }
function colorMix(a, b, t) { return [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t), mix(a[3] ?? 255, b[3] ?? 255, t)] }
function setPixel(buf, size, x, y, rgba) {
  if (x < 0 || y < 0 || x >= size || y >= size) return
  const i = (y * size + x) * 4
  const sa = (rgba[3] ?? 255) / 255
  const da = buf[i + 3] / 255
  const oa = sa + da * (1 - sa)
  if (oa <= 0) return
  buf[i] = Math.round((rgba[0] * sa + buf[i] * da * (1 - sa)) / oa)
  buf[i + 1] = Math.round((rgba[1] * sa + buf[i + 1] * da * (1 - sa)) / oa)
  buf[i + 2] = Math.round((rgba[2] * sa + buf[i + 2] * da * (1 - sa)) / oa)
  buf[i + 3] = Math.round(oa * 255)
}

function fillCircle(buf, size, cx, cy, radius, rgba) {
  const minX = Math.max(0, Math.floor(cx - radius - 1)); const maxX = Math.min(size - 1, Math.ceil(cx + radius + 1))
  const minY = Math.max(0, Math.floor(cy - radius - 1)); const maxY = Math.min(size - 1, Math.ceil(cy + radius + 1))
  for (let y = minY; y <= maxY; y += 1) for (let x = minX; x <= maxX; x += 1) {
    const dx = x + 0.5 - cx; const dy = y + 0.5 - cy; const d = Math.sqrt(dx * dx + dy * dy)
    if (d <= radius + 0.8) {
      const edge = Math.max(0, Math.min(1, radius + 0.8 - d))
      setPixel(buf, size, x, y, [rgba[0], rgba[1], rgba[2], Math.round((rgba[3] ?? 255) * edge)])
    }
  }
}

function insideRoundedRect(x, y, left, top, width, height, radius) {
  const right = left + width; const bottom = top + height
  if (x >= left + radius && x <= right - radius && y >= top && y <= bottom) return true
  if (y >= top + radius && y <= bottom - radius && x >= left && x <= right) return true
  const cx = x < left + radius ? left + radius : right - radius
  const cy = y < top + radius ? top + radius : bottom - radius
  return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
}

function drawPolyline(buf, size, points, width, start, end, alpha = 255) {
  let total = 0
  const lengths = []
  for (let i = 0; i < points.length - 1; i += 1) {
    const dx = points[i + 1][0] - points[i][0]; const dy = points[i + 1][1] - points[i][1]
    const len = Math.sqrt(dx * dx + dy * dy); lengths.push(len); total += len
  }
  let travelled = 0
  for (let i = 0; i < points.length - 1; i += 1) {
    const [x1, y1] = points[i]; const [x2, y2] = points[i + 1]; const len = lengths[i]
    const steps = Math.max(2, Math.ceil(len * 1.25))
    for (let s = 0; s <= steps; s += 1) {
      const local = s / steps; const t = Math.min(1, (travelled + len * local) / Math.max(total, 1))
      const c = colorMix(start, end, t); c[3] = alpha
      fillCircle(buf, size, x1 + (x2 - x1) * local, y1 + (y2 - y1) * local, width / 2, c)
    }
    travelled += len
  }
}

function renderBrand(size) {
  const scale = size / 512
  const buf = Buffer.alloc(size * size * 4)
  const left = 32 * scale; const top = 32 * scale; const box = 448 * scale; const radius = 116 * scale
  const bgA = [11, 29, 58, 255]; const bgB = [6, 19, 39, 255]
  for (let y = 0; y < size; y += 1) for (let x = 0; x < size; x += 1) {
    if (!insideRoundedRect(x + 0.5, y + 0.5, left, top, box, box, radius)) continue
    const t = Math.min(1, Math.max(0, (x + y) / (size * 2)))
    const c = colorMix(bgA, bgB, t); setPixel(buf, size, x, y, c)
  }

  const raw = [[157,169],[157,132],[190,100],[226,100],[327,100],[366,100],[405,139],[405,178],[405,217],[366,256],[327,256],[236,256],[198,256],[160,294],[160,332],[160,370],[198,408],[236,408],[325,408],[363,408],[401,370],[401,332]]
  const points = raw.map(([x,y]) => [x * scale, y * scale])
  drawPolyline(buf, size, points, 46 * scale, [10,46,89,190], [10,46,89,190], 190)
  drawPolyline(buf, size, points, 28 * scale, [47,107,255,255], [34,211,238,255], 255)
  fillCircle(buf, size, 401 * scale, 112 * scale, 12 * scale, [139,92,246,255])
  fillCircle(buf, size, 126 * scale, 398 * scale, 9 * scale, [34,211,238,255])
  fillCircle(buf, size, 256 * scale, 256 * scale, 10 * scale, [255,255,255,255])
  return buf
}

function makePng(size) {
  const pixels = renderBrand(size)
  const rows = []
  for (let y = 0; y < size; y += 1) {
    const row = Buffer.alloc(1 + size * 4); row[0] = 0
    pixels.copy(row, 1, y * size * 4, (y + 1) * size * 4); rows.push(row)
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 6
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(Buffer.concat(rows))), chunk('IEND', Buffer.alloc(0))])
}

for (const [name, size] of [['icon.png',512],['32x32.png',32],['128x128.png',128],['128x128@2x.png',256]]) fs.writeFileSync(path.join(outDir, name), makePng(size))

if (wantsIco) {
  const icoPng = makePng(256)
  const header = Buffer.alloc(6); header.writeUInt16LE(0,0); header.writeUInt16LE(1,2); header.writeUInt16LE(1,4)
  const entry = Buffer.alloc(16); entry[0]=0; entry[1]=0; entry.writeUInt16LE(1,4); entry.writeUInt16LE(32,6); entry.writeUInt32LE(icoPng.length,8); entry.writeUInt32LE(22,12)
  fs.writeFileSync(path.join(outDir, 'icon.ico'), Buffer.concat([header, entry, icoPng]))
}

console.log(`Scheduler Pro Time Flow icons ready at ${outDir}`)
