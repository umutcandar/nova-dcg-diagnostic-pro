/* NOVA DCG - private browser photo-specific technician corrections.
   This module does not train/replace the ONNX model and never stores images.
   Corrections only apply to the identical image fingerprint, and are matched
   to the same component geometry to avoid overwriting neighboring parts.
*/
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports) module.exports=api;
  if(root) root.NovaCorrections=api;
})(typeof globalThis!=="undefined"?globalThis:null,function(){
  "use strict";
  const VERSION=1;
  const PREFIX="nova-dcg-review-v1:";
  const MAX_ITEMS=200;
  const MAX_PHOTOS=60;
  const MIN_IOU=.48;
  function validSize(w,h){return Number.isSafeInteger(w)&&w>0&&Number.isSafeInteger(h)&&h>0;}
  function validBox(b,w,h){
    return Array.isArray(b)&&b.length===4&&b.every(x=>typeof x==="number"&&Number.isFinite(x))&&
      b[0]>=0&&b[1]>=0&&b[2]<=w&&b[3]<=h&&b[0]<b[2]&&b[1]<b[3];
  }
  function normalized(box,w,h){
    if(!validSize(w,h)||!validBox(box,w,h))return null;
    return [box[0]/w,box[1]/h,box[2]/w,box[3]/h];
  }
  function iou(a,b){
    if(!Array.isArray(a)||!Array.isArray(b)||a.length!==4||b.length!==4||
       ![...a,...b].every(x=>typeof x==="number"&&Number.isFinite(x)))return 0;
    const intersection=Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0]))*
      Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));
    if(!intersection)return 0;
    const areaA=(a[2]-a[0])*(a[3]-a[1]),areaB=(b[2]-b[0])*(b[3]-b[1]);
    return areaA>0&&areaB>0?intersection/(areaA+areaB-intersection):0;
  }
  function validLabel(label,labels){
    return typeof label==="string"&&Array.isArray(labels)&&
      label!=="Bilinmiyor"&&labels.includes(label);
  }
  function isSavedEntry(entry,labels){
    if(!entry||typeof entry!=="object"||!validLabel(entry.label,labels))return false;
    if(!Array.isArray(entry.box)||entry.box.length!==4||
       !entry.box.every(x=>typeof x==="number"&&Number.isFinite(x)&&x>=0&&x<=1))return false;
    return entry.box[0]<entry.box[2]&&entry.box[1]<entry.box[3]&&entry.confirmed===true;
  }
  function makeEntry(region,w,h,labels){
    if(!region||region.confirmed!==true||!validLabel(region.label,labels))return null;
    const box=normalized(region.bbox_xyxy_pixels,w,h);
    if(!box)return null;
    return {box,label:region.label,confirmed:true,
      human_verified:true,source:"technician_local_review_v1"};
  }
  function upsert(entries,entry,labels){
    const result=Array.isArray(entries)?entries.filter(x=>isSavedEntry(x,labels)).slice(0,MAX_ITEMS):[];
    if(!isSavedEntry(entry,labels))return result;
    let best=-1,overlap=0;
    for(let i=0;i<result.length;i++){
      const v=iou(result[i].box,entry.box);
      if(v>overlap){best=i;overlap=v;}
    }
    if(best>=0&&overlap>=MIN_IOU)result[best]=entry;
    else if(result.length<MAX_ITEMS)result.push(entry);
    return result;
  }
  function apply(regions,entries,w,h,labels){
    if(!Array.isArray(regions)||!validSize(w,h)||!Array.isArray(entries))return {regions:regions||[],applied:0,restored:0};
    const result=regions.map(r=>({...r}));
    let applied=0,restored=0;
    const claimed=new Set();
    for(const saved of entries.slice(0,MAX_ITEMS)){
      if(!isSavedEntry(saved,labels))continue;
      let bestIndex=-1,bestOverlap=0;
      for(let i=0;i<result.length;i++){
        if(claimed.has(i))continue;
        const r=result[i],box=normalized(r.bbox_xyxy_pixels,w,h);
        if(!box)continue;
        const score=iou(box,saved.box);
        if(score>=MIN_IOU&&score>bestOverlap){bestIndex=i;bestOverlap=score;}
      }
      if(bestIndex>=0){
        const r=result[bestIndex];
        if(r.confirmed===true&&r.human_verified===true){
          // Keep a fresh, explicit correction even if browser memory is older.
          claimed.add(bestIndex);continue;
        }
        result[bestIndex]={...r,original_model_label:r.original_model_label||r.label,
          label:saved.label,confirmed:true,human_verified:true,
          correction_source:"same_photo_local_review",correction_applied:true};
        claimed.add(bestIndex);applied++;
      }else{
        // Restore an earlier manual annotation that the model missed.
        // Avoid creating a second object if an overlapping region already exists:
        // it is safer to ask for manual review than to duplicate close neighbors.
        const overlaps=result.some(r=>{
          const b=normalized(r.bbox_xyxy_pixels,w,h);
          return b&&iou(b,saved.box)>.18;
        });
        if(overlaps)continue;
        const box=[saved.box[0]*w,saved.box[1]*h,saved.box[2]*w,saved.box[3]*h];
        result.push({
          label:saved.label,confirmed:true,human_verified:true,
          bbox_xyxy_pixels:box,source:"local_review",confidence:null,
          correction_source:"same_photo_local_review",
          correction_applied:true,
          original_model_label:null
        });
        claimed.add(result.length-1);restored++;
      }
    }
    return {regions:result,applied,restored};
  }
  function photoKey(digest){
    if(typeof digest!=="string"||!/^[0-9a-f]{64}$/.test(digest))return null;
    return PREFIX+digest;
  }
  function load(storage,digest,labels){
    const key=photoKey(digest);
    if(!storage||!key)return [];
    try{
      const body=JSON.parse(storage.getItem(key)||"null");
      if(!body||body.version!==VERSION||!Array.isArray(body.items))return [];
      return body.items.slice(0,MAX_ITEMS).filter(x=>isSavedEntry(x,labels));
    }catch{return [];}
  }
  function save(storage,digest,entries,labels){
    const key=photoKey(digest);
    if(!storage||!key)return false;
    try{
      const safe=Array.isArray(entries)?entries.filter(x=>isSavedEntry(x,labels)).slice(0,MAX_ITEMS):[];
      storage.setItem(key,JSON.stringify({version:VERSION,items:safe}));
      const all=[];
      for(let i=0;i<storage.length;i++){
        const k=storage.key(i);
        if(typeof k==="string"&&k.startsWith(PREFIX))all.push(k);
      }
      for(const k of all){
        // Don't delete current photo; trim oldest entries using insertion order
        // on available Storage APIs. This stores only labels, not photographs.
        if(all.length<=MAX_PHOTOS)break;
        if(k!==key){storage.removeItem(k);all.splice(all.indexOf(k),1);}
      }
      return true;
    }catch{return false;}
  }
  function reviewHint(region,w,h){
    if(!region||region.label!=="Diyot"||!validSize(w,h)||!validBox(region.bbox_xyxy_pixels,w,h))return null;
    const b=region.bbox_xyxy_pixels;
    const width=b[2]-b[0],height=b[3]-b[1];
    if(height/width>=1.3&&height/h>=.20&&width/w>=.055){
      return "Bu büyük, dikey nesne diyot olmayabilir. Kondansatör veya başka metal kılıflı parçayı kontrol et.";
    }
    return null;
  }
  return Object.freeze({PREFIX,MAX_ITEMS,MIN_IOU,normalized,iou,makeEntry,
    isSavedEntry,upsert,apply,load,save,photoKey,reviewHint});
});
