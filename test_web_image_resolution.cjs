// Run the actual embedded browser image encoder with a safe fake canvas.
// We test pixels sent for ONNX, not merely the presence of a magic string.
"use strict";
const fs=require("node:fs");
const vm=require("node:vm");
const test=require("node:test");
const assert=require("node:assert/strict");
const html=fs.readFileSync("web_studio.html","utf8");
const start=html.indexOf("function analysisImage(){");
const finish=html.indexOf("async function analyze(){",start);
assert.ok(start>=0&&finish>start,"missing embedded image encoder");
const source=html.slice(start,finish);

function encode(w,h,options={}){
  const calls=[];
  const canvas={
    width:0,height:0,
    getContext:()=>({drawImage(){}}),
    toDataURL(type,quality){
      calls.push({w:canvas.width,h:canvas.height,type,quality});
      if(options.alwaysOversize||options.firstOversize&&calls.length===1)
        return "data:image/jpeg;base64,"+"Z".repeat(15000000);
      return "data:image/jpeg;base64,ok";
    }
  };
  const context={document:{createElement(kind){
    assert.equal(kind,"canvas");return canvas;
  }},imgW:w,imgH:h,photo:{}};
  const fn=vm.runInNewContext("("+source+")",context);
  if(options.alwaysOversize)
    assert.throws(()=>fn(),/sıkıştırılamadı/);
  else
    assert.equal(fn(),"data:image/jpeg;base64,ok");
  return calls;
}

test("native 4K PCB photo keeps all available pixel detail",()=>{
  const calls=encode(4096,3072);
  assert.equal(calls.length,1);
  assert.deepEqual([calls[0].w,calls[0].h],[4096,3072]);
  assert.equal(calls[0].type,"image/jpeg");
});
test("8K photo is reduced only to 4096px, not old 1600px thumbnail",()=>{
  const calls=encode(7680,4320);
  assert.deepEqual([calls[0].w,calls[0].h],[4096,2304]);
});
test("small PCB photos are never upscaled",()=>{
  const calls=encode(640,480);
  assert.deepEqual([calls[0].w,calls[0].h],[640,480]);
});
test("oversized encoded picture is recompressed before upload",()=>{
  const calls=encode(4096,3072,{firstOversize:true});
  assert.equal(calls.length,2);
  assert.ok(calls[1].w<calls[0].w);
  assert.ok(calls[1].quality<calls[0].quality);
});
test("encoder fails safely rather than sending an oversized JSON payload",()=>{
  const calls=encode(8192,6144,{alwaysOversize:true});
  assert.equal(calls.length,8);
});
