#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
"""Generate a self-contained index.html ROM patcher.

Patch format (same as the reference patcher):
  "XDF1" + u32le source CRC32 + u32le output CRC32
        + u32le output size + u32le compressed size + raw-deflate XOR key
"""
from __future__ import annotations
import argparse
import base64
import struct
import zlib
from pathlib import Path

TEMPLATE = r'''<!DOCTYPE html>
<!-- SPDX-License-Identifier: GPL-3.0-only -->
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>超级机器人大战COMPACT3 汉化补丁 V2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0a1a;--card:rgba(18,18,40,.96);--bd:rgba(255,255,255,.07);--ac:#e63946;--ac2:#ffd166;--gn:#06d6a0;--tx:#e8e8f0;--dm:#7a7a9a;--bl:#4facfe}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--tx);font-family:"Segoe UI","Hiragino Sans",system-ui,sans-serif;padding:20px;overflow-x:hidden}
body::before{content:"";position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 30% 20%,rgba(230,57,70,.08) 0,transparent 50%),radial-gradient(circle at 70% 80%,rgba(79,172,254,.06) 0,transparent 50%);pointer-events:none}
.wrap{width:100%;max-width:540px;position:relative;z-index:1}
.card{background:var(--card);border:1px solid var(--bd);border-radius:24px;padding:30px 26px;backdrop-filter:blur(20px);box-shadow:0 30px 80px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.04)}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:22px}
.logo{display:flex;align-items:center;gap:11px}
.li{width:40px;height:40px;border-radius:11px;background:linear-gradient(135deg,var(--ac),#c1121f);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:#fff;letter-spacing:.5px}
h1{font-size:17px;font-weight:700;line-height:1.3}
.sub{font-size:11px;color:var(--dm);margin-top:2px}
.drop{position:relative;border:2px dashed rgba(255,255,255,.13);border-radius:16px;padding:30px 18px;text-align:center;cursor:pointer;transition:.2s;background:rgba(255,255,255,.02)}
.drop:hover,.drop.over{border-color:var(--ac);background:rgba(230,57,70,.07)}
.drop .ic{font-size:13px;font-weight:800;letter-spacing:2px;color:var(--ac2);margin-bottom:10px}
.drop p{font-size:13px;line-height:1.7}
.drop p.sm{font-size:11px;color:var(--dm);margin-top:6px}
.drop u{color:var(--bl);text-decoration:none}
.info{display:none;margin-top:16px;border:1px solid var(--bd);border-radius:12px;padding:12px 14px;background:rgba(255,255,255,.02)}
.row{display:flex;justify-content:space-between;gap:14px;font-size:12px;line-height:1.9}
.row span:first-child{color:var(--dm);white-space:nowrap}
.v{font-family:ui-monospace,Consolas,monospace;text-align:right;word-break:break-all}
.v.ok{color:var(--gn)} .v.er{color:var(--ac)} .v.wa{color:var(--ac2)}
.patchinfo{display:none;margin-top:12px;border:1px solid rgba(255,209,102,.35);border-radius:12px;padding:12px 14px;background:rgba(255,209,102,.05);font-size:11px;line-height:1.8}
.patchinfo .pih{color:var(--ac2);font-weight:700;margin-bottom:4px;font-size:12px}
.patchinfo .pir{display:flex;justify-content:space-between;gap:12px;color:var(--dm)}
.patchinfo .pir b{color:var(--tx);font-weight:600;text-align:right;word-break:break-all}
.fontsel{display:none;margin-top:12px;border:1px solid var(--bd);border-radius:12px;padding:10px 12px;background:rgba(255,255,255,.02)}
.fontsel .fsl{font-size:12px;color:var(--dm);margin-right:8px}
.fontsel label{display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:12px;cursor:pointer}
.fontsel label i{font-style:normal;font-size:10px;color:var(--dm)}
.fontsel input{accent-color:var(--ac)}
.bar{height:6px;border-radius:6px;background:rgba(255,255,255,.06);overflow:hidden;margin:18px 0 14px}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:width .25s}
button,#dl{display:block;width:100%;border:none;border-radius:12px;padding:13px 16px;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:.2s}
button#ap{background:linear-gradient(135deg,var(--ac),#c1121f);color:#fff}
button#ap:disabled{opacity:.45;cursor:not-allowed}
#dl{display:none;margin-top:10px;background:rgba(6,214,160,.14);border:1px solid rgba(6,214,160,.45);color:var(--gn);text-align:center;text-decoration:none}
#lg{margin-top:14px;font-family:ui-monospace,Consolas,monospace;font-size:11px;line-height:1.7;color:var(--dm);max-height:130px;overflow:auto;white-space:pre-wrap}
#lg .ok{color:var(--gn)} #lg .er{color:var(--ac)} #lg .ii{color:var(--bl)}
.note{margin-top:18px;padding-top:14px;border-top:1px solid var(--bd);font-size:11px;line-height:1.7;color:var(--dm)}

.ft{margin-top:8px;font-size:10px;line-height:1.7;color:rgba(255,255,255,.3);text-align:center}
.modal{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.74);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:18px}
.modal.hide{display:none}
.mbox{width:100%;max-width:440px;max-height:calc(100vh - 36px);overflow:auto;background:var(--card);border:1px solid rgba(255,209,102,.35);border-radius:18px;padding:22px 20px;box-shadow:0 30px 80px rgba(0,0,0,.75)}
.mbox h2{font-size:16px;color:var(--ac2);margin-bottom:10px}
.mbox p{font-size:12px;line-height:1.8;margin-bottom:8px;color:var(--tx)}
.mbox p.warn{color:var(--ac2);font-weight:700}
.mbox p.small{font-size:10px;color:var(--dm);margin-top:8px}
.mbox label{display:flex;gap:8px;align-items:flex-start;margin:12px 0;font-size:11px;line-height:1.6;color:var(--dm);cursor:pointer}
.mbox label input{margin-top:2px;accent-color:var(--ac)}
.mbox button{margin-top:4px;background:linear-gradient(135deg,var(--ac),#c1121f);color:#fff}
.mbox button:disabled{opacity:.4;cursor:not-allowed}
</style>
</head>
<body>
<div class="modal" id="notice" role="dialog" aria-modal="true" aria-labelledby="nt">
  <div class="mbox">
    <h2 id="nt">使用须知</h2>
    <p class="warn">补丁仅供自己游玩，禁止分发汉化后的 ROM。</p>
    <p>本页面只提供补丁工具，不提供游戏 ROM。打补丁后的汉化 ROM 请勿上传、分享、出售或再次分发。</p>
    <p>遇到 bug：添加 QQ <b>lcdyk66</b>，备注「游戏名 + 出现什么 bug」，并附上截图；有存档或即时存档更好。</p>
    <p>如果愿意参与剧情翻译或校准，也欢迎添加 QQ <b>lcdyk66</b>，备注「游戏名 + 翻译」或「游戏名 + 校准」。</p>
    <label><input type="checkbox" id="agree"> 我已阅读并同意：仅自己游玩，不分发汉化后的 ROM。</label>
    <button id="enter" disabled>进入</button>
    <p class="small">不同意的用户请关闭页面。</p>
  </div>
</div>
<div class="wrap">
  <div class="card">
    <div class="top">
      <div class="logo">
        <div class="li">SRW</div>
        <div>
          <h1>超级机器人大战COMPACT3</h1>
          <div class="sub">汉化补丁 V2 · WonderSwan Color</div>
        </div>
      </div>
    </div>

    <div class="drop" id="dz">
      <div class="ic">WSC ROM</div>
      <p>拖放原版日文 ROM 到此处，或<u>点击选择文件</u></p>
      <p class="sm">支持 .wsc / .ws，需通过原版 CRC 校验</p>
      <input type="file" id="fi" accept=".wsc,.ws" style="position:absolute;inset:0;opacity:0;cursor:pointer">
    </div>

    <div class="info" id="ni">
      <div class="row"><span>文件</span><span class="v" id="vn">-</span></div>
      <div class="row"><span>大小</span><span class="v" id="vs">-</span></div>
      <div class="row"><span>CRC32</span><span class="v" id="vc">-</span></div>
      <div class="row"><span>需要的原版 CRC</span><span class="v" id="vexp">-</span></div>
      <div class="row"><span>状态</span><span class="v" id="vd">-</span></div>
    </div>

    <div class="patchinfo" id="pi">
      <div class="pih">补丁信息 · V2</div>
      <div class="pir"><span>破解 / 文本初翻译</span><b>deepseek v4.1flash</b></div>
      <div class="pir"><span>文本第一轮校准</span><b>glm5.3</b></div>
      <div class="pir"><span>文本第二轮校准</span><b>gemini + glm5.3flash 翻译，deepseek 4.1flash 筛选</b></div>
      <div class="pir"><span>流程测试</span><b>Lily</b></div>
      <div class="pir"><span>干杂活</span><b>lcdyk</b></div>
      <div class="pir"><span>V2 修复</span><b>分支选项、梵·法内尔爱称、妮→尼；演示改动画；字体偏小</b></div>
      <div class="pir"><span>字体版本</span><b><span id="fname">宋体</span></b></div>
      <div class="pir"><span>CRC32</span><b><span id="pcrc">-</span> → <span id="ocrc">-</span></b></div>
    </div>

    <div class="fontsel" id="fs">
      <span class="fsl">字体</span>
      <label><input type="radio" name="font" value="simsun" checked><b>宋体</b><i>笔画扎实（推荐）</i></label>
      <label><input type="radio" name="font" value="fusion"><b>融合像素</b><i>点阵风格</i></label>
    </div>

    <div class="bar"><i id="pb"></i></div>
    <button id="ap" disabled>应用汉化补丁</button>
    <a id="dl">下载汉化 ROM</a>
    <div id="lg"></div>

    <div class="note">所有处理都在浏览器本地完成，不上传 ROM。请使用自己拥有的正版原版 ROM；补丁只适用于页面上显示的原版 CRC。</div>
    <div class="ft">V2 · XOR + Deflate · CRC32 · GPLv3</div>
  </div>
</div>

<script>
const PATCH_DATA={simsun:"__PATCH_SIMSUN_B64__",fusion:"__PATCH_FUSION_B64__"};
const FONT_NAME={simsun:"宋体",fusion:"融合像素"};
const OUT_NAMES={simsun:"超级机器人大战compact3[cn][lcdyk][v2].wsc",fusion:"超级机器人大战compact3[cn][lcdyk][v2][fusion].wsc"};
const $=id=>document.getElementById(id);
const CT=(()=>{const t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1);t[n]=c>>>0}return t})();
function crc32(u8){let c=0xFFFFFFFF;for(let i=0;i<u8.length;i++)c=(CT[(c^u8[i])&255]^(c>>>8))>>>0;return (c^0xFFFFFFFF)>>>0}
function hex8(n){return n.toString(16).toUpperCase().padStart(8,"0")}
function log(msg,cls){const d=document.createElement("div");if(cls)d.className=cls;d.textContent=msg;$("lg").appendChild(d);$("lg").scrollTop=$("lg").scrollHeight}
function stage(p,msg){$("pb").style.width=p+"%";if(msg)$("vd").textContent=msg}
let SRC=null,OUT=null,META=null,PATCHES={},SEL="simsun";
function parsePatch(b64){
  const bin=atob(b64),by=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++)by[i]=bin.charCodeAt(i);
  if(String.fromCharCode(by[0],by[1],by[2],by[3])!=="XDF1")throw new Error("补丁格式错误");
  const dv=new DataView(by.buffer);
  return {srcCrc:dv.getUint32(4,true),outCrc:dv.getUint32(8,true),size:dv.getUint32(12,true),comp:by.slice(20,20+dv.getUint32(16,true))};
}
for(const k in PATCH_DATA){if(!PATCH_DATA[k])continue;try{PATCHES[k]=parsePatch(PATCH_DATA[k])}catch(e){}}
function selectFont(k){
  if(!PATCHES[k])k="simsun";
  SEL=k;META=PATCHES[k];OUT=null;$("dl").style.display="none";
  $("fname").textContent=FONT_NAME[k]||k;
  if(META){$("vexp").textContent=hex8(META.srcCrc);$("pcrc").textContent=hex8(META.srcCrc);$("ocrc").textContent=hex8(META.outCrc)}
  if(SRC&&META){const c=crc32(SRC);$("ap").disabled=!(c===META.srcCrc&&SRC.length===META.size)}
}
if(PATCHES.simsun){selectFont("simsun");$("fs").style.display=Object.keys(PATCHES).length>1?"block":"none";}
else{$("vexp").textContent="补丁解析失败";$("vexp").className="v er"}
async function inflate(d){
  if(typeof DecompressionStream==="undefined")throw new Error("浏览器不支持 DecompressionStream（请用新版 Chrome/Edge/Firefox）");
  const ds=new DecompressionStream("deflate-raw"),w=ds.writable.getWriter();w.write(d);w.close();
  const rd=ds.readable.getReader(),ch=[];let tot=0;
  while(true){const{done,value}=await rd.read();if(done)break;ch.push(value);tot+=value.length}
  const o=new Uint8Array(tot);let off=0;for(const c of ch){o.set(c,off);off+=c.length}return o;
}
function readFile(f){
  if(!f)return;
  $("ni").style.display="block";$("vn").textContent=f.name;$("vs").textContent=f.size.toLocaleString()+" B";
  $("vc").textContent="...";$("vd").textContent="...";$("vd").className="v";$("ap").disabled=true;$("dl").style.display="none";$("lg").textContent="";$("pb").style.width="0";$("pi").style.display="none";SRC=null;OUT=null;
  const r=new FileReader();
  r.onload=e=>{
    SRC=new Uint8Array(e.target.result);
    const c=crc32(SRC);$("vc").textContent=hex8(c);
    if(!META){$("vd").textContent="补丁数据损坏";$("vd").className="v er";return}
    if(c!==META.srcCrc){$("vd").textContent="CRC 不匹配";$("vd").className="v er";log("这不是对应的原版 ROM（需要 "+hex8(META.srcCrc)+"）","er");return}
    if(SRC.length!==META.size){$("vd").textContent="文件大小不匹配";$("vd").className="v er";log("ROM 大小应为 "+META.size+" 字节","er");return}
    $("vd").textContent="原版 CRC 校验通过";$("vd").className="v ok";$("pi").style.display="block";$("ap").disabled=false;log("原版 ROM 校验通过","ok");
  };
  r.readAsArrayBuffer(f);
}
$("dz").addEventListener("click",()=>$("fi").click());
$("dz").addEventListener("dragover",e=>{e.preventDefault();$("dz").classList.add("over")});
$("dz").addEventListener("dragleave",()=>$("dz").classList.remove("over"));
$("dz").addEventListener("drop",e=>{e.preventDefault();$("dz").classList.remove("over");readFile(e.dataTransfer.files[0])});
$("fi").addEventListener("change",e=>{readFile(e.target.files[0])});
$("ap").addEventListener("click",async()=>{
  if(!SRC||!META)return;
  $("ap").disabled=true;$("lg").textContent="";$("dl").style.display="none";
  try{
    log("开始应用补丁","ii");stage(10,"解压补丁数据...");
    const key=await inflate(META.comp);
    stage(60,"还原 ROM...");
    const res=new Uint8Array(META.size);
    for(let i=0;i<META.size;i++)res[i]=(i<SRC.length?SRC[i]:0)^(i<key.length?key[i]:0);
    stage(90,"校验输出 CRC...");
    const oc=crc32(res);log("输出 CRC32: "+hex8(oc),"ii");
    if(oc!==META.outCrc)throw new Error("输出 CRC 校验失败");
    OUT=new Blob([res],{type:"application/octet-stream"});
    stage(100,"补丁应用成功");log("补丁应用成功","ok");$("dl").style.display="block";
  }catch(e){stage(0,"失败");log("失败："+e.message,"er");$("ap").disabled=false}
});
document.querySelectorAll("input[name=font]").forEach(el=>el.addEventListener("change",e=>{
  selectFont(e.target.value);
  if(SRC)log("已切换字体："+(FONT_NAME[SEL]||SEL),"ii");
}));
$("agree").addEventListener("change",e=>{$("enter").disabled=!e.target.checked});
$("enter").addEventListener("click",()=>{$("notice").classList.add("hide")});
$("dl").addEventListener("click",()=>{
  if(!OUT)return;
  const a=document.createElement("a");a.href=URL.createObjectURL(OUT);
  a.download=OUT_NAMES[SEL]||OUT_NAMES.simsun;
  a.click();URL.revokeObjectURL(a.href);log("已开始下载","ok");
});
</script>
</body>
</html>'''


def pack(src: bytes, patched: bytes, src_crc: int) -> tuple[str, int, int]:
    if len(src) != len(patched):
        raise SystemExit(f"ROM 大小不一致: {len(src)} != {len(patched)}")
    out_crc = zlib.crc32(patched) & 0xFFFFFFFF
    key = bytes(a ^ b for a, b in zip(src, patched))
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    comp = co.compress(key) + co.flush()
    assert zlib.decompress(comp, -15) == key
    blob = b"XDF1" + struct.pack("<IIII", src_crc, out_crc, len(patched), len(comp)) + comp
    return base64.b64encode(blob).decode("ascii"), out_crc, len(blob)


def main():
    ap = argparse.ArgumentParser(description="Generate a self-contained WSC patch page.")
    ap.add_argument("-i", "--input", required=True, help="原版日文 ROM")
    ap.add_argument("-o", "--patched", required=True, help="宋体汉化 ROM（默认字体）")
    ap.add_argument("--fusion", help="融合像素汉化 ROM（提供后页面出现字体选择）")
    ap.add_argument("--out", help="输出 HTML（默认 index.html）")
    args = ap.parse_args()
    src = Path(args.input).read_bytes()
    src_crc = zlib.crc32(src) & 0xFFFFFFFF
    b64_s, crc_s, len_s = pack(src, Path(args.patched).read_bytes(), src_crc)
    b64_f, crc_f, len_f = "", 0, 0
    if args.fusion:
        b64_f, crc_f, len_f = pack(src, Path(args.fusion).read_bytes(), src_crc)
    out = Path(args.out) if args.out else Path(__file__).with_name("index.html")
    html = (TEMPLATE.replace("__PATCH_SIMSUN_B64__", b64_s)
                    .replace("__PATCH_FUSION_B64__", b64_f))
    out.write_text(html, encoding="utf-8")
    print(f"source CRC32: {src_crc:08X}")
    print(f"simsun output CRC32: {crc_s:08X}  patch {len_s} B")
    if b64_f:
        print(f"fusion output CRC32: {crc_f:08X}  patch {len_f} B")
    print(f"written: {out}  ({len(html)} chars)")


if __name__ == "__main__":
    main()
