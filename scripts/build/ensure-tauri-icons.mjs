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

const table = new Uint32Array(256)
for (let n = 0; n < 256; n += 1) {
  let c = n
  for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1)
  table[n] = c >>> 0
}

function crc32(buf) {
  let c = 0xffffffff
  for (const b of buf) c = table[(c ^ b) & 0xff] ^ (c >>> 8)
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

function makePng(size) {
  const rows = []
  for (let y = 0; y < size; y += 1) {
    const row = Buffer.alloc(1 + size * 4)
    row[0] = 0
    for (let x = 0; x < size; x += 1) {
      const i = 1 + x * 4
      const grad = Math.round(48 + 80 * (x / size))
      row[i] = 20
      row[i + 1] = grad
      row[i + 2] = 220
      row[i + 3] = 255
      const s1 = x > size * 0.28 && x < size * 0.72 && y > size * 0.23 && y < size * 0.34
      const s2 = x > size * 0.28 && x < size * 0.72 && y > size * 0.45 && y < size * 0.56
      const s3 = x > size * 0.28 && x < size * 0.72 && y > size * 0.67 && y < size * 0.78
      const s4 = x > size * 0.28 && x < size * 0.40 && y > size * 0.23 && y < size * 0.56
      const s5 = x > size * 0.60 && x < size * 0.72 && y > size * 0.45 && y < size * 0.78
      if (s1 || s2 || s3 || s4 || s5) {
        row[i] = 255
        row[i + 1] = 255
        row[i + 2] = 255
      }
    }
    rows.push(row)
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8
  ihdr[9] = 6
  ihdr[10] = 0
  ihdr[11] = 0
  ihdr[12] = 0

  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(Buffer.concat(rows))),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

const png = makePng(512)
fs.writeFileSync(path.join(outDir, 'icon.png'), png)

if (wantsIco) {
  const icoPng = makePng(256)
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(1, 4)
  const entry = Buffer.alloc(16)
  entry[0] = 0
  entry[1] = 0
  entry[2] = 0
  entry[3] = 0
  entry.writeUInt16LE(1, 4)
  entry.writeUInt16LE(32, 6)
  entry.writeUInt32LE(icoPng.length, 8)
  entry.writeUInt32LE(header.length + entry.length, 12)
  fs.writeFileSync(path.join(outDir, 'icon.ico'), Buffer.concat([header, entry, icoPng]))
}

console.log(`Tauri icons ready at ${outDir}`)
