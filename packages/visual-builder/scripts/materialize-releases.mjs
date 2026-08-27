import { gunzipSync } from 'node:zlib'
import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here=dirname(fileURLToPath(import.meta.url))
const packageRoot=resolve(here,'..')
const encodedRoot=join(packageRoot,'release-b64')
const outputRoot=join(packageRoot,'releases-src')
const versions=['1.0.0','2.0.0','2.0.1']

function trimNul(value){const end=value.indexOf('\0');return (end>=0?value.slice(0,end):value).trim()}
function octal(value){const clean=trimNul(value).replace(/\s+/g,'');return clean?Number.parseInt(clean,8):0}
function safePath(value){
  const normalized=value.replaceAll('\\','/').replace(/^\.\//,'')
  if(!normalized||normalized.startsWith('/')||normalized.split('/').some(part=>part==='..'))throw new Error(`Caminho inseguro no pacote: ${value}`)
  return normalized
}

async function decodeVersion(version){
  const source=join(encodedRoot,version)
  const parts=(await readdir(source)).filter(name=>/^part-\d+\.b64$/.test(name)).sort()
  if(!parts.length)throw new Error(`Release ${version} sem partes Base64.`)
  const encoded=(await Promise.all(parts.map(name=>readFile(join(source,name),'utf8')))).join('').replace(/\s+/g,'')
  const tgz=Buffer.from(encoded,'base64')
  if(!tgz.length)throw new Error(`Release ${version} vazia.`)
  const tar=gunzipSync(tgz)
  const destination=join(outputRoot,version)
  await rm(destination,{recursive:true,force:true})
  await mkdir(destination,{recursive:true})
  let offset=0
  let files=0
  while(offset+512<=tar.length){
    const header=tar.subarray(offset,offset+512)
    if(header.every(byte=>byte===0))break
    const name=trimNul(header.subarray(0,100).toString('utf8'))
    const prefix=trimNul(header.subarray(345,500).toString('utf8'))
    const relative=safePath(prefix?`${prefix}/${name}`:name)
    const size=octal(header.subarray(124,136).toString('ascii'))
    const type=String.fromCharCode(header[156]||48)
    offset+=512
    const body=tar.subarray(offset,offset+size)
    if(type==='0'||type==='\0'){
      const target=join(destination,relative)
      await mkdir(dirname(target),{recursive:true})
      await writeFile(target,body)
      files+=1
    }else if(type==='5'){
      await mkdir(join(destination,relative),{recursive:true})
    }
    offset+=Math.ceil(size/512)*512
  }
  const entry=join(destination,'package','src','index.js')
  await readFile(entry)
  console.log(`ARGWS Visual Builder ${version}: ${files} arquivos materializados.`)
}

await mkdir(outputRoot,{recursive:true})
for(const version of versions)await decodeVersion(version)
