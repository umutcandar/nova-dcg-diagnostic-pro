"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const c=require("./web_corrections.js");
const labels=["Direnç","Diyot","Kondansatör","Entegre","Trimpot","Bilinmiyor"];
const W=1200,H=800;
const item=(box=[540,200,660,490],label="Kondansatör",confirmed=true)=>
  ({bbox_xyxy_pixels:box,label,confirmed});
function storage(){
  const map=new Map();
  return {get length(){return map.size;},getItem:k=>map.has(k)?map.get(k):null,
    setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k),key:i=>[...map.keys()][i]??null};
}
const hash="a".repeat(64);
test("only confirmed, known labels are correction candidates",()=>{
  assert.equal(c.makeEntry(item(undefined,"Bilinmiyor"),W,H,labels),null);
  assert.equal(c.makeEntry(item(undefined,"Kondansatör",false),W,H,labels),null);
  assert.equal(c.makeEntry(item(undefined,"Trimpot"),W,H,labels).human_verified,true);
  assert.equal(c.makeEntry(item([-1,0,10,10]),W,H,labels),null);
  assert.equal(c.photoKey("baddigest"),null);
});
test("correct mislabeled tall diode on identical photo",()=>{
  const original=[{...item(),"label":"Diyot",confidence:.47,confirmed:false,source:"model",id:3}];
  const change=c.makeEntry(item(),W,H,labels);
  const saved=c.upsert([],change,labels);
  const browser=storage();
  assert.equal(c.save(browser,hash,saved,labels),true);
  const again=c.apply(original,c.load(browser,hash,labels),W,H,labels);
  assert.equal(again.applied,1);
  assert.equal(again.restored,0);
  assert.equal(again.regions[0].label,"Kondansatör");
  assert.equal(again.regions[0].original_model_label,"Diyot");
  assert.equal(again.regions[0].confirmed,true);
  assert.equal(again.regions[0].source,"model");
  assert.equal(again.regions[0].confidence,.47);
  assert.equal(c.load(browser,"b".repeat(64),labels).length,0);
});
test("box shifts slightly across reanalysis and still matches",()=>{
 const saved=[c.makeEntry(item(),W,H,labels)];
 const source=[{...item([548,207,659,480],"Diyot",false),id:1}];
 const result=c.apply(source,saved,W,H,labels);
 assert.equal(result.applied,1);assert.equal(result.regions.length,1);
});
test("never overwrite an adjacent component using geometry-only proximity",()=>{
 const saved=[c.makeEntry(item(),W,H,labels)];
 const source=[{...item([705,190,775,475],"Diyot",false),id:2}];
 const result=c.apply(source,saved,W,H,labels);
 assert.equal(result.applied,0);
 assert.equal(result.regions[0].label,"Diyot");
 assert.equal(result.restored,1);
 assert.equal(result.regions[1].label,"Kondansatör");
});
test("one prior correction can only be assigned to one model box",()=>{
 const saved=[c.makeEntry(item(),W,H,labels)];
 const source=[{...item([535,201,659,484],"Diyot",false),id:3},
  {...item([540,198,660,490],"Trimpot",false),id:4}];
 const result=c.apply(source,saved,W,H,labels);
 assert.equal(result.applied,1);
 assert.equal(result.regions.filter(r=>r.label==="Kondansatör").length,1);
});
test("reviewed fresh choice wins over stale browser saved choice",()=>{
 const saved=[c.makeEntry(item(undefined,"Diyot"),W,H,labels)];
 const current=[{...item(),"human_verified":true}];
 const result=c.apply(current,saved,W,H,labels);
 assert.equal(result.applied,0);
 assert.equal(result.regions[0].label,"Kondansatör");
});
test("manual corrected candidate restores when detector finds nothing",()=>{
 const saved=[c.makeEntry(item(undefined,"Kondansatör"),W,H,labels)];
 const result=c.apply([],saved,W,H,labels);
 assert.equal(result.restored,1);
 assert.equal(result.regions[0].source,"local_review");
 assert.equal(result.regions[0].confirmed,true);
});
test("upsert replaces prior label on same region, not every part",()=>{
 const first=c.makeEntry(item(),W,H,labels);
 const second=c.makeEntry(item(undefined,"Diyot"),W,H,labels);
 const other=c.makeEntry(item([200,200,250,250],"Trimpot"),W,H,labels);
 const out=c.upsert(c.upsert([first],other,labels),second,labels);
 assert.equal(out.length,2);
 assert.equal(out.filter(x=>x.label==="Diyot").length,1);
 assert.equal(out.filter(x=>x.label==="Kondansatör").length,0);
});
test("review hints are caution only and never rewrite original label",()=>{
 const candidate=item([400,100,490,440],"Diyot",false);
 const hint=c.reviewHint(candidate,W,H);
 assert.match(hint,/Kondansatör/);
 assert.equal(candidate.label,"Diyot");
 assert.equal(c.reviewHint(item([100,200,370,230],"Diyot",false),W,H),null);
 assert.equal(c.reviewHint(item([400,100,490,440],"Kondansatör",false),W,H),null);
});
